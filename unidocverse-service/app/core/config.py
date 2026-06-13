import configparser
import logging
import platform
import os
from pydantic_settings import BaseSettings
from pathlib import Path
from app.config.model_manager import get_model_registry

logger = logging.getLogger(__name__)

# ---------------------------------------------------------
# Active model — single source of truth
# Priority: DB settings table > .env > hardcoded default
# ---------------------------------------------------------
from app.core.profiler import detect_hardware

profile = detect_hardware()

model     = profile["llm_model"]
embedding = profile["embed_model"]

CURRENT_MODEL = {"name": model}


def _load_active_model() -> str:
    """
    Load the active model from the DB settings table.
    Falls back to .env OLLAMA_MODEL, then profile suggested model.
    Called once at startup so the last FE-selected model persists across restarts.
    """
    global model, CURRENT_MODEL
    db_model = None
    try:
        from sqlalchemy import create_engine, text
        db_url = (
            f"postgresql://"
            f"{os.getenv('DB_USER', 'unidocverse')}:"
            f"{os.getenv('DB_PASSWORD', 'unidocverse')}@"
            f"{os.getenv('DB_HOST', 'localhost')}:"
            f"{os.getenv('DB_PORT', '54321')}/"
            f"{os.getenv('DB_NAME', 'unidocverse_db')}"
        )
        engine = create_engine(db_url)
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT value FROM settings WHERE key = 'active_model' LIMIT 1")
            ).fetchone()
            if row:
                db_model = row[0]
    except Exception as e:
        logger.warning(f"⚠️ Could not load model from DB: {e}")

    # Fallback order: DB model -> .env model -> profile recommendation
    env_model = os.getenv("OLLAMA_MODEL")
    selected = db_model or env_model

    if selected:
        model = selected
        if profile["tier"] == "low" and model != profile["llm_model"]:
            logger.warning(f"⚠️ Low-spec system detected ({profile['ram_gb']}GB RAM), but using user-specified model: {model}")
    else:
        model = profile["llm_model"]

    CURRENT_MODEL["name"] = model
    try:
        settings.OLLAMA_MODEL = model
    except NameError:
        pass
    logger.info(f"✅ Active model resolved: {model}")
    return model


def _persist_active_model(name: str) -> None:
    """
    Save the selected model to the DB settings table so it
    survives server restarts.
    """
    try:
        from sqlalchemy import create_engine, text
        db_url = (
            f"postgresql://"
            f"{os.getenv('DB_USER', 'unidocverse')}:"
            f"{os.getenv('DB_PASSWORD', 'unidocverse')}@"
            f"{os.getenv('DB_HOST', 'localhost')}:"
            f"{os.getenv('DB_PORT', '54321')}/"
            f"{os.getenv('DB_NAME', 'unidocverse_db')}"
        )
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(
                text("""
                    INSERT INTO settings (key, value)
                    VALUES ('active_model', :val)
                    ON CONFLICT (key) DO UPDATE SET value = :val
                """),
                {"val": name}
            )
            conn.commit()
        logger.info(f"✅ Active model persisted to DB: {name}")
    except Exception as e:
        logger.warning(f"⚠️ Could not persist model to DB: {e}")


def set_model(name: str) -> str:
    """
    Switch the active model. Updates in-memory global AND persists to DB.
    Called by the FE model switch API — survives restarts.
    """
    global model, CURRENT_MODEL
    registry = get_model_registry()

    if name in registry:
        model = name
        CURRENT_MODEL["name"] = name
        _persist_active_model(name)
        logger.info(f"✅ Model switched to: {name}")
        return model

    # Model not installed — keep current
    logger.warning(f"⚠️ Model '{name}' not in registry, keeping '{model}'")
    return f"Model '{name}' is not installed. Keeping current model '{model}'."


def get_active_model() -> str:
    """Always returns the current active model name."""
    return model


