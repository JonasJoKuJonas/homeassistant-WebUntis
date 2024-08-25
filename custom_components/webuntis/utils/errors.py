from homeassistant.exceptions import HomeAssistantError


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""


class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""


class BadCredentials(HomeAssistantError):
    """Error to indicate there are bad credentials."""


class SchoolNotFound(HomeAssistantError):
    """Error to indicate the school is not found."""


class NameSplitError(HomeAssistantError):
    """Error to indicate the name format is wrong."""


class StudentNotFound(HomeAssistantError):
    """Error to indicate there is no student with this name."""


class TeacherNotFound(HomeAssistantError):
    """Error to indicate there is no teacher with this name."""


class ClassNotFound(HomeAssistantError):
    """Error to indicate there is no class with this name."""


class NoRightsForTimetable(HomeAssistantError):
    """Error to indicate there is no right for timetable."""
