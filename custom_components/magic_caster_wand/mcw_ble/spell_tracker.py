"""Turn a stream of wand IMU samples into a 2D gesture and recognize it.

The pipeline has three stages:

1. Orientation: a Mahony complementary filter fuses the gyroscope (angular
   rate) with the accelerometer (gravity direction) into a unit quaternion
   describing how the wand is held.
2. Projection: the wand is modelled as a rigid stick of fixed length pointing
   along its body X axis. While a gesture is being recorded, the tip of that
   stick is projected onto the vertical plane facing the heading the wand had
   when recording began, giving one 2D point (in millimetres) per sample.
3. Recognition: when recording stops, idle stretches at the start and end of
   the stroke are dropped, the rest is resampled to a fixed number of points
   evenly spaced in time, scaled into the unit square and handed to the
   configured :class:`SpellDetector`.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import numpy as np

from .spell_detector import SpellDetector

_LOGGER = logging.getLogger(__name__)

# ── IMU input ────────────────────────────────────────────────────────────────

#: The wand streams IMU samples at this rate; the filter integrates at 1/rate.
IMU_SAMPLE_RATE_HZ = 234.0
IMU_SAMPLE_PERIOD_S = 1.0 / IMU_SAMPLE_RATE_HZ

#: Accelerometer samples arrive in units of g; they are converted to m/s^2.
STANDARD_GRAVITY_MS2 = 9.81

# ── Orientation filter ───────────────────────────────────────────────────────

#: Proportional gain of the Mahony filter: how strongly the measured gravity
#: direction pulls the gyro-integrated attitude back into line. No integral
#: (gyro bias) term is used.
MAHONY_PROPORTIONAL_GAIN = 0.5

# ── Gesture projection ───────────────────────────────────────────────────────

#: Distance from the pivot (the hand) to the wand tip, in millimetres. All
#: recorded gesture points are tip displacements in this unit.
WAND_LENGTH_MM = 294.0

#: Upper bound on the number of points kept for a single gesture (~35 s).
MAX_GESTURE_POINTS = 8192

# ── Recognition pre-processing ───────────────────────────────────────────────

#: A recording needs at least this many points to be worth recognizing.
MIN_GESTURE_POINTS = 100

#: Trimming never shortens the stroke below this many points.
MIN_POINTS_AFTER_TRIM = 120

#: The tip counts as resting while it moves less than this over a window.
IDLE_MOVEMENT_MM = 8.0

#: Idle stretches are removed in chunks of this many samples.
TRIM_CHUNK_POINTS = 10

#: Window used to decide whether the end of the stroke is at rest. It is wider
#: than the chunk size so a slow finishing flourish is not cut off.
TRAILING_IDLE_WINDOW_POINTS = 40

#: Number of points the detector expects.
DETECTOR_INPUT_POINTS = 50

#: Minimum detector confidence for a spell to be reported.
DEFAULT_CONFIDENCE_THRESHOLD = 0.99


# ── Quaternion helpers (w, x, y, z order, unit quaternions) ──────────────────

Quaternion = tuple[float, float, float, float]

_IDENTITY: Quaternion = (1.0, 0.0, 0.0, 0.0)


def _quat_multiply(a: Quaternion, b: Quaternion) -> Quaternion:
    """Return the Hamilton product ``a * b``."""
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (
        aw * bw - ax * bx - ay * by - az * bz,
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
    )


def _heading_of(q: Quaternion) -> float:
    """Return the rotation about the world vertical (Z) axis, in radians."""
    w, x, y, z = q
    return math.atan2(2.0 * (w * z + x * y), 1.0 - 2.0 * (y * y + z * z))


def _rotation_about_vertical(angle: float) -> Quaternion:
    """Return the quaternion for a rotation of ``angle`` radians about world Z."""
    half = 0.5 * angle
    return (math.cos(half), 0.0, 0.0, math.sin(half))


def _wand_tip_lateral(q: Quaternion) -> tuple[float, float]:
    """Return the world Y and Z coordinates of the wand tip for attitude ``q``.

    The wand points along its body X axis, so the tip is the first column of
    the rotation matrix scaled by the wand length. The X (depth) component is
    not needed for the projection and is not computed.
    """
    w, x, y, z = q
    tip_y = 2.0 * (x * y + w * z) * WAND_LENGTH_MM
    tip_z = 2.0 * (x * z - w * y) * WAND_LENGTH_MM
    return tip_y, tip_z


class MahonyFilter:
    """Attitude estimator fusing gyroscope and accelerometer readings.

    Each step rotates the current attitude by the measured angular rate. Before
    integrating, the rate is nudged by the cross product between the measured
    gravity direction and the gravity direction predicted by the current
    attitude, which slowly removes roll and pitch drift. Heading (yaw) is not
    observable without a magnetometer and is left to the gyroscope alone.
    """

    def __init__(self, proportional_gain: float = MAHONY_PROPORTIONAL_GAIN) -> None:
        self.proportional_gain = proportional_gain
        self.attitude: Quaternion = _IDENTITY

    def step(
        self,
        gyro: tuple[float, float, float],
        accel: tuple[float, float, float],
        dt: float,
    ) -> Quaternion:
        """Advance the filter by ``dt`` seconds and return the new attitude.

        ``gyro`` is in rad/s; ``accel`` may be in any unit since only its
        direction is used. An all-zero or invalid accelerometer reading skips
        the gravity correction for this step.
        """
        w, x, y, z = self.attitude
        rate_x, rate_y, rate_z = gyro
        acc_x, acc_y, acc_z = accel

        acc_norm = math.sqrt(acc_x * acc_x + acc_y * acc_y + acc_z * acc_z)
        if acc_norm > 0.0 and math.isfinite(acc_norm):
            acc_x, acc_y, acc_z = acc_x / acc_norm, acc_y / acc_norm, acc_z / acc_norm

            # World "up" expressed in the sensor frame (last row of the
            # body-to-world rotation matrix).
            up_x = 2.0 * (x * z - w * y)
            up_y = 2.0 * (w * x + y * z)
            up_z = w * w - x * x - y * y + z * z

            # Misalignment between measured and predicted gravity.
            gain = self.proportional_gain
            rate_x += gain * (acc_y * up_z - acc_z * up_y)
            rate_y += gain * (acc_z * up_x - acc_x * up_z)
            rate_z += gain * (acc_x * up_y - acc_y * up_x)

        # First-order integration of dq/dt = 0.5 * q * (0, rate).
        half_dt = 0.5 * dt
        new_w = w + half_dt * (-x * rate_x - y * rate_y - z * rate_z)
        new_x = x + half_dt * (w * rate_x + y * rate_z - z * rate_y)
        new_y = y + half_dt * (w * rate_y - x * rate_z + z * rate_x)
        new_z = z + half_dt * (w * rate_z + x * rate_y - y * rate_x)

        norm = math.sqrt(new_w * new_w + new_x * new_x + new_y * new_y + new_z * new_z)
        if norm > 0.0 and math.isfinite(norm):
            self.attitude = (new_w / norm, new_x / norm, new_y / norm, new_z / norm)
        else:
            _LOGGER.debug("Orientation filter diverged; resetting attitude")
            self.attitude = _IDENTITY
        return self.attitude


@dataclass
class SpellTrackerState:
    """Mutable state of a :class:`SpellTracker`."""

    orientation: MahonyFilter = field(default_factory=MahonyFilter)
    tracking_active: bool = False
    #: Rotation that cancels the heading the wand had when recording began.
    heading_offset: Quaternion = _IDENTITY
    #: Tip position (world Y, Z) when recording began, in millimetres.
    start_tip: tuple[float, float] = (0.0, 0.0)
    points: np.ndarray = field(default_factory=lambda: np.zeros((MAX_GESTURE_POINTS, 2), dtype=np.float32))
    position_count: int = 0

    # Attitude components, exposed for diagnostics and tests.
    @property
    def ahrs_quat_q0(self) -> float:
        return self.orientation.attitude[0]

    @property
    def ahrs_quat_q1(self) -> float:
        return self.orientation.attitude[1]

    @property
    def ahrs_quat_q2(self) -> float:
        return self.orientation.attitude[2]

    @property
    def ahrs_quat_q3(self) -> float:
        return self.orientation.attitude[3]


class SpellTracker:
    """Record wand gestures from IMU samples and recognize them as spells."""

    def __init__(self, detector: SpellDetector | None):
        self._detector: SpellDetector | None = detector
        self._state = SpellTrackerState()

    # ── Lifecycle ────────────────────────────────────────────────────────────

    def start(self) -> None:
        """Begin recording a new gesture from the wand's current pose.

        The current heading becomes "straight ahead" and the current tip
        position becomes the origin of the drawing plane.
        """
        state = self._state
        attitude = state.orientation.attitude
        state.heading_offset = _rotation_about_vertical(-_heading_of(attitude))
        state.start_tip = _wand_tip_lateral(_quat_multiply(state.heading_offset, attitude))

        state.points[0] = (0.0, 0.0)
        state.position_count = 1
        state.tracking_active = True

    async def stop(self) -> str | None:
        """Finish recording and return the recognized spell name, if any."""
        self._state.tracking_active = False
        return await self._recognize_spell()

    def abort(self) -> None:
        """Discard an in-flight recording without attempting recognition.

        Used when a cast is interrupted rather than completed -- a disconnect
        mid-gesture -- so the partial sample run cannot be carried into the next one.
        """
        self._state.tracking_active = False
        self._state.position_count = 0

    async def close(self) -> None:
        """Close the underlying detector."""
        if hasattr(self._detector, "close"):
            await self._detector.close()

    @property
    def is_active(self) -> bool:
        """Check if the underlying detector is active."""
        return getattr(self._detector, "is_active", False)

    @property
    def detector(self) -> SpellDetector | None:
        """Return the underlying detector."""
        return self._detector

    # ── Per-sample processing ────────────────────────────────────────────────

    def update(
        self,
        ax: float,
        ay: float,
        az: float,
        gx: float,
        gy: float,
        gz: float,
        *,
        calculate_position: bool = True,
    ) -> tuple[float, float] | None:
        """Feed one IMU sample (accel in g, gyro in rad/s).

        The orientation filter always advances. While recording, and when
        ``calculate_position`` is true, the wand tip is projected onto the
        drawing plane; the point is stored and returned as ``(x, y)`` in
        millimetres relative to where recording began, with x growing to the
        right and y growing downward (screen convention). Otherwise ``None``
        is returned.
        """
        state = self._state
        attitude = state.orientation.step(
            (float(gx), float(gy), float(gz)),
            (
                float(ax) * STANDARD_GRAVITY_MS2,
                float(ay) * STANDARD_GRAVITY_MS2,
                float(az) * STANDARD_GRAVITY_MS2,
            ),
            IMU_SAMPLE_PERIOD_S,
        )

        if not state.tracking_active or not calculate_position:
            return None

        tip_y, tip_z = _wand_tip_lateral(_quat_multiply(state.heading_offset, attitude))
        start_y, start_z = state.start_tip
        # World +Y is to the user's left and +Z is up; flip both for screen axes.
        point = (start_y - tip_y, start_z - tip_z)

        if state.position_count < MAX_GESTURE_POINTS:
            state.points[state.position_count] = point
            state.position_count += 1

        return point

    # ── Recognition ──────────────────────────────────────────────────────────

    async def _recognize_spell(self, confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD) -> str | None:
        """Prepare the recorded gesture and ask the detector to classify it."""
        count = self._state.position_count
        _LOGGER.debug("Spell recognition started with %d positions", count)

        if self._detector is None:
            _LOGGER.debug("Spell recognition skipped: no detector configured")
            return None

        features = build_detector_input(self._state.points[:count])
        if features is None:
            return None

        spell_name = await self._detector.detect(features, np.float32(confidence_threshold))
        if spell_name is None:
            _LOGGER.debug("Spell recognition failed: no spell recognized with sufficient confidence")
        return spell_name


def _is_idle(points: np.ndarray, first: int, second: int) -> bool:
    """Return whether the tip moved less than the idle threshold between two samples."""
    dx, dy = points[second] - points[first]
    return dx * dx + dy * dy < IDLE_MOVEMENT_MM * IDLE_MOVEMENT_MM


def trim_idle_ends(points: np.ndarray) -> tuple[int, int]:
    """Return ``(start, end)`` bounds of the stroke with resting ends removed.

    The end is pulled back one chunk at a time while the tip barely moved over
    the trailing window; the start is then pushed forward one chunk at a time
    while the tip barely moved over the next chunk. Neither step ever leaves
    fewer than :data:`MIN_POINTS_AFTER_TRIM` points.
    """
    start, end = 0, len(points)

    while end > MIN_POINTS_AFTER_TRIM and _is_idle(points, end - 1 - TRAILING_IDLE_WINDOW_POINTS, end - 1):
        end -= TRIM_CHUNK_POINTS

    while end - start > MIN_POINTS_AFTER_TRIM and _is_idle(points, start, start + TRIM_CHUNK_POINTS):
        start += TRIM_CHUNK_POINTS

    return start, end


def resample_uniform(points: np.ndarray, count: int) -> np.ndarray:
    """Resample a polyline to ``count`` points evenly spaced in time.

    Samples arrive at a fixed rate, so time is proportional to sample index.
    The stroke is split into ``count`` equal time slices and the position at
    the start of each slice is taken, linearly interpolating between samples.
    """
    source_index = np.arange(len(points), dtype=np.float64)
    target_index = np.arange(count, dtype=np.float64) * (len(points) / count)
    resampled = np.empty((count, 2), dtype=np.float32)
    resampled[:, 0] = np.interp(target_index, source_index, points[:, 0])
    resampled[:, 1] = np.interp(target_index, source_index, points[:, 1])
    return resampled


def build_detector_input(points: np.ndarray) -> np.ndarray | None:
    """Convert a recorded gesture into the detector's ``(50, 2)`` input.

    Coordinates are shifted so the recording's bounding box starts at the
    origin and divided by the longer side of that box, so the shape keeps its
    aspect ratio and fits in ``[0, 1]``. Returns ``None`` (after logging why)
    when the recording cannot be recognized.
    """
    if len(points) == 0:
        _LOGGER.debug("Spell recognition failed: no movement detected")
        return None

    lower = points.min(axis=0)
    extent = float((points.max(axis=0) - lower).max())
    if not extent > 0.0:
        _LOGGER.debug("Spell recognition failed: no movement detected")
        return None

    if len(points) < MIN_GESTURE_POINTS:
        _LOGGER.debug("Spell recognition failed: not enough data points (%d)", len(points))
        return None

    start, end = trim_idle_ends(points)
    stroke = resample_uniform(points[start:end], DETECTOR_INPUT_POINTS)
    return ((stroke - lower) / extent).astype(np.float32)
