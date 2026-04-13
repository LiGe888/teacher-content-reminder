from __future__ import annotations

import json
from urllib.request import Request, urlopen


class WeComBotClient:
    def __init__(self, webhook_url: str, timeout: int = 20) -> None:
        self.webhook_url = webhook_url
        self.timeout = timeout

    def send_markdown(self, content: str) -> dict[str, object]:
        payload = {
            "msgtype": "markdown",
            "markdown": {
                "content": content,
            },
        }
        request = Request(
            self.webhook_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
            return json.loads(body)
