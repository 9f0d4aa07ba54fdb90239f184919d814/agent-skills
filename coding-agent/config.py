"""
Agent configuration.
Reads from environment variables or .env file.
"""

import os, json
from pathlib import Path


CONFIG_FILE = Path.home() / ".coding-agent" / "config.json"


class Config:
    def __init__(self):
        self._data = self._load()

    def _load(self) -> dict:
        config = {
            "provider": os.getenv("LLM_PROVIDER", "opencode"),
            "model": os.getenv("LLM_MODEL", ""),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
            "max_iterations": int(os.getenv("MAX_ITERATIONS", "5")),
            "workdir": os.getenv("WORK_DIR", "."),
        }
        if CONFIG_FILE.exists():
            try:
                file_config = json.loads(CONFIG_FILE.read_text())
                config.update(file_config)
            except:
                pass
        return config

    def save(self):
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str, default=None):
        return self._data.get(key, default)

    def set(self, key: str, value):
        self._data[key] = value
        self.save()

    @property
    def provider(self) -> str:
        return self._data.get("provider", "opencode")

    @property
    def model(self) -> str:
        return self._data.get("model", "")

    @property
    def api_key(self) -> str:
        return self._data.get("api_key", "")

    @property
    def temperature(self) -> float:
        return float(self._data.get("temperature", 0.2))

    @property
    def max_iterations(self) -> int:
        return int(self._data.get("max_iterations", 5))

    @property
    def workdir(self) -> str:
        return self._data.get("workdir", ".")
