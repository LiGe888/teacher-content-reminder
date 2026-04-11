from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from urllib.parse import urlencode, urlparse, parse_qsl, urlunparse
from urllib.request import Request, urlopen


class DingTalkBotClient:
    def __init__(self, webhook_url: str, secret: str | None = None, timeout: int = 20) -> None:
        self.webhook_url = webhook_url
        self.secret = secret
        self.timeout = timeout

    def send_markdown(self, title: str, text: str) -> dict[str, object]:
        signed_url = self._signed_url()
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "title": title,
                "text": text,
            },
        }
        request = Request(
            signed_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
            return json.loads(body)

    def _signed_url(self) -> str:
        if not self.secret:
            return self.webhook_url
        timestamp = str(round(time.time() * 1000))
        sign_input = f"{timestamp}\n{self.secret}".encode("utf-8")
        sign = base64.b64encode(
            hmac.new(self.secret.encode("utf-8"), sign_input, hashlib.sha256).digest()
        ).decode("utf-8")
        parsed = urlparse(self.webhook_url)
        query = dict(parse_qsl(parsed.query, keep_blank_values=True))
        query["timestamp"] = timestamp
        query["sign"] = sign
        return urlunparse(parsed._replace(query=urlencode(query)))
