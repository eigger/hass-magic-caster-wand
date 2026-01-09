import asyncio
import logging
from bleak import BleakClient
from mcw import McwClient
import tkinter as tk
from collections import deque

# Configuration
MAC_ADDRESS = "F4:27:7E:29:39:D2"
CANVAS_WIDTH = 800
CANVAS_HEIGHT = 600
TRAIL_LENGTH = 200  # Number of points to keep in trail
MOTION_SENSITIVITY = 5.0  # Scale factor for motion (using gyro now)
SMOOTHING = 0.85  # Smoothing factor (0-1, higher = more smoothing)
DEBUG_IMU = False  # Set to True to see IMU values

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

        # Motion tracking
        self.motion_mode = False
        self.trail = deque(maxlen=TRAIL_LENGTH)
        self.current_pos = [CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2]
        self.velocity = [0.0, 0.0]  # Velocity for smoothing
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
        """Handle IMU data updates"""
        if not self.motion_mode or not imu_data:
            return

        # Process the most recent IMU sample
        sample = imu_data[-1]

        # Use gyroscope data for motion tracking (better for relative motion)
        # Gyro measures rotational velocity in rad/s
        # We'll use it to track directional movement
        gyro_x = sample['gyro_x']
        gyro_y = sample['gyro_y']

        if DEBUG_IMU:
            print(f"Gyro: X={gyro_x:.3f}, Y={gyro_y:.3f}")

        # Convert gyro to velocity with scaling
        target_vel_x = -gyro_y * MOTION_SENSITIVITY  # Y rotation -> X movement (inverted)
        target_vel_y = -gyro_x * MOTION_SENSITIVITY  # X rotation -> Y movement (inverted)

        # Apply exponential smoothing to reduce jitter
        self.velocity[0] = SMOOTHING * self.velocity[0] + (1 - SMOOTHING) * target_vel_x
        self.velocity[1] = SMOOTHING * self.velocity[1] + (1 - SMOOTHING) * target_vel_y

        # Apply dead zone to ignore very small movements (noise)
        dead_zone = 0.05
        if abs(self.velocity[0]) < dead_zone:
            self.velocity[0] = 0
        if abs(self.velocity[1]) < dead_zone:
            self.velocity[1] = 0

        # Clamp velocity to prevent jumps
        max_velocity = 5.0
        self.velocity[0] = max(-max_velocity, min(max_velocity, self.velocity[0]))
        self.velocity[1] = max(-max_velocity, min(max_velocity, self.velocity[1]))

        if DEBUG_IMU and (abs(self.velocity[0]) > 0.01 or abs(self.velocity[1]) > 0.01):
            print(f"Velocity: X={self.velocity[0]:.3f}, Y={self.velocity[1]:.3f}")

        # Update position
        self.current_pos[0] += self.velocity[0]
        self.current_pos[1] += self.velocity[1]

        # Keep position within bounds
        self.current_pos[0] = max(0, min(CANVAS_WIDTH, self.current_pos[0]))
        self.current_pos[1] = max(0, min(CANVAS_HEIGHT, self.current_pos[1]))

        # Add to trail only if we moved significantly
        if abs(self.velocity[0]) > 0.01 or abs(self.velocity[1]) > 0.01:
            self.trail.append(tuple(self.current_pos))

    def enter_motion_mode(self):
        """Enter motion mode and clear canvas"""
        self.motion_mode = True
        self.trail.clear()
        self.clear_canvas()
        self.current_pos = [CANVAS_WIDTH // 2, CANVAS_HEIGHT // 2]
        self.velocity = [0.0, 0.0]  # Reset velocity
        self.status_label.config(text="MOTION MODE", fg='lime')
        print("Motion mode: ACTIVE")

        # Set LEDs to red
        if self.mcw:
            asyncio.create_task(self.mcw.led_on(255, 0, 0))

    def exit_motion_mode(self):
        """Exit motion mode"""
        self.motion_mode = False
        self.status_label.config(text="Hold all buttons to start", fg='white')
        print("Motion mode: INACTIVE")

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
