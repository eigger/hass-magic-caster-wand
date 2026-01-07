# hass-magic-caster-wand
Harry Potter: Magic Caster Wand Home Assistant Integration

<table>
  <tr>
    <td colspan="2" align="center">
      <img width="1703" height="851" alt="mcw" src="./docs/images/mcw.png" />
    </td>
  </tr>
  <tr>
    <td align="center" valign="bottom">
      <img width="180"
           alt="Turn on device demo"
           src="./docs/images/device_on.gif" />
      <div style="margin-top:8px;"><b>Turn on Device</b></div>
    </td>
    <td align="center" valign="bottom">
      <img width="550"
           alt="Turn on light demo"
           src="./docs/images/light_on.gif" />
      <div style="margin-top:8px;"><b>Turn on Light</b></div>
    </td>
  </tr>
</table>



## 💬 Feedback & Support

🐞 Found a bug? Let us know via an [Issue](https://github.com/eigger/hass-magic-caster-wand/issues).  
💡 Have a question or suggestion? Join the [Discussion](https://github.com/eigger/hass-magic-caster-wand/discussions)!

## Supported Models
- Defiant
- Loyal
- Honourable

## Installation
1. Install this integration with HACS (adding repository required), or copy the contents of this
repository into the `custom_components/magic_caster_wand` directory.
2. Restart Home Assistant.

## ⚠️ Important Notice
- It is **strongly recommended to use a Bluetooth proxy instead of a built-in Bluetooth adapter**.  
  Bluetooth proxies generally offer more stable connections and better range, especially in environments with multiple BLE devices.
- When using a Bluetooth proxy, it is strongly recommended to **keep the scan interval at its default value**.  
  Changing these values may cause issues with Bluetooth data transmission.
- **bluetooth_proxy:** must always have **active: true**.
  
  Example (recommended configuration with default values):

  ```yaml
  esp32_ble_tracker:
    scan_parameters:
      active: true
  
  bluetooth_proxy:
    active: true

## Spells & Motions
>[!IMPORTANT]
>You must connect to the wand via Bluetooth(Switch) first in order to receive the spell values.

⬆ ⬇ ⬅ ➡ ⬈ ⬉ ⬊ ⬋
| Spell | Motion | Description |
|------|--------|-------------|
| Protego | ⬇ | Downward hand motion (arrow-like) |
| Serpensortia | ⬆ | Upward hand motion |
| Lumos | ⬅ ⬈ ⬊ | Draw a triangular motion: move left, then diagonally up to the right, then straight down |
| ... |  | If you know the spell motion or have an easier way to perform it, please share it here. |

## Spell Cards
<table>
  <tr>
    <td align="center"><b>Cantis</b><br/><img src="./docs/spells/Cantis.png" width="180"/></td>
    <td align="center"><b>Colovaria</b><br/><img src="./docs/spells/Colovaria.png" width="180"/></td>
    <td align="center"><b>Expecto Patronum</b><br/><img src="./docs/spells/Expecto%20Patronum.png" width="180"/></td>
    <td align="center"><b>Expelliarmus</b><br/><img src="./docs/spells/Expelliarmus.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Finite</b><br/><img src="./docs/spells/Finite.png" width="180"/></td>
    <td align="center"><b>Flagrate</b><br/><img src="./docs/spells/Flagrate.png" width="180"/></td>
    <td align="center"><b>Immobulus</b><br/><img src="./docs/spells/Immobulus.png" width="180"/></td>
    <td align="center"><b>Incendio</b><br/><img src="./docs/spells/Incendio.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Lumos Maxima</b><br/><img src="./docs/spells/Lumos%20Maxima.png" width="180"/></td>
    <td align="center"><b>Lumos</b><br/><img src="./docs/spells/Lumos.png" width="180"/></td>
    <td align="center"><b>Meteolojinx</b><br/><img src="./docs/spells/Meteolojinx.png" width="180"/></td>
    <td align="center"><b>Nox</b><br/><img src="./docs/spells/Nox.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Salvio Hexia</b><br/><img src="./docs/spells/Salvio%20Hexia.png" width="180"/></td>
    <td align="center"><b>Silencio</b><br/><img src="./docs/spells/Silencio.png" width="180"/></td>
  </tr>
</table>

## Automation Example
```yaml
alias: Lumos
description: ""
triggers:
  - trigger: state
    entity_id:
      - sensor.mcw_5363f8ea_spell
    attribute: last_updated
conditions: []
actions:
  - choose:
      - conditions:
          - condition: state
            entity_id: sensor.mcw_5363f8ea_spell
            state:
              - Lumos
        sequence:
          - action: light.turn_on
            metadata: {}
            target:
              entity_id: light.esp_kocom_livingroom_light_1
            data: {}
mode: single
```

## References
- [Magic-Caster-Wand-Open-app-ai (whymaxwhy)](https://github.com/whymaxwhy/Magic-Caster-Wand-Open-app-ai.git)
- [OpenCaster (Blues-Hailfire)](https://github.com/Blues-Hailfire/OpenCaster.git)
