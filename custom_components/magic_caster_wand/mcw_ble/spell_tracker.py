import numpy as np
import tensorflow as tf

from dataclasses import dataclass, field

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
class SpellTrackerState:
    ahrs_quat_q0: np.float32 = 1.0
    ahrs_quat_q1: np.float32 = 0.0
    ahrs_quat_q2: np.float32 = 0.0
    ahrs_quat_q3: np.float32 = 0.0
    position_count: int = 0
    initial_yaw: np.float32 = 0.0
    tracking_active: int = 0
    positions: np.ndarray = field(default_factory=lambda: np.zeros((8192, 2), dtype=np.float32))
    start_pos_z: np.float32 = -294.0
    start_quat_q0: np.float32 = 0.0
    inv_quat_q0: np.float32 = 0.0
    ref_vec_x: np.float32 = 0.0
    ref_vec_y: np.float32 = 0.0
    ref_vec_z: np.float32 = 0.0
    start_quat_q1: np.float32 = 0.0
    start_quat_q2: np.float32 = 0.0
    start_quat_q3: np.float32 = 0.0
    inv_quat_q1: np.float32 = 0.0
    inv_quat_q2: np.float32 = 0.0
    inv_quat_q3: np.float32 = 0.0

@dataclass
class SpellTracker:
    _CONST_NEG_2_0 = np.float32(-2.0)
    _CONST_NEG_1_0 = np.float32(-1.0)
    _CONST_NEG_0_5 = np.float32(-0.5)
    _CONST_NEG_0_0 = np.float32(-0.0)

    _CONST_0_0 = np.float32(0.0)
    _CONST_0_5 = np.float32(0.5)
    _CONST_0_99 = np.float32(0.99)
    _CONST_1_0 = np.float32(1.0)
    _CONST_1_5 = np.float32(1.5)
    _CONST_2_0 = np.float32(2.0)

    _CONST_GRAVITY = np.float32(9.8100004196167)
    _CONST_MILLIMETERMOVETHRESHOLD = np.float32(8.0)
    _CONST_PI = np.float32(np.pi)

    _interpreter: tf.lite.Interpreter = field(default_factory=lambda: SpellTracker._create_interpeter(), repr=False)
    _state: SpellTrackerState = field(default_factory=lambda: SpellTrackerState())

    @staticmethod
    def _create_interpeter() -> tf.lite.Interpreter:
        interpreter = tf.lite.Interpreter(model_path="model.tflite")
        interpreter.allocate_tensors()
        return interpreter

    @staticmethod
    def _inv_sqrt(x: np.float32) -> np.float32:
        if not np.isfinite(x) or x <= SpellTracker._CONST_0_0:
            return SpellTracker._CONST_0_0
        x2 = SpellTracker._CONST_0_5 * x
        # use ndarray view to avoid scalar .view limitations
        y = np.array([x], dtype=np.float32)
        i = y.view(np.uint32)
        i[:] = np.uint32(0x5f3759df) - (i >> 1)
        y = i.view(np.float32)
        y = y * (SpellTracker._CONST_1_5 - (x2 * y * y))
        return np.float32(y[0])

    @staticmethod
    def _wrap_to_2pi(angle: np.float32) -> np.float32:
        return angle if angle >= 0.0 else angle + SpellTracker._CONST_2_0 * SpellTracker._CONST_PI

    def start(
        self
    ) -> None:
        self._state.position_count = 0

        roll, pitch, yaw = self._calc_eulers_from_attitude()
        self._state.initial_yaw = yaw

        half_roll: np.float32 = roll * SpellTracker._CONST_0_5
        dStack_c: np.float32 = np.float32(np.sin(half_roll))
        dStack_14: np.float32 = np.float32(np.cos(half_roll))

        half_pitch: np.float32 = pitch * SpellTracker._CONST_0_5
        dStack_1c: np.float32 = np.float32(np.sin(half_pitch))
        dStack_24: np.float32 = np.float32(np.cos(half_pitch))

        self._state.start_quat_q0 = np.float32(dStack_c * dStack_1c * SpellTracker._CONST_0_0 + dStack_14 * dStack_24)
        self._state.start_quat_q1 = np.float32(dStack_c * dStack_24 - dStack_14 * dStack_1c * SpellTracker._CONST_0_0)
        self._state.start_quat_q2 = np.float32(dStack_c * dStack_24 * SpellTracker._CONST_0_0 + dStack_14 * dStack_1c)
        self._state.start_quat_q3 = np.float32(dStack_14 * dStack_24 * SpellTracker._CONST_0_0 - dStack_c * dStack_1c)

        fVar4: np.float32 = SpellTracker._CONST_NEG_1_0 / (self._state.start_quat_q3 * self._state.start_quat_q3 + self._state.start_quat_q2 * self._state.start_quat_q2 + self._state.start_quat_q1 * self._state.start_quat_q1 + self._state.start_quat_q0 * self._state.start_quat_q0)
        fVar1: np.float32 = fVar4*self._state.start_quat_q0
        self._state.inv_quat_q1 = fVar4*self._state.start_quat_q1
        fVar2: np.float32 = fVar1 * SpellTracker._CONST_NEG_0_0
        fVar7: np.float32 = self._state.inv_quat_q1 * SpellTracker._CONST_0_0
        self._state.inv_quat_q2 = fVar4*self._state.start_quat_q2
        self._state.inv_quat_q3 = fVar4*self._state.start_quat_q3
        fVar8: np.float32 = self._state.inv_quat_q2 * SpellTracker._CONST_0_0
        fVar4: np.float32 = self._state.inv_quat_q3 * SpellTracker._CONST_0_0

        fVar5: np.float32 = ((fVar7 - self._state.start_pos_z * fVar1) - fVar8) - fVar4
        fVar3: np.float32 = ((fVar2 - self._state.start_pos_z * self._state.inv_quat_q1) - fVar8) - fVar4
        fVar9: np.float32 = ((fVar8 + fVar2) - self._state.start_pos_z * self._state.inv_quat_q3) + fVar7
        fVar7: np.float32 = (self._state.start_pos_z * self._state.inv_quat_q2 + fVar4 + fVar2) - fVar7

        fVar8: np.float32 = (fVar7 * self._state.start_quat_q2 + fVar3 * self._state.start_quat_q1 + fVar5 * self._state.start_quat_q0) - fVar9 * self._state.start_quat_q3
        fVar4: np.float32 = fVar5 * self._state.start_quat_q3 + ((fVar3 * self._state.start_quat_q2 + fVar9 * self._state.start_quat_q0) - fVar7 * self._state.start_quat_q1)
        fVar10: np.float32 = (fVar9 * self._state.start_quat_q1 + fVar3 * self._state.start_quat_q3 + fVar7 * self._state.start_quat_q0) - fVar5 * self._state.start_quat_q2

        fVar6: np.float32 = SpellTracker._CONST_NEG_1_0 / (self._state.inv_quat_q3 * self._state.inv_quat_q3 + self._state.inv_quat_q2 * self._state.inv_quat_q2 + self._state.inv_quat_q1 * self._state.inv_quat_q1 + fVar1 * fVar1)
        self._state.inv_quat_q0 = -fVar1
        fVar2: np.float32 = -fVar1*fVar6
        fVar5: np.float32 = self._state.inv_quat_q1*fVar6
        fVar11: np.float32 = self._state.inv_quat_q2*fVar6
        fVar6: np.float32 = self._state.inv_quat_q3*fVar6
        fVar7: np.float32 = ((fVar2 * SpellTracker._CONST_NEG_0_0 - fVar5 * fVar8) - fVar11 * fVar4) - fVar6 * fVar10
        fVar9: np.float32 = (fVar6 * fVar4 + (fVar5 * SpellTracker._CONST_0_0 - fVar8 * fVar2)) - fVar11 * fVar10
        fVar3: np.float32 = fVar5 * fVar10 + ((fVar11 * SpellTracker._CONST_0_0 - fVar4 * fVar2) - fVar6 * fVar8)
        fVar4: np.float32 = (fVar11 * fVar8 + (fVar6 * SpellTracker._CONST_0_0 - fVar2 * fVar10)) - fVar5 * fVar4

        self._state.ref_vec_x = (self._state.inv_quat_q2 * fVar4 + (self._state.inv_quat_q1 * fVar7 - fVar9 * fVar1)) - self._state.inv_quat_q3 * fVar3
        self._state.ref_vec_y = (self._state.inv_quat_q3 * fVar9 + ((self._state.inv_quat_q2 * fVar7 - fVar3 * fVar1) - self._state.inv_quat_q1 * fVar4))
        self._state.ref_vec_z = ((fVar3 * self._state.inv_quat_q1 + (fVar7 * self._state.inv_quat_q3 - fVar4 * fVar1)) - fVar9 * self._state.inv_quat_q2)

        self._state.positions[0] = np.float32(0.0), np.float32(0.0)
        self._state.position_count = 1
        self._state.tracking_active = 1

    def stop(
        self
    ) -> str | None:
        self._state.tracking_active = 0
        result = self._recognize_spell()
        return result if isinstance(result, str) else None

    def update(
        self,
        ax: np.float32,
        ay: np.float32,
        az: np.float32,
        gx: np.float32,
        gy: np.float32,
        gz: np.float32
    ) -> tuple[np.float32, np.float32] | None:

        self._update_imu_only(
            gx,
            gy,
            gz,
            ax * SpellTracker._CONST_GRAVITY,
            ay * SpellTracker._CONST_GRAVITY,
            az * SpellTracker._CONST_GRAVITY,
            np.float32(0.0042735))

        if self._state.tracking_active != 1:
            return None

        roll, pitch, yaw = self._calc_eulers_from_attitude()

        fVar1: np.float32 = yaw - self._state.initial_yaw

        half_roll: np.float32 = roll * SpellTracker._CONST_0_5
        dStack_24: np.float32 = np.sin(half_roll)
        dStack_2c: np.float32 = np.cos(half_roll)

        half_pitch: np.float32 = pitch * SpellTracker._CONST_0_5
        dStack_14: np.float32 = np.sin(half_pitch)
        dStack_1c: np.float32 = np.cos(half_pitch)
        
        half_yaw: np.float32 = fVar1 * SpellTracker._CONST_0_5
        dStack_34: np.float32 = np.sin(half_yaw)
        dStack_3c: np.float32 = np.cos(half_yaw)

        fVar9: np.float32 = dStack_34 * dStack_24 * dStack_14 + dStack_3c * dStack_2c * dStack_1c
        fVar5: np.float32 = dStack_3c * dStack_24 * dStack_1c - dStack_34 * dStack_2c * dStack_14
        fVar11: np.float32 = dStack_24 * dStack_1c * dStack_34 +  dStack_2c * dStack_14 * dStack_3c
        fVar3: np.float32 = dStack_2c * dStack_1c * dStack_34 - dStack_24 * dStack_14 * dStack_3c

        fVar7: np.float32 = SpellTracker._CONST_NEG_1_0 / (fVar3 * fVar3 + fVar11 * fVar11 + fVar5 * fVar5 + fVar9 * fVar9)
        fVar2: np.float32 = fVar7 * fVar9 * SpellTracker._CONST_NEG_0_0
        fVar10: np.float32 = fVar7 * fVar5 * SpellTracker._CONST_0_0
        fVar6: np.float32 = fVar7 * fVar11 * SpellTracker._CONST_0_0
        fVar8: np.float32 = fVar7 * fVar3 * SpellTracker._CONST_0_0

        fVar4: np.float32 =((fVar10 - self._state.start_pos_z * fVar7 * fVar9) + fVar8) - fVar6
        fVar1: np.float32 = ((fVar2 - self._state.start_pos_z * fVar7 * fVar5) - fVar6) - fVar8
        fVar6: np.float32 = ((fVar6 + fVar2) - self._state.start_pos_z * fVar7 * fVar3) + fVar10
        fVar10: np.float32 = (fVar7 * fVar11 * self._state.start_pos_z + fVar8 + fVar2) - fVar10
        fVar7: np.float32 = (fVar10 * fVar11 + fVar1 * fVar5 + fVar4 * fVar9) - fVar6 * fVar3
        fVar2: np.float32 = fVar4 * fVar3 + ((fVar1 * fVar11 + fVar6 * fVar9) - fVar10 * fVar5)
        fVar4: np.float32 = (fVar6 * fVar5 + fVar1 * fVar3 + fVar10 * fVar9) - fVar4 * fVar11

        fVar6: np.float32 = SpellTracker._CONST_NEG_1_0 / (self._state.inv_quat_q3 * self._state.inv_quat_q3 + self._state.inv_quat_q2 * self._state.inv_quat_q2 + self._state.inv_quat_q1 * self._state.inv_quat_q1 + self._state.inv_quat_q0 * self._state.inv_quat_q0)
        fVar8: np.float32 = self._state.inv_quat_q0 * fVar6
        fVar5: np.float32 = self._state.inv_quat_q1 * fVar6
        fVar3: np.float32 = self._state.inv_quat_q2 * fVar6
        fVar6: np.float32 = fVar6 * self._state.inv_quat_q3

        fVar11: np.float32 = ((fVar8 * SpellTracker._CONST_NEG_0_0 - fVar5 * fVar7) - fVar3 * fVar2) - fVar6 * fVar4
        fVar1: np.float32 = (fVar6 * fVar2 + (fVar5 * SpellTracker._CONST_0_0 - fVar7 * fVar8)) - fVar3 * fVar4
        fVar12: np.float32 = fVar5 * fVar4 + ((fVar3 * SpellTracker._CONST_0_0 - fVar2 * fVar8) - fVar6 * fVar7)
        fVar2: np.float32 = (fVar3 * fVar7 + (fVar6 * SpellTracker._CONST_0_0 - fVar8 * fVar4)) - fVar5 * fVar2

        fVar9: np.float32 = SpellTracker._CONST_NEG_1_0 / (self._state.start_quat_q3 * self._state.start_quat_q3 + self._state.start_quat_q2 * self._state.start_quat_q2 + self._state.start_quat_q1 * self._state.start_quat_q1 + self._state.start_quat_q0 * self._state.start_quat_q0)
        fVar3: np.float32 = ((self._state.inv_quat_q2 * fVar2 + self._state.inv_quat_q1 * fVar11 + self._state.inv_quat_q0 * fVar1) - self._state.inv_quat_q3 * fVar12) - self._state.ref_vec_x
        fVar7: np.float32 = self._state.start_quat_q0 * fVar9
        fVar10: np.float32 = self._state.start_quat_q1 * fVar9

        fVar4: np.float32 = (self._state.inv_quat_q3 * fVar1 + ((self._state.inv_quat_q2 * fVar11 + self._state.inv_quat_q0 * fVar12) - self._state.inv_quat_q1 * fVar2)) - self._state.ref_vec_y
        fVar8: np.float32 = self._state.start_quat_q2 * fVar9
        fVar5: np.float32 = ((fVar12 * self._state.inv_quat_q1 + fVar11 * self._state.inv_quat_q3 + fVar2 * self._state.inv_quat_q0) - fVar1 * self._state.inv_quat_q2) - self._state.ref_vec_z
        fVar9: np.float32 = fVar9 * self._state.start_quat_q3

        fVar2: np.float32 = ((fVar7 * SpellTracker._CONST_NEG_0_0 - fVar10 * fVar3) - fVar8 * fVar4) - fVar9 * fVar5
        fVar1: np.float32 = (fVar9 * fVar4 + (fVar10 * SpellTracker._CONST_0_0 - fVar3 * fVar7)) - fVar8 * fVar5
        fVar6: np.float32 = fVar10 * fVar5 + ((fVar8 * SpellTracker._CONST_0_0 - fVar4 * fVar7) - fVar9 * fVar3)
        fVar4: np.float32 = (fVar8 * fVar3 + (fVar9 * SpellTracker._CONST_0_0 - fVar7 * fVar5)) - fVar10 * fVar4

        fVar3: np.float32 = self._state.start_quat_q3 * fVar1 + ((self._state.start_quat_q2 * fVar2 + self._state.start_quat_q0 * fVar6) - self._state.start_quat_q1 * fVar4)
        fVar1: np.float32 = (fVar6 * self._state.start_quat_q1 + fVar2 * self._state.start_quat_q3 + fVar4 * self._state.start_quat_q0) - fVar1 * self._state.start_quat_q2

        if self._state.position_count < 0x2000:
            self._state.positions[self._state.position_count] = (fVar3, fVar1)
            self._state.position_count += 1

        return (fVar3,fVar1)

    def _calc_eulers_from_attitude(
        self
    ) -> tuple[np.float32, np.float32, np.float32]:
        qw: np.float32 = self._state.ahrs_quat_q0
        qx: np.float32 = self._state.ahrs_quat_q1
        qy: np.float32 = self._state.ahrs_quat_q2
        qz: np.float32 = self._state.ahrs_quat_q3

        # Calculate roll
        sinroll_cospitch: np.float32 = SpellTracker._CONST_2_0 * (qy*qz + qw*qx)
        cosroll_cospitch: np.float32 = SpellTracker._CONST_1_0 - SpellTracker._CONST_2_0 * (qx * qx + qy * qy)
        roll: np.float32 = np.float32(np.arctan2(sinroll_cospitch, cosroll_cospitch))

        # Calculate pitch
        gimbal_test: np.float32 = qw * qz + qx * qy
        if gimbal_test != SpellTracker._CONST_0_5 or np.isnan(gimbal_test):
            if gimbal_test != SpellTracker._CONST_NEG_0_5 or np.isnan(gimbal_test):
                sinpitch: np.float32 = SpellTracker._CONST_2_0 * (qw * qy - qz * qx)
                sinpitch_clamped: np.float32 = np.clip(sinpitch, SpellTracker._CONST_NEG_1_0, SpellTracker._CONST_1_0)
                pitch: np.float32 = np.float32(np.arcsin(sinpitch_clamped))
            else:
                pitch: np.float32 = SpellTracker._CONST_NEG_2_0 * np.float32(np.arctan2(qx, qw))
        else:
            pitch: np.float32 = SpellTracker._CONST_2_0 * np.float32(np.arctan2(qx, qw))

        # Calculate yaw
        sinyaw_cospitch: np.float32 = SpellTracker._CONST_2_0 * (qw * qz + qx * qy)
        cosyaw_cospitch: np.float32 = SpellTracker._CONST_1_0 - SpellTracker._CONST_2_0 * (qy * qy + qz * qz)
        yaw: np.float32 = np.float32(np.arctan2(sinyaw_cospitch, cosyaw_cospitch))

        return self._wrap_to_2pi(roll), pitch, self._wrap_to_2pi(yaw)

    def _update_imu_only(
        self,
        gx: np.float32,
        gy: np.float32,
        gz: np.float32,
        ax: np.float32,
        ay: np.float32,
        az: np.float32,
        dt: np.float32
    ) -> None:
        if ax != SpellTracker._CONST_0_0 or np.isnan(ax) or ay != SpellTracker._CONST_0_0 or np.isnan(ay) or az != SpellTracker._CONST_0_0 or np.isnan(az):
            fVar2: np.float32 = az * az + ay * ay + ax * ax
            fVar1: np.float32 = self._inv_sqrt(fVar2)
            fVar3: np.float32 = self._state.ahrs_quat_q1 * self._state.ahrs_quat_q3 - self._state.ahrs_quat_q0 * self._state.ahrs_quat_q2
            fVar2: np.float32 = self._state.ahrs_quat_q3 * self._state.ahrs_quat_q2 + self._state.ahrs_quat_q1 * self._state.ahrs_quat_q0
            fVar4: np.float32 = self._state.ahrs_quat_q3 * self._state.ahrs_quat_q3 + self._state.ahrs_quat_q0 * self._state.ahrs_quat_q0 + SpellTracker._CONST_NEG_0_5
            gx: np.float32 = gx + (ay * fVar1 * fVar4 - fVar1 * az * fVar2)
            gy: np.float32 = gy + (fVar1 * az * fVar3 - fVar4 * ax * fVar1)
            gz: np.float32 = gz + (fVar2 * ax * fVar1 - fVar3 * ay * fVar1)

        fVar1: np.float32 = dt * SpellTracker._CONST_0_5
        fVar6: np.float32 = gx * fVar1
        fVar4: np.float32 = gy * fVar1
        fVar1: np.float32 = fVar1 * gz

        fVar3 = ((-(fVar6 * self._state.ahrs_quat_q1) - fVar4 * self._state.ahrs_quat_q2) - fVar1 * self._state.ahrs_quat_q3) + self._state.ahrs_quat_q0
        fVar2 = ((fVar1 * self._state.ahrs_quat_q2 + self._state.ahrs_quat_q0 * fVar6) - fVar4 * self._state.ahrs_quat_q3) + self._state.ahrs_quat_q1
        fVar5 = fVar6 * self._state.ahrs_quat_q3 + (fVar4 * self._state.ahrs_quat_q0 - fVar1 * self._state.ahrs_quat_q1) + self._state.ahrs_quat_q2
        fVar4 = ((fVar4 * self._state.ahrs_quat_q1 + fVar1 * self._state.ahrs_quat_q0) - fVar6 * self._state.ahrs_quat_q2) + self._state.ahrs_quat_q3
        fVar6 = fVar4 * fVar4 + fVar5 * fVar5 + fVar2 * fVar2 + fVar3 * fVar3
        fVar1 = self._inv_sqrt(fVar6)

        self._state.ahrs_quat_q0 = fVar3 * fVar1
        self._state.ahrs_quat_q1 = fVar2 * fVar1
        self._state.ahrs_quat_q2 = fVar5 * fVar1
        self._state.ahrs_quat_q3 = fVar1 * fVar4

    def _recognize_spell(
        self,
        confidence_threshold: np.float32 = _CONST_0_99
    ) -> str | int:
        """
        Recognize a spell/gesture from recorded positions.
        
        Returns:
            Tuple of (recognized_class_index, probabilities_array)
            - Returns (-1, None) if no movement detected
            - Returns (-2, None) if not enough data points (need > 99)
        """
        positions: np.ndarray = self._state.positions
        position_count: int = self._state.position_count
        
        # Phase 1: Calculate bounding box (min/max X and Y)
        min_x: np.float32 = np.float32(np.inf)
        max_x: np.float32 = np.float32(-np.inf)
        min_y: np.float32 = np.float32(np.inf)
        max_y: np.float32 = np.float32(-np.inf)
        
        for i in range(position_count):
            x: np.float32 = positions[i, 0]
            y: np.float32 = positions[i, 1]
            if x < min_x:
                min_x: np.float32 = x
            if x > max_x:
                max_x: np.float32 = x
            if y < min_y:
                min_y: np.float32 = y
            if y > max_y:
                max_y: np.float32 = y
        
        # Compute bounding box size (larger of width or height)
        width: np.float32 = max_x - min_x
        height: np.float32 = max_y - min_y
        bbox_size: np.float32 = np.maximum(width, height)
        
        # Phase 2: Early exit checks
        if bbox_size <= SpellTracker._CONST_0_0:
            return -1  # No movement detected
        
        if position_count <= 99:
            return -2  # Not enough data points
        
        # Phase 3: Trim stationary tail (end of gesture)
        threshold_sq = SpellTracker._CONST_MILLIMETERMOVETHRESHOLD * SpellTracker._CONST_MILLIMETERMOVETHRESHOLD
        end_index = position_count
        
        if threshold_sq > SpellTracker._CONST_0_0:
            while end_index >= 121:  # 0x79 = 121
                # Compare points 40 apart from the end
                curr_idx = end_index - 1
                prev_idx = curr_idx - 40
                
                dx = positions[curr_idx, 0] - positions[prev_idx, 0]
                dy = positions[curr_idx, 1] - positions[prev_idx, 1]
                dist_sq = dx * dx + dy * dy
                
                if dist_sq >= threshold_sq:
                    break
                    
                end_index -= 10
        
        # Phase 4: Trim stationary head (start of gesture)
        start_index = 0
        
        if threshold_sq > SpellTracker._CONST_0_0 and end_index > 120:
            while start_index < end_index - 120:  # Keep at least 120 points
                # Compare points 10 apart from the start
                curr_idx = start_index
                next_idx = curr_idx + 10
                
                dx = positions[next_idx, 0] - positions[curr_idx, 0]
                dy = positions[next_idx, 1] - positions[curr_idx, 1]
                dist_sq = dx * dx + dy * dy
                
                if dist_sq >= threshold_sq:
                    break
                    
                start_index += 10
        
        # Adjust indices for resampling
        start_float = np.float32(start_index + 1)
        trimmed_count = end_index - start_index
        
        # Phase 5: Resample to 50 normalized points (100 floats)
        pos_inputs = np.zeros((50, 2), dtype=np.float32)
        step = np.float32(trimmed_count) / np.float32(50.0)
        
        sample_pos = start_float
        for i in range(50):
            idx = int(sample_pos)

            # Clamp index to valid range
            if idx >= position_count:
                idx = position_count - 1
            if idx < 0:
                idx = 0
                
            # Normalize to [0, 1] based on bounding box
            pos_inputs[i, 0] = (positions[idx, 0] - min_x) / bbox_size
            pos_inputs[i, 1] = (positions[idx, 1] - min_y) / bbox_size
            
            sample_pos += step
        
        # Phase 6: TensorFlow Lite inference (if interpreter provided)
        # Get input tensor and copy data
        input_tensor = self._interpreter.get_input_details()[0]
        self._interpreter.set_tensor(input_tensor['index'], pos_inputs.reshape(1, 50, 2))
        
        # Run inference
        self._interpreter.invoke()
        
        # Get output probabilities
        output_tensor = self._interpreter.get_output_details()[0]
        probabilities = self._interpreter.get_tensor(output_tensor['index'])[0]
        
        # Phase 7: Find best match (highest probability)
        best_index = np.argmax(probabilities)
        best_prob = probabilities[best_index]

        if best_prob < confidence_threshold:
            return -3  # No spell recognized with sufficient confidence

        print(f"Recognized spell: {SPELL_NAMES[best_index]} with probability {best_prob:.4f}")
        return SPELL_NAMES[best_index]
