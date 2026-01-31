"""Constants for Magic Caster Wand BLE integration."""

DOMAIN = "magic_caster_wand"
MANUFACTURER = "Warner Bros. Entertainment Inc."
DEFAULT_SCAN_INTERVAL = 300
CONF_TFLITE_URL = "tflite_url"
DEFAULT_TFLITE_URL = "http://b5e3f765-tflite-server:8000"
CONF_SPELL_TIMEOUT = "spell_timeout"
DEFAULT_SPELL_TIMEOUT = 0

# Casting LED color options (name -> RGB tuple)
CASTING_LED_COLORS = {
    "White": (255, 255, 255),
    "Red": (255, 0, 0),
    "Green": (0, 255, 0),
    "Blue": (0, 0, 255),
    "Yellow": (255, 255, 0),
    "Cyan": (0, 255, 255),
    "Magenta": (255, 0, 255),
    "Orange": (255, 165, 0),
    "Purple": (128, 0, 128),
}
DEFAULT_CASTING_LED_COLOR = "White"

# Dispatcher signals
SIGNAL_SPELL_MODE_CHANGED = f"{DOMAIN}_spell_mode_changed"
