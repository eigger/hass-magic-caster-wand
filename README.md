<!-- hass-standards:header:start -->
# Magic Caster Wand

Cast **Lumos** to turn on a room light, or **Nox** to turn it off. This HACS custom integration connects Harry Potter Magic Caster Wands and their boxes to Home Assistant over Bluetooth, turning spells and button presses into automation triggers and letting Home Assistant send LED and vibration effects back to the wand.

**English** | [한국어](README.ko.md)

<!-- hass-standards:badges:start -->
[![Release](https://img.shields.io/github/v/release/eigger/hass-magic-caster-wand?style=flat)](https://github.com/eigger/hass-magic-caster-wand/releases)
[![HACS Default](https://img.shields.io/badge/HACS-Default-41BDF5?style=flat)](#installation)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.4.0-41BDF5?style=flat)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-magic-caster-wand/tests.yml?branch=master&style=flat&label=Tests)](https://github.com/eigger/hass-magic-caster-wand/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-magic-caster-wand/validate.yml?branch=master&style=flat&label=Validate)](https://github.com/eigger/hass-magic-caster-wand/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-magic-caster-wand?style=flat)](LICENSE)
[![Downloads](https://img.shields.io/github/downloads/eigger/hass-magic-caster-wand/latest/total?style=flat&color=41BDF5&label=Downloads)](https://github.com/eigger/hass-magic-caster-wand/releases)
<!-- hass-standards:badges:end -->
<!-- hass-standards:header:end -->

<img src="docs/images/mcw.png" width="720" alt="Magic Caster Wand in Home Assistant" />

<table>
  <tr>
    <td align="center"><img src="docs/images/device_on.gif" width="140" alt="Wand controlling a device" /><br/><b>Control a device with a spell</b></td>
    <td align="center"><img src="docs/images/light_on.gif" width="360" alt="Wand turning on a light" /><br/><b>Turn on a light with your wand</b></td>
  </tr>
</table>

## What you can do

**Connect the wand → perform a built-in gesture → its Spell sensor reports the spell → your automation controls a light or another HA device.** The wand recognizes its built-in gestures itself; this basic route does **not** require a TFLite server or model.

| Feature | How it works in Home Assistant |
|---|---|
| Spell automations | The **Spell** sensor reports names such as `Lumos` and `Nox`; use them to trigger your own actions. |
| Buttons and device status | Wand button binary sensors and battery sensors let you build other triggers and monitor the device. |
| Wand effects | Send predefined effects, set LED colors, clear LEDs, vibrate, or compose a macro. |
| Optional movement tracking | **Spell Tracking** streams the wand's IMU data for **Spell Canvas** and server-based recognition; it needs separate setup below. |
| Magic Caster Box | Monitor lid, USB and wand-presence status, battery and connection; control its single `TIP` LED. It has no vibration motor or wand IMU. Add the box separately from the wand. |

## Supported devices and requirements

- Wand models: **Defiant, Loyal and Honourable**; Magic Caster Box support is also included.
- Home Assistant **2025.4.0 or later**, HACS or a manual installation, and a connectable Bluetooth adapter or ESPHome Bluetooth proxy.
- Charge and wake the device, keep it in Bluetooth range, and close other apps if they hold its connection. A proxy needs `bluetooth_proxy.active: true` for GATT connections; active scanning is a separate setting. See [Bluetooth proxy setup](https://github.com/eigger/blesession/blob/main/docs/bluetooth.md).

## Installation

<!-- hass-standards:installation:start -->
[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=eigger&repository=hass-magic-caster-wand)
<!-- hass-standards:installation:end -->

1. In HACS, search for **Magic Caster Wand** and download it, or use the button above. It is included in the HACS default repository list. For manual installation, copy only `custom_components/magic_caster_wand` into your configuration's `custom_components` directory.
2. Restart Home Assistant. Open **Settings → Devices & services → Add integration → Magic Caster Wand**, or confirm its Bluetooth discovery.
3. Select your awake wand or box. On its device page, turn on **Connect** before receiving spells or sending effects. Finding a Bluetooth advertisement alone does not confirm a working connection.

For your first check, leave **Spell Tracking off**, confirm **Connected** is on, and cast a built-in gesture below using the wand's normal casting grip. Open the **Spell** entity and check that its value changes. If it does not, check the connection and button states before adding an automation. The spell value can remain visible after a disconnect, so a previously displayed spell is not proof of a current connection.

## Try the built-in gestures

These are the wand's native gesture reference and two examples to start with. Follow the arrows and the wand's normal casting instructions.

<img src="docs/images/default_spell.png" width="560" alt="Built-in Magic Caster Wand gesture reference" />

<table>
  <tr>
    <td align="center"><b>Lumos</b><br/><img src="docs/gestures/lumos.png" width="130" alt="Lumos gesture" /></td>
    <td align="center"><b>Nox</b><br/><img src="docs/gestures/nox.png" width="130" alt="Nox gesture" /></td>
  </tr>
</table>

The [full gesture gallery](docs/user-guide.md#spell-gestures) preserves the remaining reference images. A reference image alone does not mean that every listed gesture is recognized by the wand's native firmware or an available external model.

## Make Lumos turn a light on and Nox turn it off

Create an automation in Home Assistant and use this YAML, replacing **every occurrence** of `sensor.mcw_example_spell` and the light IDs with yours. Find the actual Spell entity on the wand's device page. You can replace the light actions with actions for another HA device.

```yaml
alias: Wand — Lumos and Nox
triggers:
  - trigger: state
    entity_id: sensor.mcw_example_spell
    attribute: last_updated
actions:
  - choose:
      - conditions: "{{ trigger.to_state.state | lower == 'lumos' }}"
        sequence:
          - action: light.turn_on
            target:
              entity_id: light.example
      - conditions: "{{ trigger.to_state.state | lower == 'nox' }}"
        sequence:
          - action: light.turn_off
            target:
              entity_id: light.example
mode: single
```

The conditions normalize spell names to lowercase, so `Lumos` and `lumos` both match. The trigger watches the **`last_updated` attribute**, so casting Lumos twice can trigger twice even when the spell name stays the same. In integration options, **Spell Timeout** resets the reported spell to `awaiting` after the configured seconds; `0` (the default) keeps the last spell until the next update. The example ignores `awaiting` because it only acts on Lumos or Nox.

## Send effects back to the wand

Use **Developer tools → Actions** or an automation to call these actions with a target entity belonging to the intended wand or box:

| Action | Purpose |
|---|---|
| `magic_caster_wand.play_spell` | Play a predefined LED/vibration effect such as `lumos` or `incendio`. This plays an effect; it does not cast a gesture into your automation. |
| `magic_caster_wand.set_led` | Set `group`, `rgb_color` and optional `duration` for a wand LED group. |
| `magic_caster_wand.clear_leds` | Turn off LEDs. |
| `magic_caster_wand.vibrate` | Vibrate the wand; one command produces about **800 ms** regardless of requested duration. |
| `magic_caster_wand.send_macro` | Combine LED changes, delays, buzzes and loops in a custom sequence. |

For example, play the Lumos effect on the wand (replace the target entity):

```yaml
action: magic_caster_wand.play_spell
target:
  entity_id: sensor.mcw_example_spell
data:
  spell: lumos
```

The box has only the `TIP` LED group and ignores vibration macro commands. See [the action reference](docs/user-guide.md#available-services) for the longer descriptions.

## Spell Canvas and optional server recognition

**Spell Canvas** is a camera entity showing the path of a cast, its drawing state and the recognized spell. It is an optional route beyond the wand's built-in spell reports.

<img src="docs/images/spell_canvas.png" width="480" alt="Spell Canvas displaying a wand movement trail" />

1. Set up a compatible [hass-tflite server](https://github.com/ificator/hass-tflite) and load a compatible `model.tflite` through its web UI. Set **TFLite Server URL** in the integration's options to a URL reachable from HA. **The model is not publicly provided by this project.**
2. Connect the wand, then enable **Spell Tracking**. In the current implementation it starts IMU streaming after the remote detector initializes; a missing/unreachable server or model can prevent tracking from starting. Do not assume a model-free drawing fallback.
3. Open the wand's **Spell Canvas** camera. To keep it on a dashboard, edit the dashboard, add a **Picture entity** card and select that camera entity.
4. Hold **all four wand button/touch sensors together**, then move the wand to draw. The canvas shows **TRACKING** while all four are held. Release any one of them to finish the stroke and request recognition; it returns to **READY**. A successful result updates the same Spell sensor used by your automations.
5. Check the actual **Spell Tracking** switch and the canvas status if no path appears. **SERVER OK** records a successful server check during initialization; it does not guarantee recognition of every gesture. Check tracking again after reconnecting.

<img src="docs/images/tflite_server.png" width="560" alt="TFLite server web interface" />

[Server screenshots and the original Spell Canvas walkthrough](docs/user-guide.md#spell-canvas) remain available. Built-in wand spell automations remain the starting point when you do not have the external model.

## Connection help and documentation

Bluetooth discovery, connection and successful command execution are separate stages. If the wand disconnects, wake it and turn **Connect** on again; check proxy slots, distance and other connected apps. Hardware and firmware combinations vary; see [troubleshooting and diagnostic entities](docs/troubleshooting.md).

- [Setup, options and connection details (English)](docs/setup.md)
- [Complete gesture gallery, media, Spell Canvas and action reference (English)](docs/user-guide.md)
- [Development and tests (English)](CONTRIBUTING.md)
- [Standards and verification record (Korean)](STANDARDS.md)

The Downloads badge counts GitHub release asset downloads of the current release, not active installations.

<!-- hass-standards:support:start -->
## Support

- [Issues](https://github.com/eigger/hass-magic-caster-wand/issues): Report bugs or request features.
- [Discussions](https://github.com/eigger/hass-magic-caster-wand/discussions): Ask questions and share your experience.
<!-- hass-standards:support:end -->

<!-- hass-standards:related-projects:start -->
<!-- hass-standards:related-projects:end -->

<!-- hass-standards:license:start -->
## License

Released under the [MIT License](LICENSE).
<!-- hass-standards:license:end -->
