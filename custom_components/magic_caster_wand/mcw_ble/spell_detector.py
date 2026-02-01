import numpy as np

from abc import ABC, abstractmethod

class SpellDetector(ABC):
    """Base class for spell detection from normalized position data."""

    @abstractmethod
    async def detect(self, positions: np.ndarray, confidence_threshold: np.float32) -> str | None:
        """
        Detect a spell from normalized position data.

        Args:
            positions: A (50, 2) float32 array of normalized positions in [0, 1] range.
            confidence_threshold: Minimum confidence required for a valid detection.

        Returns:
            The detected spell name as a string, or None if no spell was recognized
            with sufficient confidence.
        """
        pass
