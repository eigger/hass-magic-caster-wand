# Visualizer for wand motion with spell detection when model is available.
# To launch, use the following steps:
#   1. Change to the tools directory
#   2. If necessary create a venv (python -m venv venv)
#   3. Make sure your venv is activated
#   4. If necessary install dependencies (pip install -r imuvisualizer.txt)
#   5. Run "python imuvisualizer.py"

import asyncio
import concurrent.futures
import logging
import numpy as np
import sys
import tkinter as tk

from bleak import BleakClient
from collections import deque
from pathlib import Path

# Add the custom_components path and set up mcw_ble as a package
# We need to import submodules without triggering __init__.py (which has HA dependencies)
_CUSTOM_COMPONENTS_PATH = Path(__file__).parent.parent / "custom_components"
_MCW_BLE_PATH = _CUSTOM_COMPONENTS_PATH / "magic_caster_wand" / "mcw_ble"
sys.path.insert(0, str(_CUSTOM_COMPONENTS_PATH))

# Import submodules using importlib to avoid __init__.py
import importlib.util

def _load_module(name: str, filepath: Path):
    """Load a module from a file path without going through __init__.py."""
    spec = importlib.util.spec_from_file_location(f"magic_caster_wand.mcw_ble.{name}", filepath)
    module = importlib.util.module_from_spec(spec)
    # Register as part of mcw_ble package so relative imports work
    sys.modules[f"magic_caster_wand.mcw_ble.{name}"] = module
    spec.loader.exec_module(module)
    return module

# Create a fake mcw_ble package entry so relative imports resolve
import types
_fake_mcw_ble = types.ModuleType("magic_caster_wand.mcw_ble")
_fake_mcw_ble.__path__ = [str(_MCW_BLE_PATH)]
sys.modules["magic_caster_wand.mcw_ble"] = _fake_mcw_ble

# Load modules in dependency order
_macros = _load_module("macros", _MCW_BLE_PATH / "macros.py")
_mcw = _load_module("mcw", _MCW_BLE_PATH / "mcw.py")
_spell_detector = _load_module("spell_detector", _MCW_BLE_PATH / "spell_detector.py")
_spell_tracker = _load_module("spell_tracker", _MCW_BLE_PATH / "spell_tracker.py")

LedGroup = _macros.LedGroup
McwClient = _mcw.McwClient
SpellTracker = _spell_tracker.SpellTracker

try:
    _local_detector = _load_module("local_tensor_spell_detector", _MCW_BLE_PATH / "local_tensor_spell_detector.py")
    LocalTensorSpellDetector = _local_detector.LocalTensorSpellDetector
except ImportError:
    LocalTensorSpellDetector = None

try:
    _remote_detector = _load_module("remote_tensor_spell_detector", _MCW_BLE_PATH / "remote_tensor_spell_detector.py")
    RemoteTensorSpellDetector = _remote_detector.RemoteTensorSpellDetector
except ImportError:
    RemoteTensorSpellDetector = None

# Configuration
MAC_ADDRESS = "E0:F8:53:63:F8:EA"
MODEL_PATH = _MCW_BLE_PATH / "model.tflite"  # Obtained from APK, _MCW_BLE_PATH set above
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
TRAIL_LENGTH = 8192  # Number of points to keep in trail
DEBUG_IMU = False  # Set to True to see IMU values

class SpellRenderer:
    def __init__(self, canvas_width=800, canvas_height=600):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height

        # Center point where spell starts
        self.start_x = canvas_width / 2
        self.start_y = canvas_height / 2

        detector = None
        if LocalTensorSpellDetector is not None and MODEL_PATH.exists():
            try:
                detector = LocalTensorSpellDetector(MODEL_PATH)
                print("Using LocalTensorSpellDetector for spell detection.")
            except:
                print("Warning: Failed to initialize LocalTensorSpellDetector. Spell detection disabled.")
        elif RemoteTensorSpellDetector is not None:
            try:
                detector = RemoteTensorSpellDetector(MODEL_PATH.name, "http://localhost:8000")
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    executor.submit(asyncio.run, detector.async_init()).result()
                print("Using RemoteTensorSpellDetector for spell detection.")
            except:
                print("Warning: Failed to initialize RemoteTensorSpellDetector. Spell detection disabled.")
        else:
            print("Warning: No spell detector available. Spell detection disabled.")

        self.tracker: SpellTracker = SpellTracker(detector=detector)

    def start_spell(self) -> None:
        """Start a new spell gesture"""
        self.tracker.start()

    async def end_spell(self) -> str | None:
        """End the current spell gesture and return the recognized spell name."""
        return await self.tracker.stop()

    def update_imu(self, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z):
        point: tuple[np.float32, np.float32] | None = self.tracker.update(accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z)

        if point is None:
            return None

        return [point[0] + self.start_x, point[1] + self.start_y]

