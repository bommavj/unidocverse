from dotenv import load_dotenv
import os
load_dotenv()

# ── MUST BE FIRST — before any torch/paddle imports ──────────────────────────
os.environ["USE_PADDLEX"] = "0"
os.environ["PADDLEOCR_USE_PADDLEX"] = "0"
os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "true"
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["FLAGS_allocator_strategy"] = "naive_best_fit"
os.environ["PYTORCH_MPS_DISABLE"] = "1"
os.environ["PYTORCH_ENABLE_MPS_FALLBACK"] = "1"
os.environ["PYTORCH_MPS_HIGH_WATERMARK_RATIO"] = "0.0"

import sys
import logging
import asyncio
import socket
from pathlib import Path
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

import numpy as np
from fastapi import FastAPI, Depends, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.langgraph_agents import ollama_client
from app.agents.workflow import compile_workflow
from app.api import (
    documents, analytics, search, stats, upload, uni_license,
    llm_models, insights, ask_router, alerts_router,
    notifications_router, auth_router, clients_router,
    policies_router, features_router, agency_router,
    commission_router, gap_analysis_router, coi_router,
    loss_run_router, renewal_router, agency_settings_router,
    gmail_api, watch_folders, calendar_router, personal_router,
    domains_router, integrations_router
)
from app.api.progress import router as progress_router
from app.api.whatsapp_qr_router import router as whatsapp_qr_router
from app.core import config
from app.core.config import settings
from app.core.database import engine, get_db, SessionLocal
from app.core.tesseract_config import configure_tesseract
from app.models.document import Document
from app.services.preload import preload_manager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

langgraph_app = None


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global langgraph_app
    logger.info("🚀 Starting UniDocVerse AI Service...")

    # Preload models
    asyncio.create_task(preload_manager.preload_all())

    # Start background schedulers (renewal emails, follow-ups, etc.)
    from app.services import scheduler
    scheduler.start()

    configure_tesseract()

    # DB check
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("✅ PostgreSQL connection successful")
        
        # Initialize DB tables
        from app.core.database import init_db
        init_db()
    except Exception as e:
        logger.error(f"❌ Database connection failed/initialization failed: {e}")
        raise

    # LangGraph workflow
    try:
        logger.info("🤖 Compiling LangGraph workflow...")
        langgraph_app = compile_workflow()
        logger.info("✅ LangGraph workflow ready")
    except Exception as e:
        logger.error(f"❌ Failed to compile LangGraph workflow: {e}")
        raise

    logger.info("✅ Server ready at http://localhost:8000")

    # ── Auto-activate 90-day trial on first launch ────────────────────────
    try:
        from app.core.activation import create_trial_activation, get_trial_status
        from app.license.license_paths import get_license_path
        if not get_license_path().exists():
            trial = create_trial_activation()
            status = get_trial_status(trial)
            logger.info(f"✅ 90-day trial activated — expires: {trial['expiry_at'][:10]}")
        else:
            logger.info("✅ License already active")
    except Exception as _e:
        logger.warning(f"⚠ Trial auto-activation skipped: {_e}")
    yield
    logger.info("👋 Shutting down UniDocVerse AI Service...")


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(documents.router)
app.include_router(analytics.router)
app.include_router(search.router)
app.include_router(stats.router)
app.include_router(upload.router)
app.include_router(uni_license.router)
app.include_router(progress_router)
app.include_router(watch_folders.router)
app.include_router(gmail_api.router)
app.include_router(llm_models.router)
app.include_router(insights.router)
app.include_router(ask_router.router)
app.include_router(alerts_router.router)
app.include_router(notifications_router.router)
app.include_router(integrations_router.router)
app.include_router(whatsapp_qr_router)
app.include_router(auth_router.router)
app.include_router(clients_router.router)
app.include_router(policies_router.router)
app.include_router(features_router.router)
app.include_router(agency_router.router)
app.include_router(commission_router.router)
app.include_router(gap_analysis_router.router)
app.include_router(coi_router.router)
app.include_router(loss_run_router.router)
app.include_router(renewal_router.router)
app.include_router(agency_settings_router.router)
app.include_router(calendar_router.router)
app.include_router(personal_router.router)
app.include_router(domains_router.router)

# ── Health check ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        return {"status": "healthy", "database": "connected",
                "timestamp": datetime.utcnow().isoformat()}
    except Exception as e:
        return {"status": "unhealthy", "database": "disconnected",
                "error": str(e), "timestamp": datetime.utcnow().isoformat()}


# ── Upload ────────────────────────────────────────────────────────────────────

from app.core.profiler import detect_hardware
_profile = detect_hardware()
_UPLOAD_EXECUTOR = ThreadPoolExecutor(max_workers=_profile["max_workers"])  # limit concurrency dynamically based on hardware specs


def _process_single_upload(file_bytes: bytes, filename: str, content_type: str) -> dict:
    from app.services.processing_service import ProcessingService
    return ProcessingService.process_sync(file_bytes, filename, content_type)


@app.post("/api/upload/batch")
async def upload_batch(files: list[UploadFile] = File(...)):
    file_data = [{"bytes": await f.read(), "filename": f.filename,
                  "content_type": f.content_type} for f in files]
    loop    = asyncio.get_event_loop()
    futures = [
        loop.run_in_executor(
            _UPLOAD_EXECUTOR,
            _process_single_upload,
            fd["bytes"], fd["filename"], fd["content_type"]
        )
        for fd in file_data
    ]
    results   = await asyncio.gather(*futures)
    succeeded = sum(1 for r in results if r.get("status") == "success")
    return {"results": list(results), "total": len(results),
            "succeeded": succeeded, "failed": len(results) - succeeded}


@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    file_bytes = await file.read()
    result     = _process_single_upload(file_bytes, file.filename, file.content_type)
    if result.get("status") == "error":
        raise HTTPException(status_code=500, detail=result["error"])
    return result


# ── Serve Angular frontend — MUST BE LAST ─────────────────────────────────────

_frontend_env = os.getenv("FRONTEND_DIR", "")

if getattr(sys, 'frozen', False):
    resources_path = Path(sys.executable).parent.parent
    FRONTEND_DIR   = resources_path / "frontend"
elif _frontend_env:
    FRONTEND_DIR = Path(_frontend_env)
else:
    FRONTEND_DIR = (
        Path(__file__).parent.parent
        / "unidocverse-dashboard"
        / "dist" / "unidocverse-dashboard" / "browser"
    )

if FRONTEND_DIR.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIR), html=True), name="frontend")
    logger.info(f"✅ Angular frontend mounted from {FRONTEND_DIR}")
else:
    logger.warning(f"⚠ Frontend not found at {FRONTEND_DIR} — API-only mode")

    @app.get("/")
    async def root_fallback():
        return {"status": "running", "note": "Frontend not built yet"}


# ── Entry point ───────────────────────────────────────────────────────────────

def _port_in_use(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


if __name__ == "__main__":
    import uvicorn
    host = "0.0.0.0"
    port = int(os.getenv("PORT", "8000"))
    if _port_in_use("127.0.0.1", port):
        logger.info(f"⚠️ Port {port} already in use — skipping")
    else:
        uvicorn.run(app, host=host, port=port, reload=False,
                    workers=1, lifespan="on", log_level="info")