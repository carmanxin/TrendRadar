"""Desktop application exception hierarchy."""


class DesktopError(Exception):
    """Base for all desktop-layer errors."""

    code: str = "desktop_error"

    def __init__(self, message: str = ""):
        super().__init__(message or self.__class__.__name__)


class ConfigError(DesktopError):
    code = "config_error"


class PortInUseError(DesktopError):
    code = "port_in_use"


class RunAlreadyActiveError(DesktopError):
    code = "run_already_active"


class ResourceMissingError(DesktopError):
    """PyInstaller bundle resource could not be located."""
    code = "resource_missing"