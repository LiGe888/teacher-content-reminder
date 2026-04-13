from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class WeChatOfficialClient:
    def __init__(
        self,
        appid: str,
        appsecret: str,
        template_id: str,
        timeout: int = 20,
    ) -> None:
        self.appid = appid
        self.appsecret = appsecret
        self.template_id = template_id
        self.timeout = timeout

    def send_template_message(
        self,
        touser: str,
        title: str,
        summary: str,
        source_name: str,
        score_text: str,
        url: str | None = None,
    ) -> dict[str, object]:
        token = self._get_access_token()
        endpoint = f"https://api.weixin.qq.com/cgi-bin/message/template/send?access_token={token}"
        payload = {
            "touser": touser,
            "template_id": self.template_id,
            "data": {
                "first": {"value": title},
                "keyword1": {"value": source_name},
                "keyword2": {"value": score_text},
                "remark": {"value": summary},
            },
        }
        if url:
            payload["url"] = url

        request = Request(
            endpoint,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
            return json.loads(body)

    def _get_access_token(self) -> str:
        query = urlencode(
            {
                "grant_type": "client_credential",
                "appid": self.appid,
                "secret": self.appsecret,
            }
        )
        endpoint = f"https://api.weixin.qq.com/cgi-bin/token?{query}"
        with urlopen(endpoint, timeout=self.timeout) as response:
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
        payload = json.loads(body)
        token = payload.get("access_token")
        if not token:
            raise ValueError(f"Unable to get WeChat Official access token: {payload}")
        return str(token)
