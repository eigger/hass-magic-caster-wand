import numpy as np
from ahrs.filters import Madgwick
from dataclasses import dataclass, field
from typing import List, Self, Tuple

@dataclass
class Point:
    x: float
    y: float

@dataclass
class SpellTracker:
    _IMU_TIME_DELTA = 0.0042735  # seconds - IMU sample period (~234 Hz)
    _SHAFT_AXIS = np.array([1.0, 0.0, 0.0])  # Sensor +X points along the wand shaft (toward the tip)
    _PLANE_SCALE = 250.0  # Pixels per radian-ish of angular change (tune for gesture size)
    _SMOOTH_ALPHA = 0.15  # Low-pass smoothing factor for screen motion
    _GRAV_ALPHA = 0.02    # Low-pass for gravity estimate to keep plane orientation stable
    _GRAV_MIN_G = 0.8     # Accept accel magnitude in [0.8g, 1.2g] as gravity
    _GRAV_MAX_G = 1.2

    # State
    _filter: Madgwick = field(default_factory=lambda: Madgwick(frequency=1.0 / SpellTracker._IMU_TIME_DELTA), repr=False)
    _grav_est: np.ndarray | None = field(default=None, repr=False)
    _plane_x: np.ndarray | None = field(default=None, repr=False)
    _plane_y: np.ndarray | None = field(default=None, repr=False)
    _quat: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0], dtype=float), repr=False)
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
            gyro_z: float) -> Point:
        """Update pose and return 2D projection of wand tip movement.

        The wand is modeled as pointing along the IMU's +X axis. We track the
        tip direction (forward vector) and project its change onto a plane
        perpendicular to the initial forward direction. Rolling about the
        shaft does not affect the projection because only the forward vector
        is considered.
        """

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

        return Point(float(self._smoothed[0]), float(self._smoothed[1]))

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