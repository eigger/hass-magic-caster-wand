import struct
from enum import IntEnum
from dataclasses import dataclass
from typing import Union, Optional

# ==========================================
# 1. 상수 정의 (Enums)
# ==========================================

class OpcodeTX(IntEnum):
    """앱 -> 지팡이 전송 명령 (Channel 1)"""
    REQ_FIRMWARE       = 0x00
    REQ_BATTERY        = 0x01 # Keep-Alive
    REQ_BOX_ADDRESS    = 0x09
    REQ_FACTORY_UNLOCK = 0x0B
    REQ_PRODUCT_INFO   = 0x0D
    CMD_IMU_START      = 0x30
    CMD_IMU_STOP       = 0x31
    CMD_LIGHT_CLEAR    = 0x40
    CMD_VIBRATE        = 0x50
    CMD_MACRO_FLUSH    = 0x60
    CMD_MACRO_EXEC     = 0x68
    CMD_PREDEFINED     = 0x69
    CMD_SET_THRESHOLD  = 0x70
    CMD_READ_THRESHOLD = 0xDD
    CMD_CALIBRATE      = 0xFC

class OpcodeRX(IntEnum):
    """지팡이 -> 앱 응답 (Channel 1)"""
    RESP_BOX_ADDRESS    = 0x0A
    RESP_PRODUCT_INFO   = 0x0E
    RESP_THRESHOLD      = 0xDE
    # 펌웨어 버전은 Opcode 없이 문자열로 옴

class OpcodeStream(IntEnum):
    """지팡이 -> 앱 스트림 데이터 (Channel 2)"""
    # React 코드 분석 결과에 따른 Opcode
    BUTTON_EVENT = 0x11
    SPELL_EVENT  = 0x24  # 제스처/주문 인식
    # IMU 데이터는 별도 Opcode 없이 헤더로 구분되거나 0x80 등으로 시작

class ProductInfoType(IntEnum):
    SERIAL_NUMBER = 0x01
    SKU           = 0x02
    MFG_ID        = 0x03
    DEVICE_ID     = 0x04
    EDITION       = 0x05
    DECO          = 0x06
    COMPANION_MAC = 0x08
    WAND_TYPE     = 0x09

class WandModel(Enum):
    """지팡이 모델 (캐릭터) 매핑"""
    HARRY_POTTER     = 0x00
    HERMIONE_GRANGER = 0x01
    RON_WEASLEY      = 0x02
    DUMBLEDORE       = 0x03
    NEWT_SCAMANDER   = 0x04
    WISE_UNKNOWN     = 0x05
    UNKNOWN          = 0xFF

@dataclass
class EventButton:
    mask: int
    is_big_pressed: bool    # 0x01
    is_top_pressed: bool    # 0x02
    is_mid_pressed: bool    # 0x04
    is_bot_pressed: bool    # 0x08
    
    def __repr__(self):
        pressed = []
        if self.is_big_pressed: pressed.append("BIG")
        if self.is_top_pressed: pressed.append("TOP")
        if self.is_mid_pressed: pressed.append("MID")
        if self.is_bot_pressed: pressed.append("BOT")
        return f"<EventButton: {', '.join(pressed) if pressed else 'RELEASED'}>"

@dataclass
class EventSpell:
    name: str
    raw_bytes: bytes
    
    def __repr__(self):
        return f"<EventSpell: ✨ {self.name} ✨>"

@dataclass
class EventIMU:
    # 간단한 예시 (실제로는 여러 청크가 옴)
    accel: tuple[float, float, float]
    gyro: tuple[float, float, float]
# ==========================================
# 2. 데이터 클래스 (Parsed Responses)
# ==========================================

@dataclass
class ResponseFirmware:
    version: str

@dataclass
class ResponseBoxAddress:
    mac_address: str  # "AA:BB:CC:DD:EE:FF"

@dataclass
class ResponseThreshold:
    button_index: int
    min_val: int
    max_val: int

# 1. 시리얼 넘버 (0x01)
@dataclass
class ResponseSerialNumber:
    number: int
    hex_string: str  # 디버깅용 (예: "01020304")

# 2. SKU (0x02)
@dataclass
class ResponseSKU:
    sku: str  # 예: "KANO-WAND-HP-01"

# 3. 제조사 ID (0x03)
@dataclass
class ResponseManufacturerID:
    name: str # 예: "Kano Computing"

# 4. 장치 ID (0x04)
@dataclass
class ResponseDeviceID:
    id_string: str

# 5. 에디션 정보 (0x05)
@dataclass
class ResponseEdition:
    edition: str

# 6. Companion(Box) MAC 주소 (0x08) - Product Info에 포함될 경우
@dataclass
class ResponseCompanionAddress:
    mac_address: str # "AA:BB:CC:DD:EE:FF"