class MotionVisualizer:
    def __init__(self, loop):
        self.loop = loop
        self.mcw = None  # Will be set by wand_connection
        self.root = None
        self.canvas = None
        self.status_label = None
        self.button_frame = None
        self.button_labels: list[tk.Label] = []
        self.ui_ready = False

        # AHRS-based spell renderer
        self.spell_renderer = SpellRenderer(
            canvas_width=CANVAS_WIDTH,
            canvas_height=CANVAS_HEIGHT,
        )
        self.motion_mode = False
        self.trail = deque(maxlen=TRAIL_LENGTH)
        self.current_pos = [CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2]
        self.trail_line_ids = []

        # Button state tracking
        self.button_state = {
            'button_1': False,
            'button_2': False,
            'button_3': False,
            'button_4': False,
            'button_all': False
        }

        # Running flag
        self.running = True

    def start_ui(self):
        """Create the Tk window only after the wand connects"""
        if self.ui_ready:
            return

        self.root = tk.Tk()
        self.root.title("Wand Motion Tracker")
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # Canvas
        self.canvas = tk.Canvas(self.root, width=CANVAS_WIDTH, height=CANVAS_HEIGHT, bg='black')
        self.canvas.pack()

        # Status label
        self.status_label = tk.Label(self.root, text="Hold all buttons to start",
                                     font=('Arial', 14), fg='white', bg='black')
        self.status_label.place(x=10, y=10)

        # Button indicators frame
        self.button_frame = tk.Frame(self.root, bg='black')
        self.button_frame.place(x=10, y=50)

        self.button_labels = []
        for i in range(4):
            label = tk.Label(self.button_frame, text=f"Pad {i+1}",
                             font=('Arial', 12), fg='gray', bg='black')
            label.pack(anchor='w')
            self.button_labels.append(label)

        self.ui_ready = True

    def handle_button_callback(self, button_data: dict[str, bool]):
        """Handle button state updates"""
        prev_button_all = self.button_state['button_all']
        self.button_state = button_data

        # Update button indicators
        for i, (pad_key, label) in enumerate(zip(['button_1', 'button_2', 'button_3', 'button_4'], self.button_labels)):
            color = 'green' if button_data[pad_key] else 'gray'
            label.config(fg=color)

        # Check if entering motion mode (all buttons pressed)
        if button_data['button_all'] and not prev_button_all:
            print("Entering motion mode - all buttons pressed")
            self.enter_motion_mode()

        # Check if exiting motion mode (any button released)
        elif prev_button_all and not button_data['button_all']:
            print("Exiting motion mode - button released")
            asyncio.create_task(self.exit_motion_mode())

    def handle_imu_callback(self, imu_data: list[dict[str, float]]):
        """Handle IMU data updates using AHRS-based spell rendering"""
        if not imu_data:
            return

        for sample in imu_data:
            # Extract IMU data from sample
            accel_x = sample['accel_x']
            accel_y = sample['accel_y']
            accel_z = sample['accel_z']
            gyro_x = sample['gyro_x']
            gyro_y = sample['gyro_y']
            gyro_z = sample['gyro_z']

            if DEBUG_IMU:
                print(f"Accel: X={accel_x:.3f}, Y={accel_y:.3f}, Z={accel_z:.3f}")
                print(f"Gyro: X={gyro_x:.3f}, Y={gyro_y:.3f}, Z={gyro_z:.3f}")

            # Update AHRS filter and get screen position
            # dt = 1/100 = 0.01 seconds (assuming 100Hz sample rate)
            point = self.spell_renderer.update_imu(
                accel_x=accel_y,
                accel_y=-accel_x,
                accel_z=accel_z,
                gyro_x=gyro_y,
                gyro_y=-gyro_x,
                gyro_z=gyro_z
            )

        if point is not None:
            screen_x, screen_y = point

            if DEBUG_IMU:
                print(f"Raw Screen: X={screen_x:.1f}, Y={screen_y:.1f}")

            # Clamp to canvas bounds
            screen_x = max(0, min(CANVAS_WIDTH, screen_x))
            screen_y = max(0, min(CANVAS_HEIGHT, screen_y))

            # Update current position for rendering
            self.current_pos = [screen_x, screen_y]

            # Add to trail
            self.trail.append((screen_x, screen_y))

            if DEBUG_IMU:
                print(f"Clamped Screen: X={screen_x:.1f}, Y={screen_y:.1f}, Trail len={len(self.trail)}")

    def enter_motion_mode(self):
        """Enter motion mode and clear canvas"""
        self.motion_mode = True
        self.trail.clear()
        self.clear_canvas()
        self.current_pos = [CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2]
        self.status_label.config(text="MOTION MODE", fg='lime')
        print("Motion mode: ACTIVE")

        # Start spell rendering with AHRS
        self.spell_renderer.start_spell()

        # Set LEDs to red
        if self.mcw:
            asyncio.create_task(self.mcw.led_on(LedGroup.TIP, 255, 0, 0))

    async def exit_motion_mode(self):
        """Exit motion mode"""
        self.motion_mode = False
        print("Motion mode: INACTIVE")

        # End spell rendering and get the recognized spell
        spell_name = await self.spell_renderer.end_spell()
        
        if spell_name:
            self.status_label.config(text=f"Spell: {spell_name}", fg='yellow')
            print(f"Recognized spell: {spell_name}")
        else:
            self.status_label.config(text="Hold all buttons to start", fg='white')

        # Turn off LEDs
        if self.mcw:
            asyncio.create_task(self.mcw.led_off())

    def clear_canvas(self):
        """Clear all trail lines from canvas"""
        if not self.ui_ready:
            return
        for line_id in self.trail_line_ids:
            self.canvas.delete(line_id)
        self.trail_line_ids.clear()

    def render(self):
        """Render the visualization"""
        if not self.ui_ready:
            return
        # Draw trail if in motion mode
        if self.motion_mode and len(self.trail) > 1:
            # Only draw the latest segment
            if len(self.trail) >= 2:
                p1 = self.trail[-2]
                p2 = self.trail[-1]
                line_id = self.canvas.create_line(p1[0], p1[1], p2[0], p2[1],
                                                 fill='cyan', width=2)
                self.trail_line_ids.append(line_id)

                # Clean up old lines if we have too many
                if len(self.trail_line_ids) > TRAIL_LENGTH:
                    old_line_id = self.trail_line_ids.pop(0)
                    self.canvas.delete(old_line_id)

            # Draw cursor at current position
            x, y = int(self.current_pos[0]), int(self.current_pos[1])
            # Remove old cursor if exists
            self.canvas.delete('cursor')
            self.canvas.create_oval(x-5, y-5, x+5, y+5, fill='yellow', tags='cursor')

    def on_close(self):
        """Handle window close event"""
        self.running = False
        if self.root:
            self.root.quit()

    def update(self):
        """Update GUI (called periodically)"""
        if self.running and self.ui_ready:
            self.render()
            self.root.update()

    def cleanup(self):
        """Cleanup tkinter resources"""
        try:
            if self.root:
                self.root.destroy()
        except Exception:
            pass


