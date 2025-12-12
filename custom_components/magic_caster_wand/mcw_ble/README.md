# 🪄 Magic Wand BLE Protocol (Unofficial)

---

## 📡 1. Connection Specifications

The devices use **128-bit Custom UUIDs**. Standard 16-bit UUIDs will not work.

### 🪄 Magic Wand (Target Name: `MCW`)

| Type | UUID | Properties | Description |
| :--- | :--- | :--- | :--- |
| **Service** | `57420001-587e-48a0-974c-544d6163c577` | - | Main Control Service |
| **Command** | `57420002-587e-48a0-974c-544d6163c577` | Write, Notify | **(CH1)** Send commands & receive status |
| **Stream** | `57420003-587e-48a0-974c-544d6163c577` | Notify | **(CH2)** High-speed sensor data, spells, buttons |
| **Battery** | `00002a19-0000-1000-8000-00805f9b34fb` | Read, Notify | Standard Battery Level (0-100%) |

---

## 📤 2. Output Protocol (TX: App → Device)

Send these commands to the **Command Characteristic (CH1)**.

### 🛠 Control Opcodes

| Command | Opcode | Payload (Hex) | Description |
| :--- | :--- | :--- | :--- |
| **Firmware Req** | `0x00` | `[00]` | Request firmware string |
| **Keep Alive** | `0x01` | `[01]` | Battery Status Request (Used as heartbeat) |
| **Box Addr Req** | `0x09` | `[09]` | Request MAC address of paired box |
| **Factory Unlock**| `0x0B` | `[0B]` | Unlocks calibration commands |
| **Product Info** | `0x0D` | `[0D]` | Request SKU, Serial, etc. |
| **IMU Start** | `0x30` | `[30, 80, 00, 00, 00]` | **High Battery Drain**. Starts sensor stream. |
| **IMU Stop** | `0x31` | `[31]` | Stops sensor stream. |
| **Light Clear** | `0x40` | `[40]` | Turns off all LEDs immediately. |
| **Vibrate** | `0x50` | `[50, TL, TH]` | `T` = Duration in ms (Little Endian). |
| **Macro Flush** | `0x60` | `[60]` | Clears current macro queue. |
| **Macro Exec** | `0x68` | *(See Section 3)* | Executes custom LED/Haptic sequence. |
| **Predefined** | `0x69` | `[69, ID]` | Runs built-in effect (e.g., `0x0A`). |
| **Set Threshold**| `0x70` | `[70, Min1, Max1...]` | Sets button sensitivity. |

---

## 🌈 3. VFX Macro Protocol (Opcode `0x68`)

To create custom light patterns and vibrations, send a sequence of instructions starting with `0x68`.

**Structure:** `[ 0x68, INSTRUCTION, PARAM_1, PARAM_2... ]`

### Macro Instructions

| Instruction | Opcode | Parameters | Description |
| :--- | :--- | :--- | :--- |
| **Delay** | `0x10` | `[TL, TH]` | Wait for `T` milliseconds. |
| **Light Clear** | `0x20` | - | Turn off LED. |
| **Light Trans** | `0x22` | `[00, R, G, B, TL, TH]` | Fade to RGB color over `T` ms. |
| **Set Loops** | `0x80` | `[Count]` | Mark end of loop & set iteration count. |
| **Loop Start** | `0x81` | - | Mark start of loop. |

**Example: Flash Red (500ms)**
```hex
68 22 00 FF 00 00 F4 01
(Opcode 68, Trans 22, Mode 00, R=255, G=0, B=0, Dur=500ms)

📥 4. Input Protocol (RX: Device → App)
Data received via Stream Characteristic (CH2) notifications.

🔘 Button Events
Opcode: 0x26 (Estimated from incoming logic)

Payload: [ 0x26, Mask ]

0x01: Button 1 (Large)

0x02: Button 2

0x04: Button 3

0x08: Button 4

✨ Spell Gestures
Triggered when the hardware recognizes a wand motion.

Opcode: 0x24

Structure: [ Header(4B), Length(1B), Name(String) ]

Example: LUMOS, WINGARDIUM_LEVIOSA

🧭 IMU Stream
Active only after IMU_START. Contains 3-axis Accelerometer & Gyroscope data.

Structure: Header (4B) + N × DataChunk (12B)

Chunk Layout: [AY, AX, AZ, GY, GX, GZ] (int16, Little Endian)

Scale Factors:

Accel: Raw * 0.0078125 (G)

Gyro: Raw * 0.01084 (dps)

🐍 5. Python Example (Bleak)
This script connects to the wand, vibrates it, and listens for spells/buttons.

Python

import asyncio
from bleak import BleakScanner, BleakClient

# --- Constants derived from constants.ts ---
UUID_WAND_CMD    = "57420002-587e-48a0-974c-544d6163c577"
UUID_WAND_STREAM = "57420003-587e-48a0-974c-544d6163c577"

CMD_KEEPALIVE = 0x01  # Battery Request
CMD_VIBRATE   = 0x50

async def main():
    print("Scanning for 'MCW'...")
    device = await BleakScanner.find_device_by_name("MCW")
    
    if not device:
        print("❌ Wand not found.")
        return

    async with BleakClient(device) as client:
        print(f"✅ Connected to {device.name}")

        # Data Handler
        def handle_stream(sender, data):
            # Spell Event (0x24)
            if data[0] == 0x24:
                try:
                    # Skip header(4) + len(1) = 5 bytes
                    spell = data[5:].decode('utf-8', errors='ignore').strip()
                    print(f"✨ SPELL CAST: {spell}")
                except: pass
            
            # Button Event (0x26)
            elif data[0] == 0x26:
                print(f"🔘 Button Mask: {data[1]}")

        # Subscribe to notifications
        await client.start_notify(UUID_WAND_STREAM, handle_stream)
        
        # Send Haptic Feedback (250ms)
        # Payload: [0x50, 0xFA, 0x00]
        await client.write_gatt_char(UUID_WAND_CMD, bytearray([CMD_VIBRATE, 0xFA, 0x00]), response=True)
        print("📳 Sent vibration command.")

        # Keep-Alive Loop
        print("Waiting for spells... (Ctrl+C to exit)")
        try:
            while True:
                await asyncio.sleep(5)
                # Send Keep-Alive (Battery Request)
                await client.write_gatt_char(UUID_WAND_CMD, bytearray([CMD_KEEPALIVE]), response=True)
        except KeyboardInterrupt:
            print("Disconnecting...")

if __name__ == "__main__":
    asyncio.run(main())
⚠️ Important Notes
UUID Format: You must use the full 128-bit UUIDs listed above.

Battery Drain: Avoid keeping IMU_START (Opcode 0x30) active unless necessary. It drains the battery rapidly. Spell recognition works without it.

Connection: Button presses and Spell events are NOT advertised. You must connect and subscribe to notifications to receive them.