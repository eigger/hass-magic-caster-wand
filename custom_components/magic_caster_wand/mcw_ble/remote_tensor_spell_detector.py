import hashlib
import json
import logging
import numpy as np
import requests

from pathlib import Path
from typing import Any, Optional

from .spell_detector import SpellDetector

_LOGGER = logging.getLogger(__name__)

class RemoteTensorSpellDetector(SpellDetector):
    """Spell detector that delegates inference to a remote TensorFlow Lite server."""

    def __init__(
        self,
        model_path: str | Path,
        base_url: str,
        timeout: float = 5.0,
    ) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._timeout: float = timeout

        self._model_path: Path = Path(model_path) if model_path else Path(__file__).with_name("model.tflite")
        self._model_name: str = self._model_path.name

        if not self._model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self._model_path}")

        self._session: requests.Session = requests.Session()
        self._upload_model()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def detect(self, positions: np.ndarray, confidence_threshold: np.float32) -> str | None:
        """Detect a spell by invoking the remote TFLite server.

        Args:
            positions: A (50, 2) float32 array of normalized positions in [0, 1].
            confidence_threshold: Minimum confidence required for a valid detection.
        """

        try:
            payload = {
                "model": self._model_name,
                # Add batch dimension like local interpreter: (1, 50, 2)
                "input": positions.reshape(1, 50, 2).tolist(),
            }
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.error("Failed to prepare payload: %s", exc)
            return None

        outputs = self._invoke(payload)
        if not outputs:
            return None

        probs = outputs[0].get("data") if isinstance(outputs, list) and len(outputs) else None
        if probs is None:
            return None

        # Flatten potential batch dim
        if isinstance(probs, list) and len(probs) > 0 and isinstance(probs[0], list):
            probs = probs[0]

        try:
            probabilities = np.array(probs, dtype=np.float32)
            best_index = int(np.argmax(probabilities))
            best_prob = float(probabilities[best_index])
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.warning("Invalid probabilities from remote server: %s", exc)
            return None

        if best_prob < float(confidence_threshold):
            return None

        return self.SPELL_NAMES[best_index]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _upload_model(self) -> None:
        url = f"{self._base_url}/models/{self._model_name}"
        data = self._model_path.read_bytes()
        headers = {"Content-Type": "application/octet-stream"}
        resp = self._session.put(url, data=data, headers=headers, timeout=self._timeout)
        resp.raise_for_status()

    def _invoke(self, payload: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        url = f"{self._base_url}/invoke"
        try:
            resp = self._session.post(url, json=payload, timeout=self._timeout)
            resp.raise_for_status()
            body = resp.json()

            outputs = body.get("outputs") if isinstance(body, dict) else None
            return outputs if isinstance(outputs, list) else None
        except Exception as exc:
            _LOGGER.warning("Remote invoke failed: %s", exc)
            return None