async def wand_connection(visualizer):
    """Handle wand connection and data streaming"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    #logging.getLogger("magic_caster_wand.mcw_ble.mcw").setLevel(logging.DEBUG)

    print(f"Connecting to wand at {MAC_ADDRESS}...")
    client = BleakClient(MAC_ADDRESS)

    try:
        await client.__aenter__()
        if not client.is_connected:
            print("Failed to connect to wand.")
            visualizer.running = False
            return

        print("Connected! Creating MCW client...")
        visualizer.start_ui()
        mcw = McwClient(client)
        visualizer.mcw = mcw  # Pass mcw to visualizer for LED control

        mcw.register_callback(
            spell_cb=None,
            battery_cb=None,
            buttons_cb=visualizer.handle_button_callback,
            calibration_cb=None,
            imu_cb=visualizer.handle_imu_callback
        )

        # Start notifications
        print("Starting notifications...")
        await mcw.start_notify()

        # Start IMU streaming
        print("Starting IMU streaming...")
        await mcw.imu_streaming_start()

        print("\nInstructions:")
        print("- Press and hold ALL 4 capacitive buttons to enter motion mode")
        print("- Move the wand to draw on the canvas")
        print("- Release any button to exit motion mode")
        print("- Close window to exit\n")

        # Keep connection alive while GUI is running
        while visualizer.running:
            await asyncio.sleep(0.01)

        # Cleanup
        print("\nStopping IMU streaming...")
        await mcw.imu_streaming_stop()
        await mcw.stop_notify()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        visualizer.running = False
    finally:
        await client.__aexit__(None, None, None)
        print("Disconnected.")


async def gui_update(visualizer):
    """Periodically update the GUI"""
    while visualizer.running:
        visualizer.update()
        await asyncio.sleep(0.016)  # ~60 FPS


async def main():
    loop = asyncio.get_event_loop()
    visualizer = MotionVisualizer(loop)

    try:
        # Run both tasks concurrently
        await asyncio.gather(
            wand_connection(visualizer),
            gui_update(visualizer)
        )
    except Exception as e:
        print(f"Main error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        visualizer.cleanup()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nInterrupted by user")
