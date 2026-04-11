from __future__ import annotations


class LLMError(RuntimeError):
    def __init__(
        self,
        provider: str,
        message: str,
        *,
        retryable: bool,
        status_code: int | None = None,
        kind: str = "unknown",
    ) -> None:
        super().__init__(message)
        self.provider = provider
        self.retryable = retryable
        self.status_code = status_code
        self.kind = kind


def classify_http_error(provider: str, status_code: int, detail: str) -> LLMError:
    normalized = detail.lower()
    if status_code in {400, 404, 422}:
        return LLMError(provider, f"Invalid request for provider '{provider}': {detail}", retryable=False, status_code=status_code, kind="invalid_request")
    if status_code in {401, 403}:
        return LLMError(provider, f"Authentication failed for provider '{provider}': {detail}", retryable=False, status_code=status_code, kind="auth")
    if status_code == 402 or "insufficient balance" in normalized or "quota exceeded" in normalized:
        return LLMError(
            provider,
            f"Billing problem for provider '{provider}': {detail}",
            retryable=False,
            status_code=status_code,
            kind="billing",
        )
    if status_code == 429:
        return LLMError(provider, f"Rate limited by provider '{provider}': {detail}", retryable=True, status_code=status_code, kind="rate_limit")
    if 500 <= status_code <= 599:
        return LLMError(provider, f"Provider '{provider}' server error {status_code}: {detail}", retryable=True, status_code=status_code, kind="server_error")
    if "timeout" in normalized or "temporar" in normalized:
        return LLMError(provider, f"Transient provider error from '{provider}': {detail}", retryable=True, status_code=status_code, kind="transient")
    return LLMError(provider, f"Provider '{provider}' request failed with HTTP {status_code}: {detail}", retryable=False, status_code=status_code, kind="http_error")


def classify_network_error(provider: str, detail: str) -> LLMError:
    normalized = detail.lower()
    retryable = any(
        token in normalized
        for token in (
            "timed out",
            "temporary",
            "temporar",
            "reset",
            "unreachable",
            "refused",
            "name or service not known",
            "eof occurred",
            "ssl",
        )
    )
    kind = "network" if retryable else "client_network"
    return LLMError(provider, f"Provider '{provider}' network error: {detail}", retryable=retryable, kind=kind)


def response_parse_error(provider: str, detail: str) -> LLMError:
    return LLMError(provider, f"Provider '{provider}' returned an unreadable response: {detail}", retryable=False, kind="response_parse")
