from __future__ import annotations

import voluptuous as vol

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


from .config_flow import ConfigFlow


class IssueChangePassword(RepairsFlow):
    """Handler for an issue fixing flow."""

    def __init__(self, hass, data) -> None:
        """Create flow."""

        self._hass: HomeAssistant = hass
        self._config = data["config_data"]
        self._entry_id = data["entry_id"]
        super().__init__()

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""

        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        errors = {}
        if user_input is not None:
            data = self._config
            data["password"] = user_input["password"]
            flow = ConfigFlow()
            flow.hass = self._hass
            errors, _session_temp = await flow.validate_login(data)

            if not errors:
                entry = self.hass.config_entries.async_get_entry(self._entry_id)
                self.hass.config_entries.async_update_entry(entry, data=data)
                return self.async_create_entry(title="", data={})

            errors["base"] = next(iter(errors.values()))

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Required("password"): str,
                }
            ),
            errors=errors,
        )


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str | int | float | None] | None,
) -> RepairsFlow:
    """Create flow."""
    return IssueChangePassword(hass, data)
