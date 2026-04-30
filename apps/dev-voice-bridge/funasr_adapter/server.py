#!/usr/bin/env python3

from __future__ import annotations

import base64
import json
import os
import shutil
import tempfile
import threading
import traceback
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any


EXTENSION_MAP = {
    "audio/mp4": ".m4a",
    "audio/m4a": ".m4a",
    "audio/mp3": ".mp3",
    "audio/mpeg": ".mp3",
    "audio/wav": ".wav",
    "audio/x-wav": ".wav",
    "audio/webm": ".webm",
    "audio/ogg": ".ogg",
}

LANGUAGE_MAP = {
    "zh": "中文",
    "zh-cn": "中文",
    "zh-hk": "中文",
    "zh-tw": "中文",
    "yue": "中文",
    "en": "英文",
    "en-us": "英文",
    "en-gb": "英文",
    "ja": "日文",
    "ja-jp": "日文",
}


def mime_type_to_suffix(mime_type: str) -> str:
    return EXTENSION_MAP.get((mime_type or "").strip().lower(), ".wav")


def map_language(language: str) -> str:
    normalized = (language or "").strip().lower().replace("_", "-")
    if not normalized or normalized == "auto":
        return ""

    return LANGUAGE_MAP.get(normalized, "")


def extract_text(result: Any) -> str:
    if isinstance(result, dict):
        value = result.get("text")
        if isinstance(value, str):
            return value.strip()

    if isinstance(result, list) and result:
        for item in result:
            text = extract_text(item)
            if text:
                return text

    return ""


@dataclass
class AdapterConfig:
    host: str
    port: int
    model: str
    device: str
    hub: str
    remote_code: str
    trust_remote_code: bool
    vad_model: str
    punc_model: str
    max_single_segment_time: int
    itn: bool
    eager_load: bool

    @classmethod
    def from_env(cls) -> "AdapterConfig":
        return cls(
            host=os.environ.get("FUNASR_ADAPTER_HOST", "127.0.0.1"),
            port=int(os.environ.get("FUNASR_ADAPTER_PORT", "7861")),
            model=os.environ.get("FUNASR_MODEL", "paraformer-zh"),
            device=os.environ.get("FUNASR_DEVICE", "cpu"),
            hub=os.environ.get("FUNASR_HUB", "ms"),
            remote_code=os.environ.get("FUNASR_REMOTE_CODE", ""),
            trust_remote_code=os.environ.get("FUNASR_TRUST_REMOTE_CODE", "1") != "0",
            vad_model=os.environ.get("FUNASR_VAD_MODEL", "fsmn-vad"),
            punc_model=os.environ.get("FUNASR_PUNC_MODEL", "ct-punc"),
            max_single_segment_time=int(os.environ.get("FUNASR_VAD_MAX_SINGLE_SEGMENT_MS", "30000")),
            itn=os.environ.get("FUNASR_ITN", "1") != "0",
            eager_load=os.environ.get("FUNASR_EAGER_LOAD", "0") == "1",
        )


class LazyFunASRTranscriber:
    def __init__(self, config: AdapterConfig) -> None:
        self.config = config
        self._model = None
        self._load_error: str | None = None
        self._lock = threading.Lock()

    @property
    def is_loaded(self) -> bool:
        return self._model is not None

    @property
    def load_error(self) -> str | None:
        return self._load_error

    def warmup(self) -> None:
        self._get_model()

    def transcribe(
        self,
        *,
        audio_bytes: bytes,
        mime_type: str,
        language: str,
        hotwords: list[str] | None = None,
    ) -> dict[str, Any]:
        model = self._get_model()
        suffix = mime_type_to_suffix(mime_type)
        tmp_path = Path(tempfile.mkstemp(prefix="funasr-audio-", suffix=suffix)[1])

        try:
            tmp_path.write_bytes(audio_bytes)

            kwargs: dict[str, Any] = {
                "input": [str(tmp_path)],
                "cache": {},
                "batch_size": 1,
                "itn": self.config.itn,
            }

            language_hint = map_language(language)
            if language_hint:
                kwargs["language"] = language_hint

            if hotwords:
                kwargs["hotwords"] = hotwords

            result = model.generate(**kwargs)
            text = extract_text(result)
            if not text:
                raise RuntimeError("FunASR returned no text.")

            return {
                "text": text,
                "meta": {
                    "model": self.config.model,
                    "device": self.config.device,
                    "hub": self.config.hub,
                    "languageHint": language_hint or "auto",
                },
            }
        finally:
            try:
                tmp_path.unlink(missing_ok=True)
            except OSError:
                pass

    def _get_model(self):
        if self._model is not None:
            return self._model

        with self._lock:
            if self._model is not None:
                return self._model

            try:
                from funasr import AutoModel  # type: ignore
            except Exception as exc:  # pragma: no cover - depends on local env
                self._load_error = (
                    "FunASR is not installed. Create a venv and install "
                    "funasr, torch, torchaudio, and modelscope first. "
                    f"Original import error: {exc}"
                )
                raise RuntimeError(self._load_error) from exc

            kwargs: dict[str, Any] = {
                "model": self.config.model,
                "device": self.config.device,
                "hub": self.config.hub,
                "trust_remote_code": self.config.trust_remote_code,
            }

            if self.config.remote_code:
                kwargs["remote_code"] = self.config.remote_code

            if self.config.vad_model:
                kwargs["vad_model"] = self.config.vad_model
                kwargs["vad_kwargs"] = {
                    "max_single_segment_time": self.config.max_single_segment_time,
                }

            if self.config.punc_model:
                kwargs["punc_model"] = self.config.punc_model

            try:
                self._model = AutoModel(**kwargs)
                self._load_error = None
            except Exception as exc:  # pragma: no cover - depends on local env
                self._load_error = f"Failed to load FunASR model {self.config.model}: {exc}"
                raise RuntimeError(self._load_error) from exc

            return self._model


