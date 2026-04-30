# Dev Voice Bridge MVP

一个面向程序员的 Mac 本地语音输入桥接原型。

当前形态不是浏览器插件，也不是 Chrome 扩展；它是：

- `Mac 本地服务`
- `手机或浏览器里的控制页`
- `macOS 粘贴桥接`

另外，现在已经有一个同级的原生 Mac menubar 壳原型：

- [../dev-voice-bridge-shell](</Users/lige/Documents/New project/apps/dev-voice-bridge-shell/README.md>)

当前还支持：

- 浏览器实时预览优先，停止后最终校正
- 锁定目标应用，避免误插入到别的窗口
- PWA 安装到主屏幕
- 页面内直接编辑自定义 glossary
- `科大讯飞 / 豆包语音 / OpenAI / 阿里云百炼 / FunASR` 多供应商转写
- 中文、英文、粤语等语言提示参数透传到转写层

当前 MVP 的链路是：

1. 手机浏览器打开本地网页
2. 浏览器优先提供实时转写预览
3. 停止录音后把文本或音频发给 Mac 本地服务
4. Mac 调用 `科大讯飞 / 豆包语音 / OpenAI / 阿里云百炼 / FunASR` 做音频转写，或者只做归一化
5. 做程序员 glossary 归一化
6. 一次性粘贴到当前 Mac 前台输入框

## 适用场景

- 给 Codex / Claude / Cursor / Kiro 说 prompt
- 给 IDE 输入较长需求描述
- 给评论框输入 review 意见

## 当前限制

- 优先推荐“手机做麦克风，Mac 保持焦点在目标应用”
- 网页桥接版本身还不是原生 menubar app，但已经有同级 `dev-voice-bridge-shell` 原型可试
- 还没有“内建”的本地离线语音识别；`FunASR` 当前按本地适配器模式接入
- 实时预览依赖浏览器 `SpeechRecognition`，不支持时会自动回退到“停止后转写”

## 浏览器建议

- `Android 上的 Google Chrome`：当前最推荐，录音、实时预览、添加到主屏幕这条链路最顺。
- `Mac/Windows 上的 Chrome`：打开控制页没问题，也能做本机录音测试。
- `iPhone 上的 Chrome`：可以用，但因为底层仍是 WebKit，实时预览通常不如 Android Chrome 稳，很多时候会回退到“停止后转写”。

所以结论是：`Google Chrome 没问题`，只是 `Android Chrome` 体验最好，`iPhone Chrome` 以可用为主、实时预览别预期太高。

## 推荐使用方式

1. 在 Mac 上启动本地服务
2. 用手机 Chrome 打开控制页
3. 先点一次“锁定当前前台应用”
4. 开始说话，看实时预览
5. 结束后点“插入到 Mac 当前输入框”
6. 回到目标应用，自己按回车发送
7. 如果某些术语识别不稳，直接在页面底部“自定义术语”里补词

## 启动

可以先参考：

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
cp .env.example .env
npm run doctor
```

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
VOICE_CODER_XFYUN_APP_ID=your_app_id_here \
VOICE_CODER_XFYUN_API_KEY=your_api_key_here \
VOICE_CODER_XFYUN_API_SECRET=your_api_secret_here \
npm start
```

或者：

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
VOICE_CODER_DOUBAO_APP_KEY=your_app_key_here npm start
```

或者：

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
OPENAI_API_KEY=your_key_here npm start
```

如果你还在用阿里云百炼，也仍然支持：

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
DASHSCOPE_API_KEY=your_key_here npm start
```

如果你只想先测试桥接链路，不想调用任何云端转写：

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
npm run start:dry
```

然后在手机和 Mac 同一局域网下，打开服务打印出来的地址。

