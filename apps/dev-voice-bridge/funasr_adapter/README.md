# FunASR Local Adapter

这个目录提供一个给 `Dev Voice Bridge` 用的本地 HTTP 适配器。

它的作用很单纯：

- 接收桥接服务发来的 `audioBase64`
- 用本机 `FunASR` 做转写
- 返回统一的 `{ "text": "..." }` 结果

这样主桥接服务只需要设置：

```bash
VOICE_CODER_TRANSCRIBE_PROVIDER=funasr
VOICE_CODER_FUNASR_URL=http://127.0.0.1:7861/transcribe
```

## 依赖

官方 FunASR README 展示的是 `from funasr import AutoModel` + `model.generate(...)` 的本地推理方式。

参考：

- [FunASR README](https://github.com/FunAudioLLM/Fun-ASR)
- [FunASR Runtime Roadmap](https://github.com/modelscope/FunASR/blob/main/runtime/readme.md)

这个适配器为了尽量轻，服务端只用了 Python 标准库；真正的模型依赖在 `requirements.txt`：

- `funasr`
- `modelscope`
- `torch`
- `torchaudio`

如果你要处理 `webm/m4a/mp3` 之类的输入，建议系统里再装一个 `ffmpeg`。

## 建议安装

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
python3 -m venv .venv-funasr
. .venv-funasr/bin/activate
pip install -U pip setuptools wheel
pip install -r funasr_adapter/requirements.txt
```

## 启动

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
./scripts/run-funasr-adapter.sh
```

默认会监听：

- `http://127.0.0.1:7861/healthz`
- `http://127.0.0.1:7861/transcribe`

## 可选环境变量

- `FUNASR_ADAPTER_HOST`: 默认 `127.0.0.1`
- `FUNASR_ADAPTER_PORT`: 默认 `7861`
- `FUNASR_MODEL`: 默认 `FunAudioLLM/Fun-ASR-Nano-2512`
- `FUNASR_DEVICE`: 默认 `cpu`
- `FUNASR_HUB`: 默认 `hf`
- `FUNASR_VAD_MODEL`: 可选，例子：`fsmn-vad`
- `FUNASR_ITN`: 默认 `1`
- `FUNASR_EAGER_LOAD`: 设为 `1` 时启动就预热模型

## 验证

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge/funasr_adapter
python3 -m unittest test_server.py
```