# 7. 지팡이 타입 (0x09) - 가장 중요!
@dataclass
class ResponseWandType:
    model_id: int
    model_name: WandModel
    description: str # 예: "Harry Potter (Adventurous)"


# 타입 힌트용 Union 타입 정의
ProductResponseVariant = Union[
    ResponseSerialNumber, 
    ResponseSKU, 
    ResponseManufacturerID, 
    ResponseDeviceID, 
    ResponseEdition, 
    ResponseCompanionAddress, 
    ResponseWandType,
    None
]
# ==========================================
# 3. 프로토콜 처리 클래스
# ==========================================

class Protocol:
    """패킷 생성(Build) 및 파싱(Parse) 헬퍼"""
    # --- [TX] 패킷 생성 메서드 ---
    @staticmethod
    def build_keep_alive() -> bytes:
        return struct.pack('B', OpcodeTX.REQ_BATTERY)

    @staticmethod
    def build_vibrate(duration_ms: int) -> bytes:
        # Opcode(1B) + Duration(2B, Little Endian)
        return struct.pack('<B H', OpcodeTX.CMD_VIBRATE, duration_ms)

    @staticmethod
    def build_imu_start() -> bytes:
        # 0x30, 0x80, 00, 00, 00 (React 코드 기준)
        return bytes([OpcodeTX.CMD_IMU_START, 0x80, 0x00, 0x00, 0x00])

    @staticmethod
    def build_imu_stop() -> bytes:
        return struct.pack('B', OpcodeTX.CMD_IMU_STOP)

    @staticmethod
    def build_set_threshold(thresholds: list[tuple[int, int]]) -> bytes:
        """
        thresholds: [(min1, max1), (min2, max2), (min3, max3), (min4, max4)]
        """
        if len(thresholds) != 4:
            raise ValueError("Must provide thresholds for all 4 buttons")
        
        payload = bytearray([OpcodeTX.CMD_SET_THRESHOLD])
        for min_v, max_v in thresholds:
            payload.extend([min_v, max_v])
        return bytes(payload)

    @staticmethod
    def build_read_threshold(button_index: int) -> bytes:
        return struct.pack('BB', OpcodeTX.CMD_READ_THRESHOLD, button_index)
    
    @staticmethod
    def build_request_firmware() -> bytes:
        return struct.pack('B', OpcodeTX.REQ_FIRMWARE)
    
    @staticmethod
    def build_request_product_info() -> bytes:
        return struct.pack('B', OpcodeTX.REQ_PRODUCT_INFO)
    
    @staticmethod
    def build_request_box_address() -> bytes:
        return struct.pack('B', OpcodeTX.REQ_BOX_ADDRESS)
    
    # --- [RX] 패킷 파싱 메서드 ---
    @staticmethod
    def parse_response(data: bytearray) -> Optional[object]:
        if not data:
            return None

        opcode = data[0]

        # 1. 펌웨어 버전 (Opcode 없음, "MCW" 문자열로 시작)
        # 예: b'MCW 1.0.2'
        try:
            # 안전하게 디코딩 시도
            text = data.decode('utf-8')
            if text.startswith("MCW"):
                return ResponseFirmware(version=text.strip())
        except UnicodeDecodeError:
            pass # 텍스트가 아니면 다음 로직으로 넘어감

        # 2. 박스 주소 응답 (0x0A) - 직접 요청에 대한 응답
        # 구조: [0A, B6, B5, B4, B3, B2, B1] (역순 MAC)
        if opcode == OpcodeRX.RESP_BOX_ADDRESS and len(data) == 7:
            mac_bytes = data[1:][::-1]
            mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
            return ResponseBoxAddress(mac_address=mac_str)

        # 3. 제품 정보 응답 (0x0E) -> 구체적인 클래스로 분기
        # 구조: [0E, Type, Data...]
        if opcode == OpcodeRX.RESP_PRODUCT_INFO and len(data) >= 3:
            info_type = data[1]
            raw_val = data[2:]
            
            # 3-1. 시리얼 넘버 (0x01)
            if info_type == ProductInfoType.SERIAL_NUMBER:
                if len(raw_val) >= 4:
                    num = struct.unpack('<I', raw_val[:4])[0]
                    return ResponseSerialNumber(number=num, hex_string=raw_val.hex())

            # 3-2. 지팡이 타입 (0x09) [중요]
            elif info_type == ProductInfoType.WAND_TYPE:
                if len(raw_val) >= 1:
                    tid = raw_val[0]
                    try:
                        model = WandModel(tid)
                    except ValueError:
                        model = WandModel.UNKNOWN
                    
                    desc_map = {
                        WandModel.HARRY_POTTER: "Harry Potter (Adventurous)",
                        WandModel.HERMIONE_GRANGER: "Hermione Granger (Defiant)",
                        WandModel.RON_WEASLEY: "Ron Weasley (Heroic)",
                        WandModel.DUMBLEDORE: "Dumbledore (Honourable)",
                        WandModel.NEWT_SCAMANDER: "Newt Scamander (Loyal)",
                        WandModel.WISE_UNKNOWN: "Wise",
                        WandModel.UNKNOWN: "Unknown Model"
                    }
                    return ResponseWandType(
                        model_id=tid, 
                        model_name=model, 
                        description=desc_map.get(model, "Unknown")
                    )

            # 3-3. 문자열 데이터들 (SKU, MFG_ID, DEVICE_ID, EDITION)
            elif info_type == ProductInfoType.SKU:
                text = raw_val.decode('utf-8', errors='ignore').strip().replace('\x00', '')
                return ResponseSKU(sku=text)

            elif info_type == ProductInfoType.MFG_ID:
                text = raw_val.decode('utf-8', errors='ignore').strip().replace('\x00', '')
                return ResponseManufacturerID(name=text)

            elif info_type == ProductInfoType.DEVICE_ID:
                text = raw_val.decode('utf-8', errors='ignore').strip().replace('\x00', '')
                return ResponseDeviceID(id_string=text)
                
            elif info_type == ProductInfoType.EDITION:
                text = raw_val.decode('utf-8', errors='ignore').strip().replace('\x00', '')
                return ResponseEdition(edition=text)

            # 3-4. Companion Address (Info 패킷 내부에 포함된 경우)
            elif info_type == ProductInfoType.COMPANION_MAC:
                if len(raw_val) == 6:
                    mac_bytes = raw_val[::-1]
                    mac_str = ':'.join(f'{b:02X}' for b in mac_bytes)
                    return ResponseCompanionAddress(mac_address=mac_str)

        # 4. 버튼 감도 응답 (0xDE)
        # 구조: [DE, Idx, Min, Max]
        if opcode == OpcodeRX.RESP_THRESHOLD and len(data) == 4:
            return ResponseThreshold(
                button_index=data[1],
                min_val=data[2],
                max_val=data[3]
            )

        return None
    
    @staticmethod
    def parse_stream(data: bytearray) -> Union[EventButton, EventSpell, EventIMU, None]:
        if not data or len(data) < 2:
            return None

        opcode = data[0]

        # 1. 버튼 이벤트 (0x11)
        # 구조: [11, Mask]
        if opcode == OpcodeStream.BUTTON_EVENT:
            mask = data[1]
            return EventButton(
                mask=mask,
                is_big_pressed=(mask & 0x01) > 0,
                is_top_pressed=(mask & 0x02) > 0,
                is_mid_pressed=(mask & 0x04) > 0,
                is_bot_pressed=(mask & 0x08) > 0
            )

        # 2. 주문(Spell) 이벤트 (0x24)
        # 구조: [Header(4B), Length(1B), String...]
        # React 코드: const header = data.slice(0, 4); const spellLength = data[3] (index 3이 Length일 수 있음)
        # 패킷 덤프 분석 기반 수정:
        # 일반적으로 [24, XX, XX, XX] (헤더 4바이트) + [Len] + [String] 구조임.
        if opcode == OpcodeStream.SPELL_EVENT:
            try:
                # 데이터가 충분히 긴지 확인 (헤더4 + 길이1 + 최소문자1)
                if len(data) < 6: 
                    return None
                
                # React 코드 로직: "const spellLength = data[3];" 라고 되어 있었으나
                # 일반적인 패킷 구조상 헤더 뒤에 길이가 옴.
                # 안전하게 5번째 바이트(Index 4)부터 문자열 탐색
                
                # 주문 이름 길이 (Index 4) - 가변적일 수 있으므로 길이 바이트 확인
                spell_len = data[4]
                
                # 문자열 추출 (Index 5부터)
                raw_name = data[5 : 5 + spell_len]
                spell_name = raw_name.decode('utf-8', errors='ignore').strip()
                
                # 널 문자 및 공백 제거, 정규화
                spell_name = spell_name.replace('\x00', '').replace('_', ' ')
                
                if not spell_name:
                    return None
                    
                return EventSpell(name=spell_name, raw_bytes=raw_name)
                
            except Exception as e:
                print(f"Spell Parse Error: {e}")
                return None

        # 3. IMU 데이터 (Opcode 확인 필요, 보통 12바이트 배수로 옴)
        # 이 부분은 헤더 체크 로직이 복잡하므로 여기선 생략하거나
        # 데이터 길이로 추정 가능 (예: len(data) > 10 and (len(data)-4) % 12 == 0)
        
        return None