如果你想走本地 `FunASR`：

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
./scripts/install-funasr-adapter.sh
./scripts/run-funasr-adapter.sh
```

然后把 `.env` 里设成：

```bash
VOICE_CODER_TRANSCRIBE_PROVIDER=funasr
VOICE_CODER_FUNASR_URL=http://127.0.0.1:7861/transcribe
```

适配器说明在：

- [funasr_adapter/README.md](/Users/lige/Documents/New%20project/apps/dev-voice-bridge/funasr_adapter/README.md)

## 权限

第一次真实投递到 Mac 前台应用时，需要给启动它的终端应用授予 macOS Accessibility 权限。

常见做法：

- 系统设置
- 隐私与安全性
- 辅助功能
- 给 `Terminal` 或你实际运行服务的终端应用授权

## 环境变量

- `OPENAI_API_KEY`: OpenAI API key
- `VOICE_CODER_XFYUN_APP_ID`: 讯飞开放平台应用 AppID
- `VOICE_CODER_XFYUN_API_KEY`: 讯飞开放平台 APIKey
- `VOICE_CODER_XFYUN_API_SECRET`: 讯飞开放平台 APISecret
- `VOICE_CODER_XFYUN_MODEL`: 展示/兼容用途，默认 `iat`
- `VOICE_CODER_XFYUN_DOMAIN`: 默认 `iat`
- `VOICE_CODER_XFYUN_ACCENT`: 默认 `mandarin`
- `VOICE_CODER_XFYUN_EOS`: 讯飞后端点静默时长，默认 `2000`
- `VOICE_CODER_XFYUN_ENDPOINT`: 默认 `wss://iat-api.xfyun.cn/v2/iat`
- `VOICE_CODER_DOUBAO_API_KEY`: 豆包语音新版控制台 API key
- `VOICE_CODER_DOUBAO_APP_KEY`: 豆包语音 App key，老控制台或兼容配置可用
- `VOICE_CODER_DOUBAO_ACCESS_KEY`: 老控制台 Access key；新版控制台通常不需要
- `VOICE_CODER_DOUBAO_UID`: 请求里的用户标识，默认 `voice-bridge`
- `VOICE_CODER_DOUBAO_MODEL`: 默认 `bigmodel`
- `VOICE_CODER_DOUBAO_RESOURCE_ID`: 默认 `volc.bigasr.auc_turbo`
- `VOICE_CODER_DOUBAO_ENDPOINT`: 默认 `https://openspeech.bytedance.com/api/v3/auc/bigmodel/recognize/flash`
- `DASHSCOPE_API_KEY`: 阿里云百炼 API key
- `VOICE_CODER_HOST`: 默认 `0.0.0.0`
- `VOICE_CODER_PORT`: 默认 `4317`
- `VOICE_CODER_TRANSCRIBE_PROVIDER`: `xfyun` / `doubao` / `openai` / `dashscope` / `funasr`
- `VOICE_CODER_TRANSCRIBE_MODEL`: 兼容旧变量；显式指定 provider 时会作为该 provider 的模型后备值
- `VOICE_CODER_OPENAI_MODEL`: 默认 `gpt-4o-mini-transcribe`
- `VOICE_CODER_DASHSCOPE_MODEL`: 默认 `qwen3-asr-flash`
- `VOICE_CODER_DASHSCOPE_BASE_URL`: 默认 `https://dashscope.aliyuncs.com/compatible-mode/v1`
- `VOICE_CODER_FUNASR_URL`: 本地 FunASR 适配器 URL
- `VOICE_CODER_FUNASR_MODEL`: 仅作为展示/诊断用途，默认 `funasr-local`
- `VOICE_CODER_DRY_RUN`: `1` 时不执行真实粘贴
- `VOICE_CODER_GLOSSARY_PATH`: 自定义 glossary JSON 路径
- `VOICE_CODER_USER_GLOSSARY_PATH`: 用户 glossary JSON 路径，默认 `data/user-glossary.json`

## 豆包接入说明

- 当前实现优先直连豆包语音极速识别接口，默认资源 ID 用 `volc.bigasr.auc_turbo`
- 浏览器如果只能录成 `webm`，页面会先在本地把录音转成 `wav` 再发给豆包，避免格式不兼容
- 如果你已经同时配置了多个 key，而又不想显式指定 provider，当前自动优先级是 `xfyun > doubao > openai > dashscope > funasr`

## 讯飞接入说明

- 当前接的是讯飞开放平台 `语音听写（流式版）WebAPI`
- 讯飞要求 `16k/8k、16bit、单声道 pcm`；页面会把浏览器录音自动规整成 `16k/mono/wav`，服务端再提取 PCM 帧通过 WebSocket 发给讯飞
- 常见参数是 `AppID / APIKey / APISecret` 三件套，三者缺一不可
- 中文默认走 `zh_cn + iat + mandarin`；如果你后面想试粤语或别的授权语种，可以再通过语言参数和环境变量继续细调

## 模式说明

- `chat`: 给大模型聊天框组织 prompt
- `editor`: 给 IDE 或文档输入草稿
- `terminal`: 给终端输入命令草稿

无论哪种模式，当前 MVP 都只负责“插入文本”，最终发送由你自己在目标应用里按回车确认。

## 测试

```bash
cd /Users/lige/Documents/New\ project/apps/dev-voice-bridge
npm test
```
