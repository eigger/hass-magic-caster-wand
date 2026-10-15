"""Link a Magic Caster Box to the wand it is paired with.

The box reports the BLE address of its paired wand, which is the same address
the wand advertises. Home Assistant keeps one device per config entry, so the
two cannot be merged; instead the wand device is made a child of the box device
(``via_device_id``), which shows as "Connected via Magic Caster Box".
"""

import inspect
import logging

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

_ACTIVE_STATES = (ConfigEntryState.LOADED, ConfigEntryState.SETUP_IN_PROGRESS)


_UNPAIRED = "00:00:00:00:00:00"


def normalize_address(address: str | None) -> str | None:
    """Return a comparable form of a BLE address, or None if there is none.

    An all-zero address means the box has no wand paired, so it is no address.
    """
    if not address:
        return None
    address = address.strip().upper()
    return None if address == _UNPAIRED else address


def plan_links(
    boxes: dict[str, str | None],
    wands: dict[str, tuple[str, str | None]],
) -> dict[str, str | None]:
    """Decide which wand devices to re-parent.

    ``boxes`` maps a box device id to the wand address it reports (None while
    unknown). ``wands`` maps a wand address to ``(device id, current parent id)``.
    Returns ``{wand device id: new parent id or None}`` for the changes needed.

    A wand is only unlinked from a box that now reports a different wand. A box
    that has not answered yet, or a wand that was pulled out of the box, never
    removes a link: the box keeps reporting the paired wand when it is removed.
    """
    parent_by_wand = {addr: box_id for box_id, addr in boxes.items() if addr}
    changes: dict[str, str | None] = {}
    for address, (wand_id, current) in wands.items():
        desired = parent_by_wand.get(address)
        if desired is not None:
            if current != desired:
                changes[wand_id] = desired
        elif current in boxes and boxes[current]:
            changes[wand_id] = None
    return changes


async def async_reconcile_links(hass: HomeAssistant) -> None:
    """Make each wand a child of the box that reports it as its paired wand."""
    dev_reg = dr.async_get(hass)
    if "via_device_id" not in inspect.signature(dev_reg.async_update_device).parameters:
        _LOGGER.debug("This Home Assistant cannot link devices by id; skipping box and wand link")
        return

    def device_id(address: str) -> str | None:
        device = dev_reg.async_get_device(connections={(dr.CONNECTION_BLUETOOTH, address)})
        return device.id if device else None

    boxes: dict[str, str | None] = {}
    wand_ids: dict[str, str] = {}
    for entry in hass.config_entries.async_entries(DOMAIN):
        # Home Assistant only marks an entry loaded after its setup returns, and
        # reconcile runs from inside setup, so an entry still setting up counts.
        if entry.state not in _ACTIVE_STATES or not entry.unique_id:
            continue
        runtime_data = getattr(entry, "runtime_data", None)
        if runtime_data is None:
            continue
        address = normalize_address(entry.unique_id)
        dev_id = device_id(entry.unique_id)
        if address is None or dev_id is None:
            continue
        if entry.data.get("device_type", "mcw") == "mcb":
            boxes[dev_id] = normalize_address(getattr(runtime_data.device, "wand_address", None))
        else:
            wand_ids[address] = dev_id

    wands: dict[str, tuple[str, str | None]] = {}
    for address, dev_id in wand_ids.items():
        device = dev_reg.async_get(dev_id)
        wands[address] = (dev_id, device.via_device_id if device else None)

    for wand_id, parent_id in plan_links(boxes, wands).items():
        _LOGGER.debug("Linking wand device %s to box device %s", wand_id, parent_id)
        dev_reg.async_update_device(wand_id, via_device_id=parent_id)
