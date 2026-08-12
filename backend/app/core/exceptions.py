class ConfigurationError(RuntimeError):
    """Raised when an application or integration setting is unavailable."""


class IntegrationNotConfiguredError(ConfigurationError):
    """Raised when code attempts to use a disabled external integration."""


class ExternalServiceError(RuntimeError):
    """Raised when an external provider returns an unusable response."""
