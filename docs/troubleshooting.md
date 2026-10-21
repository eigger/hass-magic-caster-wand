# Troubleshooting

[README](../README.md) | **English** | [한국어](troubleshooting.ko.md) | [Setup](setup.md)

## Common troubleshooting

Start with the [common Bluetooth troubleshooting](https://github.com/eigger/blesession/blob/main/docs/troubleshooting.md).
For proxy setup and Home Assistant registration, use the [Bluetooth proxy guide](https://github.com/eigger/blesession/blob/main/docs/bluetooth.md).
It includes proxy firmware, board revisions, connection slots, range and network
checks. This integration's device-specific checks are below. No physical
wand/box, firmware or adapter/proxy combination was newly validated for this adoption.

## Device-specific checks

Charge and wake Defiant, Loyal or Honourable wands and the Magic Caster Box using
their own instructions. Close other BLE apps holding the connection and add the
wand and box separately. This integration offers no PIN/bonding input; protocol
initialization is handled by the device session. Persistent connections consume
slots. Automatic reconnection and retries are not guaranteed after every failure.
Check actual completion before repeating a partly executed LED/vibration macro.

## Symptoms and actions

| Symptom | Failing stage | Checks | Action |
|---|---|---|---|
| No devices found | Discovery | Charge/power and wake the device using its own instructions; check for `MCW-*` or `MCB-*` in HA Bluetooth. | Move it near the adapter/proxy and verify the proxy is online. The manual flow only lists devices HA has already discovered. |
| Discovery works but Connect fails | Connection | Advertisement reception is distinct from GATT connection, protocol initialization and writing. | Confirm a connectable path and `bluetooth_proxy.active: true`, close other BLE clients, and check available connection slots. No PIN/bonding input is offered by this integration. |
| Connection closes or commands stop working | Transport loss | Check battery, actual adapter/proxy path, distance, proxy power and network interruptions. | Wake the device and enable Connect again. Persistent connections consume slots; automatic reconnect after every failure is not guaranteed. |
| Connected but no spells | Session / spell reporting | Confirm the wand's Connect state. | Use its normal spell-casting controls; enable Spell Tracking for IMU/Canvas. For TFLite recognition, check server reachability and model availability. The model is not distributed here. |
| Spell Tracking goes off | Session / IMU streaming | It reflects actual tracking state. | Inspect the connection and server, then enable tracking again. A reconnect that cannot restart streaming must not be treated as successful tracking. |
| Box differs from wand | Device capabilities | Add each device separately. | The box exposes lid, USB/wand presence and a single TIP LED; it has no vibration motor or IMU stream. Its paired-wand address is not a user-configurable HA pairing key. |
| Vibration duration seems ignored | Command completion | The firmware emits a fixed approximately 800 ms pulse for one command. | Closely spaced buzz packets can extend it; this is a firmware limit, not a connection timeout. |
| LEDs/macros partly execute | Transfer / completion | Check Last Failure and the device's actual LEDs before resending. | A returned write does not necessarily confirm completion of the entire effect; repeating a macro may duplicate effects. |

## Diagnostics and logs

Open **Settings → Devices & services → Magic Caster Wand → device**, then inspect
its diagnostic entities. If a diagnostic entity is disabled, enable it in the
entity settings. In **Developer tools → States**, inspect the corresponding state
and attributes:

- **Connection Duration**: duration and attributes of the latest recorded connect operation.
- **Failure Count**: in-memory recorded failure count; it is not a lifetime hardware counter.
- **Last Failure**: retained failure timestamp and report attributes. A later successful
  operation does not erase the retained failure, so compare timestamps.
- **Connected** and **Connect**: the device connection state. Check actual spell/LED
  behavior separately from connection state.

Reports retain structured fields such as `failed_stage`, `likely_cause_key`,
`via_type`, `rssi`, `paths`, `via_unconfirmed` and numeric timings when available.
The `error` field contains the exception class only. Raw exception messages,
proxy/address identifiers, `via`, `failed_detail` and arbitrary backend metadata
are removed before the report is retained. Advertisement reception and signal strength
do not prove which path carried the connection.

In this integration, `subscribe` and `notification` map to the session stage,
`initialize` maps to auth, and `transfer` maps to transfer. An auth-stage report can
therefore describe protocol initialization rather than a user-entered password failure.
Use the stage, cause key, exception class and observed behavior together when
choosing the next action.

The actual logger namespace is `custom_components.magic_caster_wand`, including
device submodules. For additional logs, enable debug logging for the integration on its HA integration
page, reproduce once, then disable logging. Check the automation trace if an action
was triggered by an automation. There is no dedicated integration diagnostics-download
endpoint; use the actual entity reports and relevant HA logs.

## If the problem persists

Use the [existing Issues](https://github.com/eigger/hass-magic-caster-wand/issues)
and follow its reporting instructions.

Include HA/integration versions, ESPHome and blesession versions if known, wand/box model and
firmware if available, adapter/proxy model/revision and firmware, local or remote
path, failure time, report stage/error, reproduction steps and last known success.
Describe the failed attempt separately from a later successful attempt. State whether
other apps were connected and whether a command partly executed.

Before posting publicly, remove MAC/Bluetooth addresses, device IDs, serial numbers,
local IPs/hostnames, proxy names, location details, tokens and other identifying data
from entity attributes, traces and logs. Use stable placeholders if comparing paths.
