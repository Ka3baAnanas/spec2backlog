import httpx

RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
RETRYABLE_PREFIX = "[retryable] "


class ProviderError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, status_code: int | None = None):
        super().__init__(message)
        self.retryable = retryable
        self.status_code = status_code


class ProviderUnavailableError(ProviderError):
    def __init__(self, message: str, *, status_code: int | None = None):
        super().__init__(message, retryable=True, status_code=status_code)


class ProviderConfigurationError(ProviderError):
    def __init__(self, message: str):
        super().__init__(message, retryable=False)


def is_retryable_provider_error(exc: BaseException | None) -> bool:
    if exc is None:
        return False
    if isinstance(exc, ProviderError):
        return exc.retryable
    if isinstance(exc, httpx.RequestError):
        return True
    status = getattr(getattr(exc, "response", None), "status_code", None)
    return status in RETRYABLE_STATUS


def retryable_message(message: str) -> str:
    return f"{RETRYABLE_PREFIX}{message}"


def is_retryable_message(message: str | None) -> bool:
    return str(message or "").startswith(RETRYABLE_PREFIX)