def _load_ollama_conf(models_path: Path) -> dict:
    conf_path = models_path / "ollama.conf"
    if not conf_path.exists():
        logger.warning(f"⚠️ ollama.conf not found at {conf_path}, using defaults")
        return {}

    parser = configparser.ConfigParser()
    parser.read(conf_path)

    return {
        "OLLAMA_HOST":            f"http://{parser.get('server', 'host', fallback='127.0.0.1')}:{parser.get('server', 'port', fallback='11434')}",
        "OLLAMA_NUM_PARALLEL":    parser.getint("server", "num_parallel", fallback=1),
        "OLLAMA_MAX_QUEUE":       parser.getint("server", "max_queue", fallback=5),
        "OLLAMA_MODEL":           parser.get("models", "default", fallback=model),
        "OLLAMA_EMBEDDING_MODEL": parser.get("models", "embedding", fallback="all-mpnet-base-v2"),
    }


class Settings(BaseSettings):
    APP_NAME:    str  = "UniDocVerse AI Service"
    APP_VERSION: str  = "1.0.0"
    DEBUG:       bool = False

    DB_HOST:     str = "localhost"
    DB_PORT:     int = 54321
    DB_NAME:     str = "unidocverse_db"
    DB_USER:     str = "unidocverse"
    DB_PASSWORD: str = "unidocverse"

    @property
    def DATABASE_URL(self) -> str:
        return f"postgresql://{self.DB_USER}:{self.DB_PASSWORD}@{self.DB_HOST}:{self.DB_PORT}/{self.DB_NAME}"

    MODELS_PATH:   Path = Path("../models")
    UPLOAD_DIR:    Path = Path.home() / "Library/Application Support/UniDocVerse/storage/uploads"
    PROCESSED_DIR: Path = Path.home() / "Library/Application Support/UniDocVerse/storage/processed"

    MAX_FILE_SIZE_MB: int = 50

    ALLOWED_EXTENSIONS: list[str] = [
        ".pdf", ".doc", ".docx", ".odt", ".rtf", ".txt", ".md",
        ".html", ".htm", ".xlsx", ".xls", ".xlsm", ".csv", ".tsv",
        ".ods", ".parquet", ".json", ".jsonl", ".pptx", ".ppt",
        ".odp", ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff",
        ".tif", ".webp", ".heic", ".heif", ".eml", ".msg", ".mbox",
        ".xml", ".yaml", ".yml"
    ]

    OLLAMA_HOST:            str = "http://127.0.0.1:11434"
    OLLAMA_MODEL:           str = model
    OLLAMA_EMBEDDING_MODEL: str = embedding
    OLLAMA_NUM_PARALLEL:    int = profile["max_workers"]
    OLLAMA_MAX_QUEUE:       int = profile["max_workers"] * 2

    CORS_ORIGINS: list[str] = [
        "http://localhost:4200",
        "http://localhost:3000",
        "http://localhost:8000",
        "http://localhost:8080",
        "http://localhost",
        "https://unidocverse.com",
        "https://www.unidocverse.com",
        "https://staging.unidocverse.com",
    ]

    class Config:
        extra = 'ignore'
        env_file = ".env"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # ollama.conf overlays on top of .env defaults
        ollama_conf = _load_ollama_conf(self.MODELS_PATH)
        for key, value in ollama_conf.items():
            object.__setattr__(self, key, value)

        # Platform-aware OCR
        system = platform.system().lower()
        if system in ("darwin", "windows", "linux"):
            os.environ["ENABLE_OCR"] = "true"
            os.environ["PADDLE_PDX_DISABLE_MODEL_SOURCE_CHECK"] = "true"
            os.environ["OCR_MODE"] = "landingai"
            logger.info(f"🧠 OCR enabled ({system} desktop mode)")
        else:
            os.environ["ENABLE_OCR"] = "false"
            os.environ["OCR_MODE"] = "none"
            logger.info("🚫 OCR disabled (server mode)")


settings = Settings()

settings.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
settings.PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

# Load active model from DB — overwrites module-level default
# Must run after settings so DB connection details are available
_load_active_model()