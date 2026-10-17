# Setup and options

[English quick start](../README.md) | [한국어 빠른 시작](../README.ko.md)

Install the integration as described in the quick start. Discovery accepts connectable
`MCW-*` wand advertisements and `MCB-*` box advertisements. The manual config flow
lists supported devices already discovered by Home Assistant; it does not ask you to
enter an arbitrary MAC address. Register the wand and box separately if you use both.

## Bluetooth and first connection

Charge and power on the wand using its normal device controls; keep the box powered
and wake it according to its device instructions. Confirm that Home Assistant sees
the corresponding `MCW-*` or `MCB-*` advertisement before adding the integration.
Exact wake procedures and firmware compatibility have not been independently tested
in this adoption, so the device instructions remain the source for those steps.

Use an available local Bluetooth adapter or a connectable ESPHome proxy. See the
[Bluetooth proxy setup](https://github.com/eigger/hass-repo-standards/blob/main/docs/bluetooth.md)
for board revisions, network setup and recommended hardware. Keep default scan timing
initially. `bluetooth_proxy.active: true` enables GATT connections;
`esp32_ble_tracker.scan_parameters.active` controls scan responses. These serve
different purposes, and passive scanning alone does not imply GATT is unavailable.

Close the official app or other BLE clients if they hold the device connection.
This integration exposes no PIN, pairing or bonding setup step. The wand/box protocol
initialization runs after connecting; finding an advertisement does not verify that
initialization or a subsequent command succeeded. Pairing between a physical box and
its wand is distinct from adding either device to Home Assistant; no UI action is
provided to change that physical pairing.

Enable the device's **Connect** switch before receiving spells or issuing actions.
A connection is kept until disconnection or unload; do not assume an unlimited
proxy slot pool or guaranteed automatic reconnection. If disconnected, wake the
device and turn **Connect** on again. For built-in wand spells, leave **Spell Tracking** off: native recognized spells
arrive through the **Spell** sensor without an external model. For the optional
server/IMU/Spell Canvas path, prepare the compatible server and model first, then
enable **Spell Tracking**. The current switch starts IMU only after detector
initialization succeeds. After a reconnect, check its actual state.

## Integration options

Open the integration's options from **Settings → Devices & services**.

| Option | Default | Meaning |
|---|---|---|
| TFLite Server URL | `http://b5e3f765-tflite-server:8000` | Address of the separately installed recognition server; use a reachable URL for your deployment. |
| Spell Timeout | `0` seconds | Nonnegative time until a detected spell resets to `awaiting`; `0` disables the timeout. |

The server and a compatible `model.tflite` are optional external components for
the server recognition/Spell Canvas path. They are not needed for native wand
spells, LED/vibration actions or button automations. The model is not publicly
supplied. See [Spell Canvas](user-guide.md#spell-canvas) for prerequisites, grip/release
behavior, a dashboard example and the original server screenshots.

## Entities and actions

Wands expose battery, spell, buttons, calibration, connection, casting color, alias
and Spell Canvas features. Boxes expose their own battery/connection and box status;
they do not provide a wand IMU or vibration motor. Use the device page to find your
actual entity IDs; IDs vary with the address and registry customization.

Actions are `magic_caster_wand.vibrate`, `set_led`, `clear_leds`, `play_spell` and
`send_macro`. Choose a target entity belonging to the intended device. The box has
one LED group (`TIP`) and ignores vibration macro commands. A single wand vibration
has the firmware's approximately 800 ms pulse regardless of the requested duration.
See [the complete action reference](user-guide.md#available-services) and the
[gesture gallery](user-guide.md#spell-gestures). Avoid overlapping macro sequences
while diagnosing transmission problems; a retry may repeat an effect already applied.
