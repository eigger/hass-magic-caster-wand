# hass-magic-caster-wand
Magic Caster Wand Home Assistant Integration

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

## Built-in Spell Gestures for the Wand
<table>
  <tr>
    <td colspan="2" align="center">
      <img width="940" alt="mcw" src="./docs/images/default_spell.png" />
    </td>
  </tr>
</table>


## Spell Gestures
<table>
  <tr>
    <td align="center"><b>Aberto</b><br/><img src="./docs/gestures/aberto.png" width="180"/></td>
    <td align="center"><b>Accio</b><br/><img src="./docs/gestures/accio.png" width="180"/></td>
    <td align="center"><b>Aguamenti</b><br/><img src="./docs/gestures/aguamenti.png" width="180"/></td>
    <td align="center"><b>Alohomora</b><br/><img src="./docs/gestures/alohomora.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Anteoculatia</b><br/><img src="./docs/gestures/anteoculatia.png" width="180"/></td>
    <td align="center"><b>Appare Vestigium</b><br/><img src="./docs/gestures/appare_vestigium.png" width="180"/></td>
    <td align="center"><b>Arania Exumai</b><br/><img src="./docs/gestures/arania_exumai.png" width="180"/></td>
    <td align="center"><b>Ascendio</b><br/><img src="./docs/gestures/ascendio.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Bombarda</b><br/><img src="./docs/gestures/bombarda.png" width="180"/></td>
    <td align="center"><b>Brachiabindo</b><br/><img src="./docs/gestures/brachiabindo.png" width="180"/></td>
    <td align="center"><b>Calvorio</b><br/><img src="./docs/gestures/calvorio.png" width="180"/></td>
    <td align="center"><b>Cantis</b><br/><img src="./docs/gestures/cantis.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Colloportus</b><br/><img src="./docs/gestures/colloportus.png" width="180"/></td>
    <td align="center"><b>Colloshoo</b><br/><img src="./docs/gestures/colloshoo.png" width="180"/></td>
    <td align="center"><b>Colovaria</b><br/><img src="./docs/gestures/colovaria.png" width="180"/></td>
    <td align="center"><b>Confringo</b><br/><img src="./docs/gestures/confringo.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Confundo</b><br/><img src="./docs/gestures/confundo.png" width="180"/></td>
    <td align="center"><b>Densaugeo</b><br/><img src="./docs/gestures/densaugeo.png" width="180"/></td>
    <td align="center"><b>Entomorphis</b><br/><img src="./docs/gestures/entomorphis.png" width="180"/></td>
    <td align="center"><b>Evanesco</b><br/><img src="./docs/gestures/evanesco.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Expecto Patronum</b><br/><img src="./docs/gestures/expecto_patronum.png" width="180"/></td>
    <td align="center"><b>Expelliarmus</b><br/><img src="./docs/gestures/expelliarmus.png" width="180"/></td>
    <td align="center"><b>Expulso</b><br/><img src="./docs/gestures/expulso.png" width="180"/></td>
    <td align="center"><b>Finestra</b><br/><img src="./docs/gestures/finestra.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Finite</b><br/><img src="./docs/gestures/finite.png" width="180"/></td>
    <td align="center"><b>Flagrate</b><br/><img src="./docs/gestures/flagrate.png" width="180"/></td>
    <td align="center"><b>Flipendo</b><br/><img src="./docs/gestures/flipendo.png" width="180"/></td>
    <td align="center"><b>Fulgari</b><br/><img src="./docs/gestures/fulgari.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Glacius</b><br/><img src="./docs/gestures/glacius.png" width="180"/></td>
    <td align="center"><b>Herbivicus</b><br/><img src="./docs/gestures/herbivicus.png" width="180"/></td>
    <td align="center"><b>Immobulus</b><br/><img src="./docs/gestures/immobulus.png" width="180"/></td>
    <td align="center"><b>Impedimenta</b><br/><img src="./docs/gestures/impedimenta.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Incarcerous</b><br/><img src="./docs/gestures/incarcerous.png" width="180"/></td>
    <td align="center"><b>Incendio</b><br/><img src="./docs/gestures/incendio.png" width="180"/></td>
    <td align="center"><b>Lumos</b><br/><img src="./docs/gestures/lumos.png" width="180"/></td>
    <td align="center"><b>Lumos Maxima</b><br/><img src="./docs/gestures/lumos_maxima.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Melefors</b><br/><img src="./docs/gestures/melefors.png" width="180"/></td>
    <td align="center"><b>Meteolojinx</b><br/><img src="./docs/gestures/meteolojinx.png" width="180"/></td>
    <td align="center"><b>Mucus Ad Nauseum</b><br/><img src="./docs/gestures/mucus_ad_nauseum.png" width="180"/></td>
    <td align="center"><b>Nox</b><br/><img src="./docs/gestures/nox.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Orchideous</b><br/><img src="./docs/gestures/orchideous.png" width="180"/></td>
    <td align="center"><b>Petrificus Totalus</b><br/><img src="./docs/gestures/petrificus_totalus.png" width="180"/></td>
    <td align="center"><b>Piertotum Locomotor</b><br/><img src="./docs/gestures/piertotum_locomotor.png" width="180"/></td>
    <td align="center"><b>Protego</b><br/><img src="./docs/gestures/protego.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Quietus</b><br/><img src="./docs/gestures/quietus.png" width="180"/></td>
    <td align="center"><b>Reducto</b><br/><img src="./docs/gestures/reducto.png" width="180"/></td>
    <td align="center"><b>Reparo</b><br/><img src="./docs/gestures/reparo.png" width="180"/></td>
    <td align="center"><b>Revelio</b><br/><img src="./docs/gestures/revelio.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Rictusempra</b><br/><img src="./docs/gestures/rictusempra.png" width="180"/></td>
    <td align="center"><b>Riddikulus</b><br/><img src="./docs/gestures/riddikulus.png" width="180"/></td>
    <td align="center"><b>Salvio Hexia</b><br/><img src="./docs/gestures/salvio_hexia.png" width="180"/></td>
    <td align="center"><b>Scourgify</b><br/><img src="./docs/gestures/scourgify.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Silencio</b><br/><img src="./docs/gestures/silencio.png" width="180"/></td>
    <td align="center"><b>Stupefy</b><br/><img src="./docs/gestures/stupefy.png" width="180"/></td>
    <td align="center"><b>The Cheering Charm</b><br/><img src="./docs/gestures/the_cheering_charm.png" width="180"/></td>
    <td align="center"><b>The Force Spell</b><br/><img src="./docs/gestures/the_force_spell.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>The Hair Thickening Growing Charm</b><br/><img src="./docs/gestures/the_hair_thickening_growing_charm.png" width="180"/></td>
    <td align="center"><b>The Hour Reversal Charm</b><br/><img src="./docs/gestures/the_hour_reversal_charm.png" width="180"/></td>
    <td align="center"><b>The Sleeping Charm</b><br/><img src="./docs/gestures/the_sleeping_charm.png" width="180"/></td>
    <td align="center"><b>The Spell Thickening Charm</b><br/><img src="./docs/gestures/the_spell_thickening_charm.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>The Stretching Jinx</b><br/><img src="./docs/gestures/the_stretching_jinx.png" width="180"/></td>
    <td align="center"><b>Ventus</b><br/><img src="./docs/gestures/ventus.png" width="180"/></td>
    <td align="center"><b>Verdimillious</b><br/><img src="./docs/gestures/verdimillious.png" width="180"/></td>
    <td align="center"><b>Vermillious</b><br/><img src="./docs/gestures/vermillious.png" width="180"/></td>
  </tr>
  <tr>
    <td align="center"><b>Wingardium Leviosa</b><br/><img src="./docs/gestures/wingardium_leviosa.png" width="180"/></td>
    <td></td>
    <td></td>
    <td></td>
  </tr>
