"""
Wand Motion Tracker with AHRS-based Spell Rendering

Uses Madgwick AHRS filter to convert IMU data into stable 2D spell traces.

Axis Mapping:
- Horizontal (X): -roll (tilt left/right)
- Vertical (Y): -yaw (rotate wand tip left/right)

TUNING:
- Adjust TRACE_SCALE (line 21) to change gesture size
- Enable DEBUG_IMU (line 17) to see raw sensor values
"""

import asyncio
import logging
from bleak import BleakClient
from mcw import McwClient
import tkinter as tk
from collections import deque
import numpy as np
from ahrs.filters import Madgwick

# Configuration
MAC_ADDRESS = "F4:27:7E:29:39:D2"
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
TRAIL_LENGTH = 200  # Number of points to keep in trail
MOTION_SENSITIVITY = 5.0  # Scale factor for motion (using gyro now)
SMOOTHING = 0.85  # Smoothing factor (0-1, higher = more smoothing)
DEBUG_IMU = False  # Set to True to see IMU values

# AHRS Configuration
AHRS_SAMPLE_RATE = 100.0  # Hz - IMU sample rate
TRACE_SCALE = 50.0  # Scale factor for spell rendering (increase for bigger gestures)


class SpellRenderer:
    """
    AHRS-based spell renderer that converts IMU data to 2D screen coordinates.

    Axis mapping: X = -roll (left/right tilt), Y = -yaw (rotate wand tip)
    """

    def __init__(self, canvas_width=800, canvas_height=600, trace_scale=TRACE_SCALE):
        self.canvas_width = canvas_width
        self.canvas_height = canvas_height
        self.trace_scale = trace_scale

        # Center point where spell starts
        self.start_x = canvas_width / 2
        self.start_y = canvas_height / 2

        # AHRS filter (Madgwick)
        self.ahrs = Madgwick(frequency=AHRS_SAMPLE_RATE)

        # Current orientation quaternion [w, x, y, z]
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])

        # Reference orientation (captured at spell start)
        self.reference_quaternion = None
        self.reference_yaw = 0.0
        self.reference_roll = 0.0

        # Path tracking
        self.path = []
        self.is_active = False

    def start_spell(self):
        """Start a new spell gesture"""
        self.path = []
        self.is_active = True
        # Reset AHRS filter
        self.ahrs = Madgwick(frequency=AHRS_SAMPLE_RATE)
        self.quaternion = np.array([1.0, 0.0, 0.0, 0.0])
        # Reset reference - will be set on first update
        self.reference_quaternion = None
        self.reference_yaw = 0.0
        self.reference_roll = 0.0

    def end_spell(self):
        """End the current spell gesture and return the path"""
        self.is_active = False
        return self.path.copy()

    def update_imu(self, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z, dt=0.01):
        """
        Process IMU sample and return screen coordinates

        Args:
            accel_x, accel_y, accel_z: Accelerometer readings (m/s^2)
            gyro_x, gyro_y, gyro_z: Gyroscope readings (rad/s)
            dt: Time delta since last sample (seconds)

        Returns:
            Tuple of (screen_x, screen_y) coordinates, or None if not active
        """
        if not self.is_active:
            return None

        # Create numpy arrays for AHRS processing
        accel = np.array([accel_x, accel_y, accel_z])
        gyro = np.array([gyro_x, gyro_y, gyro_z])

        # Update AHRS filter with IMU data
        # This produces a quaternion representing the current orientation
        self.quaternion = self.ahrs.updateIMU(self.quaternion, gyr=gyro, acc=accel)

        # Extract yaw and roll from current orientation
        yaw, roll = self._quaternion_to_yaw_roll(self.quaternion)

        # On first update, capture reference orientation
        if self.reference_quaternion is None:
            self.reference_quaternion = self.quaternion.copy()
            self.reference_yaw = yaw
            self.reference_roll = roll
            # Start at center
            screen_x = self.start_x
            screen_y = self.start_y
        else:
            # Calculate relative position
            # X axis: -roll (negative roll delta = left/right tilt)
            # Y axis: -yaw (negative yaw delta = rotate wand tip)
            delta_roll = roll - self.reference_roll
            delta_yaw = yaw - self.reference_yaw

            pos_x = -delta_roll
            pos_y = -delta_yaw

            # Scale with multiplier (100.0 from reference implementation)
            pos_x *= 100.0 * self.trace_scale
            pos_y *= 100.0 * self.trace_scale

            # Convert to screen coordinates
            screen_x = self.start_x + pos_x
            screen_y = self.start_y + pos_y

        # Add to path
        point = (screen_x, screen_y)
        self.path.append(point)

        return point

    def _quaternion_to_yaw_roll(self, q):
        """
        Convert quaternion to yaw and roll Euler angles.

        Args:
            q: Quaternion array [w, x, y, z]

        Returns:
            Tuple of (yaw, roll) in radians
        """
        # Extract quaternion components
        w, x, y, z = q

        # Yaw (rotation around Z axis) - rotate wand tip left/right
        sin_yaw = 2.0 * (w * z + x * y)
        cos_yaw = 1.0 - 2.0 * (y * y + z * z)
        yaw = np.arctan2(sin_yaw, cos_yaw)

        # Roll (rotation around X axis) - tilt wand left/right
        sin_roll = 2.0 * (w * x + y * z)
        cos_roll = 1.0 - 2.0 * (x * x + y * y)
        roll = np.arctan2(sin_roll, cos_roll)

        return yaw, roll


