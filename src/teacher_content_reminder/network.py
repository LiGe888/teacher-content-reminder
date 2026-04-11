from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping
from urllib.request import Request, urlopen
from urllib.error import URLError
import socket

try:
    from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
except ImportError as exc:
    raise RuntimeError("tenacity is not installed. Please run `pip install tenacity`.") from exc


DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}


@dataclass(slots=True)
class HttpResponse:
    url: str
    text: str
    headers: Mapping[str, str]
    status_code: int


@retry(
    wait=wait_exponential(multiplier=1, min=2, max=10),
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((URLError, socket.timeout, ConnectionError, TimeoutError)),
    reraise=True
)
def fetch_text(url: str, timeout: int = 20, headers: Mapping[str, str] | None = None) -> HttpResponse:
    merged_headers = dict(DEFAULT_HEADERS)
    if headers:
        merged_headers.update(headers)

    request = Request(url, headers=merged_headers)
    with urlopen(request, timeout=timeout) as response:
        payload = response.read()
        charset = response.headers.get_content_charset() or "utf-8"
        return HttpResponse(
            url=response.geturl(),
            text=payload.decode(charset, errors="replace"),
            headers=dict(response.headers.items()),
            status_code=getattr(response, "status", 200),
        )

