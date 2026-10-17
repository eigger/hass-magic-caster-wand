# Magic Caster Wand

<!-- hass-standards:badges:start -->
[![HACS Custom](https://img.shields.io/badge/HACS-Custom-41BDF5?style=flat-square)](#installation)
[![Release](https://img.shields.io/github/v/release/eigger/hass-magic-caster-wand?style=flat-square)](https://github.com/eigger/hass-magic-caster-wand/releases)
[![Home Assistant minimum](https://img.shields.io/badge/HA-%E2%89%A5%202025.4.0-41BDF5?style=flat-square)](hacs.json)
[![Tests](https://img.shields.io/github/actions/workflow/status/eigger/hass-magic-caster-wand/tests.yml?branch=master&style=flat-square&label=Tests)](https://github.com/eigger/hass-magic-caster-wand/actions/workflows/tests.yml)
[![Validate](https://img.shields.io/github/actions/workflow/status/eigger/hass-magic-caster-wand/validate.yml?branch=master&style=flat-square&label=Validate)](https://github.com/eigger/hass-magic-caster-wand/actions/workflows/validate.yml)
[![License](https://img.shields.io/github/license/eigger/hass-magic-caster-wand?style=flat-square)](LICENSE)
[![Analytics reporting installs](https://img.shields.io/badge/dynamic/json?style=flat-square&color=41BDF5&label=Usage&query=%24.magic_caster_wand.total&url=https%3A%2F%2Fanalytics.home-assistant.io%2Fcustom_integrations.json)](https://analytics.home-assistant.io/)
<!-- hass-standards:badges:end -->

**English** | [한국어](README.ko.md)

A HACS custom integration connecting Harry Potter Magic Caster Wands and their boxes to Home Assistant over Bluetooth. Trigger automations from spells and buttons, control LEDs and vibration, and visualize wand movements.

## Supported devices and requirements

- Wand models: **Defiant, Loyal and Honourable**; Magic Caster Box support is also included.
- Home Assistant **2025.4.0 or later**, HACS or a manual installation, and a connectable Bluetooth adapter or ESPHome Bluetooth proxy.
- Use a charged, awake device within Bluetooth range. Proxy connections require `bluetooth_proxy.active: true`; see [shared Bluetooth setup and hardware guidance (Korean)](https://github.com/eigger/hass-repo-standards/blob/main/docs/bluetooth.md).

## Installation

1. In HACS, add `https://github.com/eigger/hass-magic-caster-wand` as a custom **Integration** repository and download **Magic Caster Wand**. For manual installation, copy only `custom_components/magic_caster_wand` into your configuration's `custom_components` directory.
2. Restart Home Assistant. Open **Settings → Devices & services → Add integration → Magic Caster Wand**, or confirm its Bluetooth discovery.
3. Select your awake wand or box and enable its **Connect** switch before receiving spells or sending commands. Enable **Spell Tracking** for wand movement visualization.

See [setup and options](docs/setup.md) for the TFLite URL, spell timeout and connection details.

## Example

Replace the entity IDs with yours. Triggering on `last_updated` also handles repeated casts of the same spell.

```yaml
triggers:
  - trigger: state
    entity_id: sensor.mcw_example_spell
    attribute: last_updated
conditions:
  - condition: state
    entity_id: sensor.mcw_example_spell
    state: Lumos
actions:
  - action: light.turn_on
    target:
      entity_id: light.example
```

## Important limitations

A single vibration command produces a firmware-controlled pulse of about 800 ms, regardless of its duration parameter. Spell recognition using TFLite requires a separate server and compatible `model.tflite`; that model is **not publicly provided**. Hardware/proxy combinations were not newly tested during this standards adoption. See [troubleshooting](docs/troubleshooting.md).

The Usage badge counts HA Analytics participating installations that opted into reporting. Missing data or a failed lookup does not mean zero installations.

## Documentation

- [Setup and options (English)](docs/setup.md)
- [Full user guide, gesture gallery, Spell Canvas, actions and automation example (English)](docs/user-guide.md)
- [Connection troubleshooting and diagnostics (English)](docs/troubleshooting.md)
- [Development, real HA testing and dependencies (English)](CONTRIBUTING.md)
- [Standards adoption and verification record (Korean)](STANDARDS.md)

## Support and license

Report bugs in [Issues](https://github.com/eigger/hass-magic-caster-wand/issues); use [Discussions](https://github.com/eigger/hass-magic-caster-wand/discussions) for questions and suggestions. Licensed under [MIT](LICENSE).
