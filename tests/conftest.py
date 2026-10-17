"""Repository fixtures using the real Home Assistant test plugin."""

import pytest


@pytest.fixture(autouse=True)
def custom_integrations(enable_custom_integrations):
    """Allow Home Assistant to discover this custom integration."""
