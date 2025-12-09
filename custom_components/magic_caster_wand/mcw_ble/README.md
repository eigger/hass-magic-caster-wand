# 🪄 Magic Wand BLE Protocol (Unofficial)

## 📡 1. Connection Specifications

The device uses **Custom 128-bit UUIDs**. Standard 16-bit UUIDs will **not** work.

| Type | Name / Value | Description |
| :--- | :--- | :--- |
| **Device Name** | `MCW` | Used for filtering during scan |
| **Service UUID** | `64A70012-F691-4B93-A6F4-0968F5B648F8` | Main Control Service |
| **Char: Command** | `64A70013-F691-4B93-A6F4-0968F5B648F8` | **(CH1)** Read, Write, Notify |
| **Char: Stream** | `64A70014-F691-4B93-A6F4-0968F5B648F8` | **(CH2)** Notify (Sensors, Buttons, Spells) |

### 🔄 Connection Flow
1. **Scan**: Look for devices starting with name `MCW`.
2. **Connect**: Connect to the GATT Server.
3. **Subscribe**: Enable notifications (`start_notify`) on **CH1** and **CH2**.
4. **Keep-Alive**: Send a keep-alive packet (e.g., `0x00`) to CH1 every ~5 seconds.

---

## 📥 2. Input Protocol (RX: Device → App)

Data received from the wand via **Stream Char (CH2)** notifications.

### 🔘 Button Events
Triggered when buttons are pressed or released. **(Requires active connection)**

* **Opcode**: `0x11`
* **Packet**: `[ 0x11, Mask ]`

| Bit Mask | Button |
| :--- | :--- |
| `0x01` | Button 1 (Big) |
| `0x02` | Button 2 |
| `0x04` | Button 3 |
| `0x08` | Button 4 |

### ✨ Spell Gestures
Triggered when a spell gesture is recognized by the hardware.

* **Opcode**: `0x24`
* **Packet Structure**:
[ Header (4 bytes) ] [ Length (1 byte) ] [ Spell Name String (ASCII) ]

* **Example**: `WINGARDIUM LEVIOSA`, `LUMOS`, `INCENDIO`

### 🧭 IMU Sensor Data
High-speed stream of Accelerometer & Gyroscope data. (Only active after `IMU_START` command).

* **Structure**: Header (4B) + N × DataChunk (12B)
* **Single Chunk Layout (12 Bytes, Little Endian)**:

| Offset | Type | Value | Unit Conversion |
| :--- | :--- | :--- | :--- |
| 0 | `int16` | Accel Y | `-(Raw * 0.0078125)` G |
| 2 | `int16` | Accel X | `Raw * 0.0078125` G |
| 4 | `int16` | Accel Z | `Raw * 0.0078125` G |
| 6 | `int16` | Gyro Y | `-(Raw * 0.01084)` dps |
| 8 | `int16` | Gyro X | `Raw * 0.01084` dps |
| 10 | `int16` | Gyro Z | `Raw * 0.01084` dps |

> **Note**: Y-axis values are inverted (`-`) in the reference implementation.

---

## 📤 3. Output Protocol (TX: App → Device)

Commands sent to the wand via **Command Char (CH1)**.

### 🛠 Control Commands

| Command | Hex Payload | Description |
| :--- | :--- | :--- |
| **Keep Alive** | `00` | Heartbeat to maintain connection |
| **IMU Start** | `13` | Start sensor streaming **(High Battery Drain)** |
| **IMU Stop** | `14` | Stop sensor streaming |
| **Vibrate** | `02 [TL] [TH]` | Haptic feedback (`T`: Duration ms in Little Endian) |

### 🌈 VFX Macros (LED & Haptics)
Execute complex light and vibration sequences.

* **Base Opcode**: `0xMM` (Macro Execute)
* **Example Payload (Solid Red Light for 1s)**:
```hex
[MM, 01, 00, FF, 00, 00, E8, 03]
01: Light Transition Opcode

00: Mode

FF 00 00: RGB Color

E8 03: Duration (1000ms, Little Endian)

🐍 4. Python Example
Requires bleak:

Bash

pip install bleak
Python

import asyncio
from bleak import BleakScanner, BleakClient

# Constants
UUID_CHAR_COMMAND = "64A70013-F691-4B93-A6F4-0968F5B648F8"
UUID_CHAR_STREAM  = "64A70014-F691-4B93-A6F4-0968F5B648F8"

async def main():
    print("Scanning for 'MCW'...")
    device = await BleakScanner.find_device_by_name("MCW")
    
    if not device:
        print("Wand not found.")
        return

    async with BleakClient(device) as client:
        print(f"Connected to {device.name}")

        # Callback for Button/Spells/IMU
        def handle_stream(sender, data):
            # Button Event (0x11)
            if data[0] == 0x11:
                mask = data[1]
                print(f"Button Pressed Mask: {bin(mask)}")
            
            # Spell Event (0x24) - Simple Check
            elif data[0] == 0x24:
                # Skip header(4) and length(1)
                spell_name = data[5:].decode('utf-8', errors='ignore').strip()
                print(f"🪄 SPELL CAST: {spell_name}")

        await client.start_notify(UUID_CHAR_STREAM, handle_stream)
        
        print("Waiting for spells or buttons... (Press Ctrl+C to exit)")
        
        # Keep Alive Loop
        try:
            while True:
                # Send Keep Alive (Example byte)
                # await client.write_gatt_char(UUID_CHAR_COMMAND, bytearray([0x00]))
                await asyncio.sleep(5)
        except KeyboardInterrupt:
            print("Disconnecting...")

if __name__ == "__main__":
    asyncio.run(main())
⚠️ 5. Important Notes
🔋 Battery Drain Warning:

Sending the IMU_START command causes the wand to stream high-frequency data, which drains the battery very quickly.

Only use it when analyzing raw motion data. Always send IMU_STOP when finished.

Spell recognition works without IMU streaming.

Connection Required:

Button events and Spell recognition data are NOT advertised.

You must Connect and Subscribe (Notify) to receive this data.

UUID Format:

Use the full 128-bit UUIDs. Short 16-bit UUIDs will fail.