class MotionVisualizer:
    def __init__(self, loop):
        self.loop = loop
        self.mcw = None  # Will be set by wand_connection
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

        # AHRS-based spell renderer
        self.spell_renderer = SpellRenderer(
            canvas_width=CANVAS_WIDTH,
            canvas_height=CANVAS_HEIGHT,
            trace_scale=TRACE_SCALE
        )

        # Motion tracking
        self.motion_mode = False
        self.trail = deque(maxlen=TRAIL_LENGTH)
        self.current_pos = [CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2]
        self.trail_line_ids = []

        # Button state tracking
        self.button_state = {
            'pad1': False,
            'pad2': False,
            'pad3': False,
            'pad4': False,
            'full_touch': False
        }

        # Running flag
        self.running = True

    def handle_button_callback(self, button_data):
        """Handle button state updates"""
        prev_full_touch = self.button_state['full_touch']
        self.button_state = button_data

        # Update button indicators
        for i, (pad_key, label) in enumerate(zip(['pad1', 'pad2', 'pad3', 'pad4'], self.button_labels)):
            color = 'green' if button_data[pad_key] else 'gray'
            label.config(fg=color)

        # Check if entering motion mode (all buttons pressed)
        if button_data['full_touch'] and not prev_full_touch:
            print("Entering motion mode - all buttons pressed")
            self.enter_motion_mode()

        # Check if exiting motion mode (any button released)
        elif prev_full_touch and not button_data['full_touch']:
            print("Exiting motion mode - button released")
            self.exit_motion_mode()

    def handle_imu_callback(self, imu_data):
        """Handle IMU data updates using AHRS-based spell rendering"""
        if not self.motion_mode or not imu_data:
            return

        # Process the most recent IMU sample (processing all can cause lag)
        sample = imu_data[-1]

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
            accel_x=accel_x,
            accel_y=accel_y,
            accel_z=accel_z,
            gyro_x=gyro_x,
            gyro_y=gyro_y,
            gyro_z=gyro_z,
            dt=1.0 / AHRS_SAMPLE_RATE
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
            asyncio.create_task(self.mcw.led_on(255, 0, 0))

    def exit_motion_mode(self):
        """Exit motion mode"""
        self.motion_mode = False
        self.status_label.config(text="Hold all buttons to start", fg='white')
        print("Motion mode: INACTIVE")

        # End spell rendering and get the complete path
        path = self.spell_renderer.end_spell()
        print(f"Spell complete: {len(path)} points captured")

        # Turn off LEDs
        if self.mcw:
            asyncio.create_task(self.mcw.led_off())

    def clear_canvas(self):
        """Clear all trail lines from canvas"""
        for line_id in self.trail_line_ids:
            self.canvas.delete(line_id)
        self.trail_line_ids.clear()

    def render(self):
        """Render the visualization"""
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
        self.root.quit()

    def update(self):
        """Update GUI (called periodically)"""
        if self.running:
            self.render()
            self.root.update()

    def cleanup(self):
        """Cleanup tkinter resources"""
        try:
            self.root.destroy()
        except:
            pass


async def wand_connection(visualizer):
    """Handle wand connection and data streaming"""
    # Setup logging
    logging.basicConfig(level=logging.INFO)
    #logging.getLogger("mcw").setLevel(logging.DEBUG)

    print(f"Connecting to wand at {MAC_ADDRESS}...")
    client = BleakClient(MAC_ADDRESS)

    try:
        await client.__aenter__()
        if not client.is_connected:
            print("Failed to connect to wand.")
            visualizer.running = False
            return

        print("Connected! Creating MCW client...")
        mcw = McwClient(client)
        visualizer.mcw = mcw  # Pass mcw to visualizer for LED control

        mcw.register_callbacks(
            spell_cb=None,
            battery_cb=None,
            button_cb=visualizer.handle_button_callback,
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
