import logging
import numpy as np
from typing import Optional
from pathlib import Path

from .spell_detector import SpellDetector
from .gesture_io import GestureIO

_LOGGER = logging.getLogger(__name__)

class ShapeSpellDetector(SpellDetector):
    """
    Spell detector that uses template matching (Dollar Q / Nearest Neighbor variant)
    to recognize shapes and spells. 
    Integrates logic previously in UnifiedShapeDetector.
    """

    def __init__(self, model_path: Optional[str | Path] = None) -> None:
        """
        Args:
            model_path: Path to .json/.npz file or None for built-in memory Core.
        """
        self._model_path = str(model_path) if model_path else None
        
        # Load templates via GestureIO
        self.templates = GestureIO.load(self._model_path)
        self._ensure_template_quality()
        
        _LOGGER.debug("ShapeSpellDetector initialized with %d templates (Source: %s)", len(self.templates), self._model_path)
        self._is_active = False

    def _ensure_template_quality(self):
        """Resample all templates to 50 points."""
        for k, v in self.templates.items():
            if len(v) > 0:
                self.templates[k] = self._resample(v, 50)

    def _resample(self, points, n=50):
        """Resample a point path to exactly n equidistant points."""
        path_length = sum(np.linalg.norm(points[i+1] - points[i]) for i in range(len(points)-1))
        I = path_length / (n - 1)
        if I == 0: return points
        
        new_points = [points[0]]
        D = 0.0
        src_pts = list([pt for pt in points])
        
        i = 1
        while i < len(src_pts):
            pt1 = src_pts[i-1]
            pt2 = src_pts[i]
            d = np.linalg.norm(pt2 - pt1)
            
            if D + d >= I:
                qx = pt1[0] + ((I - D) / d) * (pt2[0] - pt1[0])
                qy = pt1[1] + ((I - D) / d) * (pt2[1] - pt1[1])
                q = np.array([qx, qy])
                new_points.append(q)
                src_pts.insert(i, q) 
                D = 0.0
            else:
                D += d
            i += 1
            
        while len(new_points) < n:
            new_points.append(src_pts[-1])
        return np.array(new_points[:n])

    def _normalize(self, points):
        """Scale points to [0,1] bounding box."""
        min_vals = np.min(points, axis=0)
        max_vals = np.max(points, axis=0)
        size = np.maximum(max_vals - min_vals, 1e-5)
        return (points - min_vals) / size

    def predict_shape(self, positions):
        """
        Internal synchronous prediction.
        Returns: (best_label, score)
        """
        points = np.array(positions)
        if len(points) < 10: return "Too Short", 0.0
        points = self._resample(points, 50)
        points = self._normalize(points)

        best_score = -float('inf')
        best_label = "Unknown"

        for label, template in self.templates.items():
            if len(template) != 50: continue
            dist = np.mean(np.linalg.norm(points - template, axis=1))
            score = 1.0 - dist
            if score > best_score:
                best_score = score
                best_label = label
        
        return best_label, max(0.0, best_score)

    # ------------------------------------------------------------------
    # SpellDetector Interface Implementation
    # ------------------------------------------------------------------

    @property
    def is_active(self) -> bool:
        """Check if the detector is active."""
        return self._is_active

    async def async_init(self) -> None:
        """Initialize the detector asynchronously."""
        self._is_active = True
        _LOGGER.debug("ShapeSpellDetector activated")

    async def close(self) -> None:
        """Close the detector."""
        self._is_active = False
        _LOGGER.debug("ShapeSpellDetector deactivated")

    async def check_connectivity(self) -> bool:
        """Check if the detector is operational."""
        return True

    async def detect(self, positions: np.ndarray, confidence_threshold: np.float32) -> str | None:
        """
        Detect a spell/shape from normalized position data.
        
        Args:
            positions: A (50, 2) float32 array of normalized positions in [0, 1] range.
            confidence_threshold: Minimum confidence required for a valid detection.
            
        Returns:
            The detected shape name as a string, or None if no shape was recognized
            with sufficient confidence.
        """
        # Run prediction
        label, score = self.predict_shape(positions)
        
        if score < confidence_threshold:
            _LOGGER.debug("Shape detected '%s' with score %.4f < threshold %.2f", label, score, confidence_threshold)
            return None
            
        _LOGGER.debug("Shape detected '%s' with score %.4f", label, score)
        return label
