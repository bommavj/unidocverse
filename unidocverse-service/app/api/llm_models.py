# routes/model_routes.py

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.config.model_manager import get_model_registry
from app.core import config
from app.config.model_manager import get_model_registry

router = APIRouter(prefix="/api/models", tags=["models"])

import logging
logger = logging.getLogger(__name__)

class ModelRequest(BaseModel):
    model_name: str


@router.post("/set-model")
def set_model(req: ModelRequest):
    requested = req.model_name
    selected = config.set_model(requested)

    model_info = {
        "success": True,
        "selected_model": selected,
        "message": f"Model '{selected}' selected successfully."
    }
    logger.info(f"{model_info}")
    return model_info


@router.get("/get-model")
def get_model():
    return {
        "selected_model": config.model,
        "message": f"Current active model is '{config.model}'."
    }


@router.get("/list-models")
def list_models():
    registry = get_model_registry()

    return {
        "installed_models": list(registry.keys()),
        "count": len(registry),
        "message": "Installed models discovered successfully."
    }


class TranslateDictRequest(BaseModel):
    target_lang: str
    dictionary: dict


@router.post("/translate-dict")
def translate_dict(req: TranslateDictRequest):
    import json
    from app.agents.langgraph_agents import ollama_client
    
    prompt = f"""You are a professional dictionary translator.
Translate the values of this JSON dictionary from English into "{req.target_lang}".
Keep the JSON keys exactly the same. Do not change the keys, only translate the values.
Translate them contextually as UI labels for a document analysis app dashboard.
Output ONLY the final translated JSON.

JSON Dictionary to translate:
{json.dumps(req.dictionary, ensure_ascii=False)}
"""
    try:
        res = ollama_client.generate(
            model=config.model,
            prompt=prompt,
            format="json",
            options={"temperature": 0.0}
        )
        response_text = res.get("response", "").strip()
        
        # Robust JSON boundary extractor
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}')
        if start_idx != -1 and end_idx != -1:
            response_text = response_text[start_idx:end_idx+1]
            
        translated = json.loads(response_text)
        return {"success": True, "translated": translated}
    except Exception as e:
        logger.error(f"Failed to translate dictionary to {req.target_lang}: {e}")
        return {"success": False, "translated": req.dictionary, "error": str(e)}
