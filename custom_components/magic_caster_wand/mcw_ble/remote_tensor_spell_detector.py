import logging
import asyncio
import numpy as np
import aiohttp

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
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self._base_url: str = base_url.rstrip("/")
        self._timeout: float = timeout
        self._session: Optional[aiohttp.ClientSession] = session
        self._is_external_session: bool = session is not None

        self._model_path: Path = Path(model_path) if model_path else Path(__file__).with_name("model.tflite")
        self._model_name: str = self._model_path.name

        if not self._model_path.exists():
            raise FileNotFoundError(f"Model file not found: {self._model_path}")

        self._model_uploaded: bool = False

    @property
    def is_active(self) -> bool:
        """Check if the session is active."""
        return self._session is not None and not self._session.closed

    async def async_init(self) -> None:
        """Initialize the detector asynchronously."""
        if self._session is None:
            self._session = aiohttp.ClientSession()
        
        await self._upload_model()

    async def close(self) -> None:
        """Close the session if it was created internally."""
        if not self._is_external_session and self._session:
            await self._session.close()
            self._session = None

    async def check_connectivity(self) -> bool:
        """Check if the remote server is reachable.
        
        Returns:
            True if reachable, False otherwise.
        """
        temp_session = False
        if self._session is None:
            self._session = aiohttp.ClientSession()
            temp_session = True
        
        try:
            # Use the /health endpoint for a more reliable check
            url = f"{self._base_url}/health"
            async with self._session.get(url, timeout=2.0) as resp:
                # 200 OK means the server is fully operational
                return resp.status == 200
        except Exception as exc:
            _LOGGER.debug("Health check failed for %s: %s", self._base_url, exc)
            return False
        finally:
            if temp_session:
                await self._session.close()
                self._session = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    async def detect(self, positions: np.ndarray, confidence_threshold: np.float32) -> str | None:
        """Detect a spell by invoking the remote TFLite server.

        Args:
            positions: A (50, 2) float32 array of normalized positions in [0, 1].
            confidence_threshold: Minimum confidence required for a valid detection.
        """
        _LOGGER.debug("Remote detect called with %d positions, threshold: %.2f", len(positions), confidence_threshold)
        
        # Ensure session is initialized
        if self._session is None:
            self._session = aiohttp.ClientSession()

        # Ensure model is uploaded
        if not self._model_uploaded:
            try:
                await self._upload_model()
            except Exception as exc:
                _LOGGER.error("Failed to upload model before detection: %s", exc)
                return None

        try:
            payload = {
                "model": self._model_name,
                # Add batch dimension like local interpreter: (1, 50, 2)
                "input": positions.reshape(1, 50, 2).tolist(),
            }
        except Exception as exc:  # pragma: no cover - defensive
            _LOGGER.error("Failed to prepare payload: %s", exc)
            return None

        outputs = await self._invoke(payload)
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

    async def _upload_model(self) -> None:
        if self._model_uploaded:
            _LOGGER.debug("Model %s already uploaded, skipping", self._model_name)
            return

        url = f"{self._base_url}/models/{self._model_name}"
        # Use to_thread to avoid blocking the event loop with file I/O
        data = await asyncio.to_thread(self._model_path.read_bytes)
        headers = {"Content-Type": "application/octet-stream"}
        
        _LOGGER.debug("Uploading model to %s (%d bytes)", url, len(data))
        async with self._session.put(url, data=data, headers=headers, timeout=self._timeout) as resp:
            resp.raise_for_status()
            self._model_uploaded = True
            _LOGGER.info("Model %s uploaded successfully to %s", self._model_name, self._base_url)

    async def _invoke(self, payload: dict[str, Any]) -> Optional[list[dict[str, Any]]]:
        url = f"{self._base_url}/invoke"
        try:
            _LOGGER.debug("Sending remote invoke request to %s: %s", url, payload)
            async with self._session.post(url, json=payload, timeout=self._timeout) as resp:
                resp.raise_for_status()
                body = await resp.json()
                _LOGGER.debug("Received remote invoke response: %s", body)

                outputs = body.get("outputs") if isinstance(body, dict) else None
                return outputs if isinstance(outputs, list) else None
        except Exception as exc:
            _LOGGER.warning("Remote invoke failed: %s", exc)
            return None