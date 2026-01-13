import json
import numpy as np
import tensorflow as tf
from ahrs.filters import Madgwick
from collections import namedtuple
from dataclasses import dataclass, field
from typing import List, Self, Tuple

Point = namedtuple('Point', ['x', 'y'])

SPELL_NAMES = [
    "The_Force_Spell",
    "Colloportus",
    "Colloshoo",
    "The_Hour_Reversal_Reversal_Charm",
    "Evanesco",
    "Herbivicus",
    "Orchideous",
    "Brachiabindo",
    "Meteolojinx",
    "Riddikulus",
    "Silencio",
    "Immobulus",
    "Confringo",
    "Petrificus_Totalus",
    "Flipendo",
    "The_Cheering_Charm",
    "Salvio_Hexia",
    "Pestis_Incendium",
    "Alohomora",
    "Protego",
    "Langlock",
    "Mucus_Ad_Nauseum",
    "Flagrate",
    "Glacius",
    "Finite",
    "Anteoculatia",
    "Expelliarmus",
    "Expecto_Patronum",
    "Descendo",
    "Depulso",
    "Reducto",
    "Colovaria",
    "Aberto",
    "Confundo",
    "Densaugeo",
    "The_Stretching_Jinx",
    "Entomorphis",
    "The_Hair_Thickening_Growing_Charm",
    "Bombarda",
    "Finestra",
    "The_Sleeping_Charm",
    "Rictusempra",
    "Piertotum_Locomotor",
    "Expulso",
    "Impedimenta",
    "Ascendio",
    "Incarcerous",
    "Ventus",
    "Revelio",
    "Accio",
    "Melefors",
    "Scourgify",
    "Wingardium_Leviosa",
    "Nox",
    "Stupefy",
    "Spongify",
    "Lumos",
    "Appare_Vestigium",
    "Verdimillious",
    "Fulgari",
    "Reparo",
    "Locomotor",
    "Quietus",
    "Everte_Statum",
    "Incendio",
    "Aguamenti",
    "Sonorus",
    "Cantis",
    "Arania_Exumai",
    "Calvorio",
    "The_Hour_Reversal_Charm",
    "Vermillious",
    "The_Pepper-Breath_Hex",
]

