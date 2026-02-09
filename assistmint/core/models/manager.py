"""
Model Manager - Multi-model management with per-module switching.

Loads model configuration from ~/.assistmint/config.yaml and routes
requests to the correct Ollama model based on module name.
"""
import os
import yaml
import requests
from typing import Dict, Optional, List
from dataclasses import dataclass

# Config file location
CONFIG_DIR = os.path.expanduser("~/.assistmint")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")

# Ollama API settings from central config
try:
    from config import (
        OLLAMA_API_URL, OLLAMA_CHECK_TIMEOUT, OLLAMA_LIST_TIMEOUT,
        OLLAMA_COMPLETION_TIMEOUT
    )
    OLLAMA_API = OLLAMA_API_URL
except ImportError:
    OLLAMA_API = "http://localhost:11434"
    OLLAMA_CHECK_TIMEOUT = 2
    OLLAMA_LIST_TIMEOUT = 5
    OLLAMA_COMPLETION_TIMEOUT = 120


@dataclass
class ModelConfig:
    """Configuration for model selection."""
    default: str = "qwen2.5:7b"
    models: Dict[str, str] = None

    def __post_init__(self):
        if self.models is None:
            self.models = {}


class ModelManager:
    """
    Manages model selection per module.

    Each module can have its own model assigned in config.yaml:

    models:
      default: qwen2.5:7b
      terminal: mistral
      coding: qwen2.5-coder:7b
      chat: llama3
    """

    def __init__(self):
        self._config: Dict = {}
        self._model_config = ModelConfig()
        self._current_model: Optional[str] = None
        self._messages: Dict[str, List[dict]] = {}  # Per-module message history
        self._load_config()

    def _load_config(self):
        """Load config from YAML file."""
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r') as f:
                    self._config = yaml.safe_load(f) or {}

                models_section = self._config.get('models', {})
                self._model_config = ModelConfig(
                    default=models_section.get('default', 'qwen2.5:7b'),
                    models=models_section
                )
                print(f"[ModelManager] Loaded config from {CONFIG_FILE}")
            except Exception as e:
                print(f"[ModelManager] Error loading config: {e}")
        else:
            print(f"[ModelManager] No config file at {CONFIG_FILE}, using defaults")

    def reload_config(self):
        """Reload config from file (for runtime updates)."""
        self._load_config()

    def get_model_for_module(self, module_name: str) -> str:
        """Get the model assigned to a module."""
        model = self._model_config.models.get(module_name)
        if model:
            return model
        return self._model_config.default

    def set_model_for_module(self, module_name: str, model: str):
        """Set model for a specific module (runtime only, not saved)."""
        self._model_config.models[module_name] = model

    def get_config(self, section: str, key: str = None, default=None):
        """Get config value from a section."""
        section_data = self._config.get(section, {})
        if key is None:
            return section_data
        return section_data.get(key, default)

    def list_available_models(self) -> List[str]:
        """Fetch available models from Ollama."""
        try:
            response = requests.get(f"{OLLAMA_API}/api/tags", timeout=OLLAMA_LIST_TIMEOUT)
            if response.status_code == 200:
                return [m["name"] for m in response.json().get("models", [])]
        except requests.RequestException:
            pass
        return []

    def is_ollama_available(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = requests.get(f"{OLLAMA_API}/api/tags", timeout=OLLAMA_CHECK_TIMEOUT)
            return response.status_code == 200
        except requests.RequestException:
            return False

    def ask(
        self,
        question: str,
        module_name: str = "default",
        system_prompt: str = None,
        model_override: str = None,
        max_tokens: int = 1500,
        temperature: float = 0.7,
        stream: bool = False
    ) -> Optional[str]:
        """
        Send question to Ollama using module-specific model.

        Args:
            question: The user's question
            module_name: Module name for model selection
            system_prompt: Optional system prompt override
            model_override: Force specific model (ignores config)
            max_tokens: Max response tokens
            temperature: Creativity (0.0-1.0)
            stream: Whether to stream response (not implemented yet)

        Returns:
            Model response text, or None on error
        """
        # Select model
        model = model_override or self.get_model_for_module(module_name)

        # Build messages
        messages = []

        # Add system prompt if provided
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        # Add conversation history for this module
        if module_name in self._messages:
            messages.extend(self._messages[module_name][-6:])  # Keep last 3 exchanges

        # Add current question
        messages.append({"role": "user", "content": question})

        # API request
        payload = {
            "model": model,
            "messages": messages,
            "stream": stream,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        try:
            response = requests.post(
                f"{OLLAMA_API}/v1/chat/completions",
                json=payload,
                timeout=OLLAMA_COMPLETION_TIMEOUT
            )

            if response.status_code == 200:
                data = response.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "")

                # Save to history
                if module_name not in self._messages:
                    self._messages[module_name] = []
                self._messages[module_name].append({"role": "user", "content": question})
                self._messages[module_name].append({"role": "assistant", "content": content})

                # Trim history (configurable via MODEL_MANAGER_HISTORY_MAX)
                try:
                    from config import MODEL_MANAGER_HISTORY_MAX
                except ImportError:
                    MODEL_MANAGER_HISTORY_MAX = 12
                if len(self._messages[module_name]) > MODEL_MANAGER_HISTORY_MAX:
                    self._messages[module_name] = self._messages[module_name][-MODEL_MANAGER_HISTORY_MAX:]

                return content
            else:
                print(f"[ModelManager] API error: {response.status_code}")
                return None

        except requests.ConnectionError:
            print("[ModelManager] Ollama not running")
            return None
        except requests.Timeout:
            print("[ModelManager] Ollama timeout")
            return None
        except Exception as e:
            print(f"[ModelManager] Error: {e}")
            return None

    def clear_history(self, module_name: str = None):
        """Clear conversation history for a module or all modules."""
        if module_name:
            self._messages.pop(module_name, None)
        else:
            self._messages.clear()

    def get_history(self, module_name: str) -> List[dict]:
        """Get conversation history for a module."""
        return self._messages.get(module_name, [])


# Singleton instance
_manager: Optional[ModelManager] = None


def get_model_manager() -> ModelManager:
    """Get the global ModelManager instance."""
    global _manager
    if _manager is None:
        _manager = ModelManager()
    return _manager
