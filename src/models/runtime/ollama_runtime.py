"""
Concrete Ollama runtime adapter implementation.
Sole module authorized to interface directly with local Ollama engine API calls.
"""

from typing import Any, Dict, List, Optional
from config.settings import settings
from src.core.exceptions import ModelException
from src.models.runtime.base_runtime import BaseRuntime
from utils.logger import logger

import os
from urllib.parse import urlparse
from src.security.network_policy import NetworkPolicy, NetworkPolicyError

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    ollama = None  # type: ignore
    OLLAMA_AVAILABLE = False


class OllamaRuntime(BaseRuntime):
    """
    Adapter implementing BaseRuntime for local Ollama server deployments.
    """

    def __init__(self, host: Optional[str] = None, timeout: Optional[float] = None) -> None:
        self.host = host or settings.OLLAMA_BASE_URL
        self.timeout = timeout or settings.OLLAMA_TIMEOUT
        self._client: Optional[Any] = None

        # Validate endpoint locality in strict offline mode
        if getattr(settings, "OFFLINE_STRICT_MODE", True):
            policy = NetworkPolicy()
            if not policy.is_allowed_url(self.host):
                raise ModelException(f"Remote model endpoint '{self.host}' rejected by offline policy.")

    def is_cloud_disabled(self) -> bool:
        """Check if OLLAMA_NO_CLOUD is set in environment."""
        return os.getenv("OLLAMA_NO_CLOUD", "0") in ("1", "true", "TRUE")

    def _get_client(self) -> Any:
        """
        Lazily initialize and return the ollama.Client instance.
        """
        if not OLLAMA_AVAILABLE:
            raise ModelException("The 'ollama' Python package is not installed. Please install 'ollama>=0.2.0'.")
        if self._client is None:
            self._client = ollama.Client(host=self.host, timeout=self.timeout)
        return self._client

    def load_model(self, model_name: str, **kwargs: Any) -> bool:
        """
        Pre-load a model into Ollama engine memory using zero keep-alive prompt warm-up.
        """
        try:
            client = self._get_client()
            logger.info(f"OllamaRuntime: Loading model '{model_name}'...")
            client.generate(model=model_name, prompt="", keep_alive=kwargs.get("keep_alive", "10m"))
            logger.info(f"OllamaRuntime: Model '{model_name}' successfully loaded into VRAM.")
            return True
        except Exception as e:
            logger.error(f"OllamaRuntime: Failed to load model '{model_name}': {e}")
            return False

    def unload_model(self, model_name: str, **kwargs: Any) -> bool:
        """
        Evict a model from VRAM by setting keep_alive=0.
        """
        try:
            client = self._get_client()
            logger.info(f"OllamaRuntime: Evicting model '{model_name}' from VRAM...")
            client.generate(model=model_name, prompt="", keep_alive=0)
            logger.info(f"OllamaRuntime: Model '{model_name}' successfully evicted from VRAM.")
            return True
        except Exception as e:
            logger.warning(f"OllamaRuntime: Error while evicting model '{model_name}': {e}")
            return False

    def generate(self, prompt: str, model_name: str, **kwargs: Any) -> str:
        """
        Execute text generation on Ollama for the specified model tag.
        """
        try:
            client = self._get_client()
            temperature = kwargs.get("temperature", settings.TEMPERATURE)
            top_p = kwargs.get("top_p", settings.TOP_P)
            max_tokens = kwargs.get("max_tokens", settings.MAX_TOKENS)

            options = {
                "temperature": temperature,
                "top_p": top_p,
                "num_predict": max_tokens,
            }

            gen_payload = {
                "model": model_name,
                "prompt": prompt,
                "options": options,
                "stream": False,
            }
            images = kwargs.get("images")
            if images:
                gen_payload["images"] = images

            response = client.generate(**gen_payload)
            return response.get("response", "")
        except Exception as e:
            logger.error(f"OllamaRuntime: Generation error for model '{model_name}': {e}")
            raise ModelException(f"Ollama generation failed for '{model_name}': {e}") from e

    def list_models(self) -> List[str]:
        """
        Query Ollama server for currently installed model tags.
        """
        try:
            client = self._get_client()
            response = client.list()
            models_list = response.get("models", [])
            names = []
            for item in models_list:
                if isinstance(item, dict):
                    names.append(item.get("name") or item.get("model", ""))
                elif hasattr(item, "model"):
                    names.append(getattr(item, "model", ""))
                elif hasattr(item, "name"):
                    names.append(getattr(item, "name", ""))
                else:
                    names.append(str(item))
            return [n for n in names if n]
        except Exception as e:
            logger.warning(f"OllamaRuntime: Failed to list models: {e}")
            return []

    def health(self) -> Dict[str, Any]:
        """
        Check health status of the local Ollama server.
        """
        if not OLLAMA_AVAILABLE:
            return {
                "runtime": "ollama",
                "available": False,
                "error": "ollama package missing",
                "models_count": 0,
            }
        try:
            models = self.list_models()
            return {
                "runtime": "ollama",
                "available": True,
                "endpoint": self.host,
                "models_count": len(models),
                "installed_models": models,
            }
        except Exception as e:
            return {
                "runtime": "ollama",
                "available": False,
                "endpoint": self.host,
                "error": str(e),
                "models_count": 0,
            }