@dataclass
class SpellTracker:
    _IMU_TIME_DELTA = 0.0042735  # seconds - IMU sample period (~234 Hz)
    _MAX_POINTS = 8192    # Max points to buffer for a spell gesture
    _PLANE_SCALE = 250.0  # Pixels per radian-ish of angular change (tune for gesture size)
    _GRAV_ALPHA = 0.02    # Low-pass for gravity estimate to keep plane orientation stable
    _GRAV_MAX_G = 1.2
    _GRAV_MIN_G = 0.8     # Accept accel magnitude in [0.8g, 1.2g] as gravity
    _SHAFT_AXIS = np.array([1.0, 0.0, 0.0])  # Sensor +X points along the wand shaft (toward the tip)
    _SMOOTH_ALPHA = 0.15  # Low-pass smoothing factor for screen motion

    # State
    _filter: Madgwick = field(default_factory=lambda: Madgwick(frequency=1.0 / SpellTracker._IMU_TIME_DELTA), repr=False)
    _grav_est: np.ndarray | None = field(default=None, repr=False)
    _interpreter: tf.lite.Interpreter = field(default_factory=lambda: SpellTracker._create_interpeter(), repr=False)
    _plane_x: np.ndarray | None = field(default=None, repr=False)
    _plane_y: np.ndarray | None = field(default=None, repr=False)
    _points: np.ndarray = field(default_factory=lambda: np.zeros((SpellTracker._MAX_POINTS, 2), dtype=np.float32), repr=False)
    _points_count: int = field(default=0, repr=False)
    _quat: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0], dtype=float), repr=False)
    _active: bool = field(default=False, repr=False)
    _ref_forward: np.ndarray | None = field(default=None, repr=False)
    _ref_up: np.ndarray | None = field(default=None, repr=False)
    _smoothed: np.ndarray = field(default_factory=lambda: np.zeros(2), repr=False)

    def update(
            self: Self,
            accel_x: float,
            accel_y: float,
            accel_z: float,
            gyro_x: float,
            gyro_y: float,
            gyro_z: float) -> Point | None:
        """Update pose and return 2D projection of wand tip movement.

        The wand is modeled as pointing along the IMU's +X axis. We track the
        tip direction (forward vector) and project its change onto a plane
        perpendicular to the initial forward direction. Rolling about the
        shaft does not affect the projection because only the forward vector
        is considered.

        Returns None if the tracker is not active.
        """
        if not self._active:
            return None

        # Normalize accelerometer to reduce the effect of magnitude drift; the
        # Madgwick implementation internally handles normalization, but keeping
        # inputs reasonable helps stability when the wand is moving fast.
        accel = np.array([accel_x, accel_y, accel_z], dtype=float)
        gyro = np.array([gyro_x, gyro_y, gyro_z], dtype=float)

        # Update orientation estimate.
        self._quat = self._filter.updateIMU(q=self._quat, gyr=gyro, acc=accel)

        # Current forward vector of the wand in world frame.
        forward = self._rotate_vector(self._quat, self._SHAFT_AXIS)

        # On first sample, establish reference plane perpendicular to the
        # initial forward vector. This keeps the projection independent of how
        # the user initially holds the wand.
        if self._ref_forward is None:
            self._ref_forward = forward / np.linalg.norm(forward)
            # Use gravity (from accel) to anchor screen "up" so the plane has a
            # consistent world tilt; this removes arbitrary rotation drift.
            accel_norm = accel / np.linalg.norm(accel)
            self._ref_up = -accel_norm  # gravity points opposite measured accel
            self._grav_est = self._ref_up.copy()
            self._plane_x, self._plane_y = self._build_plane_axes(self._ref_forward, self._ref_up)
            return Point(0.0, 0.0)

        # Update gravity estimate slowly when accel magnitude is close to 1g
        a_mag = np.linalg.norm(accel)
        if self._GRAV_MIN_G <= a_mag <= self._GRAV_MAX_G:
            grav_meas = -accel / a_mag
            self._grav_est = (1.0 - self._GRAV_ALPHA) * self._grav_est + self._GRAV_ALPHA * grav_meas
            self._grav_est /= np.linalg.norm(self._grav_est)

        # Rebuild plane axes each frame using the latest gravity estimate to
        # prevent slow rotation drift of the projection plane.
        self._plane_x, self._plane_y = self._build_plane_axes(self._ref_forward, self._grav_est)

        # Compute deviation of forward vector from the initial forward, then
        # project it onto the plane basis. This is roll-invariant because the
        # projection uses only the forward direction, not the wand's roll.
        forward_norm = forward / np.linalg.norm(forward)

        # Delta from the initial forward; projects small angular changes, which
        # tends to keep horizontal sweeps flatter than using absolute comps.
        delta = forward_norm - self._ref_forward

        raw_point = np.array([
            float(np.dot(delta, self._plane_x)),
            float(np.dot(delta, self._plane_y)),
        ]) * self._PLANE_SCALE

        # Smooth the output a bit to reduce jitter from gyro bias/noise
        self._smoothed = (1.0 - self._SMOOTH_ALPHA) * self._smoothed + self._SMOOTH_ALPHA * raw_point

        point = Point(float(self._smoothed[0]), float(self._smoothed[1]))

        # Accumulate point if active and under the limit
        if self._active and self._points_count < self._MAX_POINTS:
            self._points[self._points_count, 0] = point.x
            self._points[self._points_count, 1] = point.y
            self._points_count += 1

        return point

    def start(self: Self) -> None:
        """Reset state and start accumulating points for a new spell."""
        self._filter = Madgwick(frequency=1.0 / self._IMU_TIME_DELTA)
        self._grav_est = None
        self._plane_x = None
        self._plane_y = None
        self._points_count = 0
        self._quat = np.array([1.0, 0.0, 0.0, 0.0], dtype=float)
        self._ref_forward = None
        self._ref_up = None
        self._smoothed = np.zeros(2)
        self._active = True

    def stop(self: Self) -> str | None:
        """Stop accumulating points and write them to a JSON file.
        
        Returns the recognized spell name, or None if no spell was recognized.
        """
        self._active = False
        return self._recognize_spell()

    @staticmethod
    def _build_plane_axes(forward: np.ndarray, up: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
        """Create orthonormal X/Y axes perpendicular to forward, anchored to gravity."""
        # Ensure up is not parallel to forward
        if abs(np.dot(up, forward)) > 0.9:
            # fall back to an arbitrary up to avoid degeneracy
            up = np.array([0.0, 0.0, 1.0]) if abs(forward[2]) < 0.9 else np.array([0.0, 1.0, 0.0])

        # X axis: right, from up x forward (keeps x horizontal relative to gravity)
        plane_x = np.cross(up, forward)
        plane_x /= np.linalg.norm(plane_x)

        # Y axis: up in the plane, orthogonal to forward and plane_x
        plane_y = np.cross(forward, plane_x)
        plane_y /= np.linalg.norm(plane_y)
        return plane_x, plane_y

    @staticmethod
    def _create_interpeter() -> tf.lite.Interpreter:
        interpreter = tf.lite.Interpreter(model_path="c:\\temp\\tensor\\model.tflite")
        interpreter.allocate_tensors()
        return interpreter

    @staticmethod
    def _rotate_vector(q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Rotate vector v by quaternion q (w, x, y, z)."""
        w, x, y, z = q
        # Rotation matrix from quaternion
        r00 = 1 - 2 * (y * y + z * z)
        r01 = 2 * (x * y - z * w)
        r02 = 2 * (x * z + y * w)
        r10 = 2 * (x * y + z * w)
        r11 = 1 - 2 * (x * x + z * z)
        r12 = 2 * (y * z - x * w)
        r20 = 2 * (x * z - y * w)
        r21 = 2 * (y * z + x * w)
        r22 = 1 - 2 * (x * x + y * y)
        rot = np.array([[r00, r01, r02], [r10, r11, r12], [r20, r21, r22]])
        return rot @ v
    
    def _recognize_spell(self: Self) -> str | None:
        points = self._points[:self._points_count]
        min_x = np.min(points[:, 0])
        max_x = np.max(points[:, 0])
        min_y = np.min(points[:, 1])
        max_y = np.max(points[:, 1])

        range_x = max_x - min_x
        range_y = max_y - min_y
        range_val = max(range_x, range_y)

        stride = float(self._points_count) / float(50)

        downsampled_points = np.zeros((50, 2), dtype=np.float32)
        position = 0.0

        for i in range(50):
            sample_idx = int(position)
            if sample_idx >= self._points_count:
                sample_idx = self._points_count - 1
            
            x = self._points[sample_idx, 0]
            y = self._points[sample_idx, 1]
            
            # Normalize to [0, 1] with aspect-ratio preservation
            downsampled_points[i, 0] = (x - min_x) / range_val
            downsampled_points[i, 1] = (y - min_y) / range_val
            
            position += stride

        input_data = downsampled_points.reshape(1, 50, 2)
        self._interpreter.set_tensor(0, input_data)
        self._interpreter.invoke()

        spells = self._interpreter.get_tensor(14)
        predicted_index = np.argmax(spells)
        confidence = spells[0][predicted_index]

        if confidence >= 0.9:
            return SPELL_NAMES[predicted_index]

        return None