class FunASRRequestHandler(BaseHTTPRequestHandler):
    server_version = "DevVoiceBridgeFunASR/0.1"

    @property
    def transcriber(self) -> LazyFunASRTranscriber:
        return self.server.transcriber  # type: ignore[attr-defined]

    @property
    def config(self) -> AdapterConfig:
        return self.server.adapter_config  # type: ignore[attr-defined]

    def do_GET(self) -> None:
        if self.path.rstrip("/") == "/healthz":
            self._write_json(
                HTTPStatus.OK,
                {
                    "ok": True,
                    "model": self.config.model,
                    "device": self.config.device,
                    "hub": self.config.hub,
                    "loaded": self.transcriber.is_loaded,
                    "loadError": self.transcriber.load_error,
                    "ffmpegAvailable": shutil.which("ffmpeg") is not None,
                },
            )
            return

        self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})

    def do_POST(self) -> None:
        if self.path.rstrip("/") != "/transcribe":
            self._write_json(HTTPStatus.NOT_FOUND, {"error": "Not found"})
            return

        try:
            payload = self._read_json_body()
        except ValueError as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": str(exc)})
            return

        audio_base64 = str(payload.get("audioBase64") or "").strip()
        mime_type = str(payload.get("mimeType") or "audio/wav").strip()
        language = str(payload.get("language") or "").strip()
        hotwords = payload.get("hotwords") or []

        if not audio_base64:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": "audioBase64 is required."})
            return

        try:
            audio_bytes = base64.b64decode(audio_base64, validate=True)
        except Exception as exc:
            self._write_json(HTTPStatus.BAD_REQUEST, {"error": f"Invalid audioBase64 payload: {exc}"})
            return

        try:
            result = self.transcriber.transcribe(
                audio_bytes=audio_bytes,
                mime_type=mime_type,
                language=language,
                hotwords=[str(item) for item in hotwords if str(item).strip()],
            )
        except Exception as exc:
            self._write_json(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": str(exc),
                    "traceback": traceback.format_exc(limit=4),
                },
            )
            return

        self._write_json(HTTPStatus.OK, result)

    def log_message(self, format: str, *args: Any) -> None:
        print(f"[funasr-adapter] {self.address_string()} - {format % args}")

    def _read_json_body(self) -> dict[str, Any]:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("Invalid Content-Length header.") from exc

        if length <= 0:
            return {}

        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError("Request body must be valid JSON.") from exc

        if not isinstance(data, dict):
            raise ValueError("JSON body must be an object.")

        return data

    def _write_json(self, status: HTTPStatus, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status.value)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def create_server(config: AdapterConfig | None = None) -> ThreadingHTTPServer:
    adapter_config = config or AdapterConfig.from_env()
    server = ThreadingHTTPServer((adapter_config.host, adapter_config.port), FunASRRequestHandler)
    server.adapter_config = adapter_config  # type: ignore[attr-defined]
    server.transcriber = LazyFunASRTranscriber(adapter_config)  # type: ignore[attr-defined]
    return server


def main() -> None:
    config = AdapterConfig.from_env()
    server = create_server(config)

    if config.eager_load:
        server.transcriber.warmup()  # type: ignore[attr-defined]

    print("FunASR local adapter is running.")
    print(f"- http://{config.host}:{config.port}/healthz")
    print(f"- http://{config.host}:{config.port}/transcribe")
    print(f"- model={config.model} device={config.device} hub={config.hub}")
    server.serve_forever()


if __name__ == "__main__":
    main()
