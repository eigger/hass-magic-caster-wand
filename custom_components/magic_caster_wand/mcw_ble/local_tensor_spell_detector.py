import numpy as np
import tensorflow as tf

from .spell_detector import SpellDetector
from .spells import ALL_SPELLS

class LocalTensorSpellDetector(SpellDetector):
    """Spell detector implementation using TensorFlow Lite for local inference."""

    def __init__(self, model_path: str):
        """
        Initialize the TensorFlow Lite interpreter.

        Args:
            model_path: Path to the TFLite model file.
        """
        self._interpreter = tf.lite.Interpreter(model_path=model_path)
        self._interpreter.allocate_tensors()

    async def detect(self, positions: np.ndarray, confidence_threshold: np.float32) -> str | None:
        """
        Detect a spell from normalized position data using TensorFlow Lite.

        Args:
            positions: A (50, 2) float32 array of normalized positions in [0, 1] range.
            confidence_threshold: Minimum confidence required for a valid detection.

        Returns:
            The detected spell name as a string, or None if no spell recognized
            with sufficient confidence.
        """
        # Get input tensor and copy data
        input_tensor = self._interpreter.get_input_details()[0]
        self._interpreter.set_tensor(input_tensor['index'], positions.reshape(1, 50, 2))

        # Run inference
        self._interpreter.invoke()

        # Get output probabilities
        output_tensor = self._interpreter.get_output_details()[0]
        probabilities = self._interpreter.get_tensor(output_tensor['index'])[0]

        # Find best match (highest probability)
        best_index = np.argmax(probabilities)
        best_prob = probabilities[best_index]

        if best_prob < confidence_threshold:
            return None

        return ALL_SPELLS[best_index].Name
