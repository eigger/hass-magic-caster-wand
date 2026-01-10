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
    """Tracks the spell gesture using IMU data."""

    _IMU_TIME_DELTA = 0.0042735  # Hz - IMU sample rate

    _ahrs: Madgwick = field(default_factory=lambda: Madgwick(frequency=1/SpellTracker._IMU_TIME_DELTA))
    _points: List[Tuple[float, float]] = field(default_factory=lambda: [(0.0, 0.0)] * 8192)
    _points_length: int = field(default=0)
    _quaternion: np.ndarray = field(default_factory=lambda: np.array([1.0, 0.0, 0.0, 0.0]))
    _reference_quaternion: np.ndarray | None = field(default=None)

    def _quaternion_inverse(self, q: np.ndarray) -> np.ndarray:
        """Compute the inverse (conjugate) of a unit quaternion."""
        # For unit quaternions, inverse = conjugate = [w, -x, -y, -z]
        return np.array([q[0], -q[1], -q[2], -q[3]])

    def _quaternion_multiply(self, q1: np.ndarray, q2: np.ndarray) -> np.ndarray:
        """Multiply two quaternions: q1 * q2."""
        w1, x1, y1, z1 = q1
        w2, x2, y2, z2 = q2
        return np.array([
            w1*w2 - x1*x2 - y1*y2 - z1*z2,
            w1*x2 + x1*w2 + y1*z2 - z1*y2,
            w1*y2 - x1*z2 + y1*w2 + z1*x2,
            w1*z2 + x1*y2 - y1*x2 + z1*w2
        ])

    def update(
            self: Self,
            accel_x: float,
            accel_y: float,
            accel_z: float,
            gyro_x: float,
            gyro_y: float,
            gyro_z: float) -> Point:
        """Update tracking with new IMU data."""

        # Create numpy arrays for AHRS processing
        accel = np.array([accel_x, accel_y, accel_z])
        gyro = np.array([gyro_x, gyro_y, gyro_z])

        # Update AHRS filter with IMU data
        # This produces a quaternion representing the current orientation
        self._quaternion = self._ahrs.updateIMU(self._quaternion, gyr=gyro, acc=accel)

        # On first update, capture reference orientation
        if self._reference_quaternion is None:
            self._reference_quaternion = self._quaternion.copy()

        # Compute relative quaternion: q_relative = q_ref_inverse * q_current
        # This gives us the rotation FROM the reference orientation TO the current orientation
        q_ref_inv = self._quaternion_inverse(self._reference_quaternion)
        q_relative = self._quaternion_multiply(q_ref_inv, self._quaternion)

        # Project the quaternion to 2D point
        point: Point = self._quaternion_to_point(q_relative)

        # Scale to screen coordinates
        adjPoint = Point(
            x=point.x * 1000.0,
            y=point.y * 1000.0,
        )
        
        self._points[self._points_length] = adjPoint
        self._points_length += 1
        return adjPoint

    def _rotate_vector_by_quaternion(self, q: np.ndarray, v: np.ndarray) -> np.ndarray:
        """Rotate a 3D vector by a quaternion using q * v * q_inverse."""
        w, x, y, z = q
        vx, vy, vz = v
        
        # Optimized quaternion-vector rotation
        # t = 2 * cross(q.xyz, v)
        tx = 2.0 * (y * vz - z * vy)
        ty = 2.0 * (z * vx - x * vz)
        tz = 2.0 * (x * vy - y * vx)
        
        # result = v + w * t + cross(q.xyz, t)
        return np.array([
            vx + w * tx + (y * tz - z * ty),
            vy + w * ty + (z * tx - x * tz),
            vz + w * tz + (x * ty - y * tx)
        ])

    def _quaternion_to_point(self, q) -> Point:
        """Convert relative quaternion to screen coordinates.
        
        Roll-invariant approach: track where the wand tip points in space.
        
        IMU coordinate frame (wand held horizontally, pointing forward):
        - X axis: points DOWN (gravity is -1g on X when horizontal)
        - Y axis: points FORWARD (wand tip direction) - roll axis
        - Z axis: points RIGHT
        
        We rotate a forward vector by the relative quaternion, then extract:
        - Azimuth (X/Z plane angle) -> Screen Y (left/right)
        - Elevation (angle from horizontal) -> Screen X (up/down)
        """
        # Forward vector = wand tip direction in local frame (Y axis)
        forward = np.array([0.0, 1.0, 0.0])
        
        # Rotate by relative quaternion to get current pointing direction
        pointing = self._rotate_vector_by_quaternion(q, forward)
        
        # Azimuth: angle in horizontal plane (Z-Y plane since X is vertical)
        # atan2(Z, Y) gives left/right angle
        azimuth = np.arctan2(pointing[2], pointing[1])
        
        # Elevation: angle from horizontal plane
        # X is vertical (down), so -X is up
        horizontal_dist = np.sqrt(pointing[1]**2 + pointing[2]**2)
        elevation = np.arctan2(-pointing[0], horizontal_dist)
        
        return Point(x=-elevation, y=-azimuth)