</table>


## Spell Canvas
The Spell Canvas provides real-time visualization of your wand's movements.
- **Spell Tracking**: Turn on the **Spell Tracking** switch to start receiving IMU data from the wand.
- **Drawing**: Drawing on the canvas begins automatically when the wand's button is pressed and all button states are detected.
- **Spell Recognition**: To use spell recognition, you must install the [hass-tflite](https://github.com/ificator/hass-tflite) addon. Once the addon is installed use the `Open web UI` button to upload the `model.tflite` file so that it's ready for use. You can update the server address in the configuration settings if you're using a custom fork.
<table>
  <tr>
    <td colspan="2" align="center">
      <img width="722" height="222" alt="image" src="https://github.com/user-attachments/assets/8b896c42-170c-47dc-a7e9-212a4e179563" />
    </td>
    <td colspan="2" align="center">
      <img width="400" height="222" alt="image" src="https://github.com/user-attachments/assets/e8d0baf9-abf9-48b1-b157-c3d5a2679bda" />
    </td>
    <td colspan="2" align="center">
      <img width="411" height="222" alt="image" src="https://github.com/user-attachments/assets/7e8c8c2d-6ead-47a3-9e9a-25f5756ce5f4" />
    </td>
  </tr>
</table>

> [!NOTE]
> The `model.tflite` file is not shared publicly at this time due to potential issues and to ensure compatibility.


<table>
  <tr>
    <td align="center">
      <img src="./docs/images/spell_canvas.png" width="600" alt="Spell Canvas Demo"/>
    </td>
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
