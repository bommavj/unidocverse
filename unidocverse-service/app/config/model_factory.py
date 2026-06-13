import os
from pathlib import Path
from threading import Lock

from sentence_transformers import SentenceTransformer


class EmbeddingModelFactory:
    """Thread-safe singleton factory for SentenceTransformer embedding model."""

    _instance: SentenceTransformer = None
    _lock = Lock()

    # Project root (…/unidocverse-service)
    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    @classmethod
    def get_model(cls) -> SentenceTransformer:
        """
        Return a singleton SentenceTransformer instance.
        Model is loaded strictly from local disk (offline mode).
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    # Enforce offline mode
                    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

                    # Resolve path dynamically using the settings configuration
                    env_path = os.getenv("MODEL_PATH")
                    if env_path:
                        model_path = Path(env_path)
                    else:
                        from app.core.config import settings
                        model_path = cls.PROJECT_ROOT / "models" / settings.OLLAMA_EMBEDDING_MODEL

                    if not model_path.exists():
                        raise FileNotFoundError(
                            f"Embedding model not found at: {model_path}"
                        )

                    cls._instance = SentenceTransformer(
                        str(model_path)
                    )

        return cls._instance
