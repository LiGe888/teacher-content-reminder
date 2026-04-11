# Teacher Content Reminder

面向教师场景的定时内容抓取、加工与钉钉推送系统。

当前仓库已完成第一阶段的基础工程骨架，重点覆盖：

- 来源配置加载
- RSS / HTML 列表抓取入口
- 通用 HTML 正文提取
- 内容价值评分
- SQLite 持久化
- CLI 预览与抓取命令
- FastAPI 接口预留

当前仓库也已包含第二阶段的结构化生成骨架：

- LLM 客户端抽象
- 本地 mock 生成器
- Prompt 模板
- 阅读材料 / 阅读理解 / 完形填空生成
- 结构化输出校验
- 多提供商路由与降级骨架

## 目录结构

```text
config/                         默认配置
docs/                           需求与设计文档
examples/                       示例配置
src/teacher_content_reminder/   应用代码
tests/                          基础单元测试
```

## 本地命令

初始化数据库：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder init-db
```

检查当前运行环境是否准备齐全：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder doctor
```

检查 beta 环境是否准备好，可选执行 live provider 探针：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder beta-check
PYTHONPATH=src python3 -m teacher_content_reminder beta-check --live
```

发送一条测试告警到告警机器人：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder alert-smoke-test
```

测试某个模型 provider 是否能返回合法 JSON：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder llm-smoke-test --provider qwen
PYTHONPATH=src python3 -m teacher_content_reminder llm-smoke-test --provider kimi
PYTHONPATH=src python3 -m teacher_content_reminder llm-smoke-test --provider deepseek
```

查看启用来源：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder list-sources
```

预览单个来源的候选内容：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder preview --source nasa_news --limit 2
```

抓取全部启用来源并落库：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder fetch-all --limit 2 --persist
```

生成教师素材预览：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder generate-preview --source nasa_news --audience senior --limit 1
```

生成时同步导出到本地目录：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder generate-preview --source nasa_news --audience senior --provider router --limit 1 --export-dir .exports
```

专门导出可打印版本：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder export-preview --source nasa_news --audience senior --provider router --limit 1 --output-dir .exports --formats markdown,html,json
```

把某个来源直接生成并放入审核队列：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder queue-source --source nasa_news --audience senior --provider router
```

查看审核队列：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder review-queue --limit 20
PYTHONPATH=src python3 -m teacher_content_reminder review-queue --status pending_review
```

批准某条内容，必要时可直接发送：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder review-approve --queue-id 12
PYTHONPATH=src python3 -m teacher_content_reminder review-approve --queue-id 12 --send
```

拒绝某条内容：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder review-reject --queue-id 12 --note "题材重复，先不发"
```

在发送窗口内尝试派发已批准内容：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder dispatch-approved --now 2026-04-13T07:35:00+08:00
PYTHONPATH=src python3 -m teacher_content_reminder dispatch-approved --send
```

运行一轮定时任务：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder run-scheduled
PYTHONPATH=src python3 -m teacher_content_reminder run-scheduled --force-sources --force-dispatch
```

直接使用真实路由链生成预览：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder generate-preview --source nasa_news --audience senior --provider router --limit 1
```

生成钉钉消息并本地 dry-run 预览：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder send-preview --source nasa_news --audience senior --limit 1
```

实际发送到钉钉：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder send-preview --source nasa_news --audience senior --limit 1 --send
```

发送时同步保存到本地目录：

```bash
PYTHONPATH=src python3 -m teacher_content_reminder send-preview --source nasa_news --audience senior --provider router --limit 1 --send --export-dir .exports
```

`send-preview` 现在默认就会导出到 `.exports`，不额外传 `--export-dir` 也会自动留档。

`send-preview` 默认会拦截低于 `selection.min_total_score` 的内容；如果你只是想人工看效果，可以加 `--allow-low-score`。

当前默认已经是 `router` 真实路由链，优先级为：

```text
qwen -> kimi -> deepseek
```

如果你只想在本地离线调结构，也可以临时改成 mock，有两种方式：

1. 在 CLI 命令里显式加 `--provider mock`
2. 临时把 `config/default.toml` 里的 `llm.provider` 改成 `mock`

真实路由链会自动跳过没有配置 API key 的 provider，所以只配 `Qwen` 也能正常跑；如果同时配了 `Kimi / DeepSeek`，它们会自动作为备份参与。

运行真实模型前，需要先准备环境变量：

```bash
export DASHSCOPE_API_KEY=...
export MOONSHOT_API_KEY=...
export DEEPSEEK_API_KEY=...
```

并且已经支持按任务配置路由链，例如 `extract_facts`、`generate_reading_passage`、`generate_cloze_test` 可以分别走不同 provider 顺序。

真实生成结果会记录：

- 每一步的耗时
- 每一步实际使用的 provider
- 每一步实际使用的 model

本地导出当前支持：

- `teacher_worksheet.md`
- `teacher_worksheet.html`
- `student_worksheet.md`
- `student_worksheet.html`
- `package.json`

其中：

- `teacher` 版包含答案、解析、教学价值、讨论点和延展活动
- `student` 版去掉答案和教师说明，更适合直接打印给学生
- `worksheet.md/html` 仍然保留为 `teacher` 版兼容别名

其中 `worksheet.html` 已经是打印友好版，可以直接在浏览器里“打印 / 另存为 PDF”。如果机器上安装了 `wkhtmltopdf` 或 `weasyprint`，导出时也可以加上 `pdf` 格式。

真实 provider 请求现在会区分鉴权失败、余额不足、限流、服务端错误和网络异常；只有可恢复错误才会重试。钉钉消息在发送前也会做标题、题量和消息长度校验。

当前默认的 beta 策略已经写进配置：

- `score < 78` 直接丢弃
- `78 - 85.9` 进入人工审核
- `86 - 91.9` 标记为可自动发送候选
- `>= 92` 标记为特别推荐候选
- 抓取池偏向知识性和可教学性：
- `NASA` 工作日白天每 `2` 小时一次
- `Science News` 工作日每天 `4` 次
- `Smithsonian` 工作日每天 `3` 次
- `AP` 默认不进入自动抓取池，只保留人工或强制入队
- 工作日默认发送窗口为 `07:40` 和 `20:40`
- 晚间窗口默认只允许 `special` 内容自动发送
- 每天最多 `2` 条，且两次推送至少间隔 `8` 小时
- `project.default_review_mode = "manual"` 时，仍然会先进审核队列，适合 beta 阶段

运行单元测试：

```bash
PYTHONPATH=src python3 -m unittest discover -s tests
```

## API 说明

HTTP API 入口位于 `src/teacher_content_reminder/api.py`，默认依赖 `FastAPI`。

如果后续需要启用 API，可以安装可选依赖：

```bash
pip3 install -e ".[api]"
```

如果你想在本地跑 `pytest` 或 API 测试，建议直接安装开发依赖：

```bash
pip3 install -e ".[api,dev]"
```

然后通过 `uvicorn teacher_content_reminder.api:app --reload` 启动。

启动后可以直接打开：

- `http://127.0.0.1:8000/review`

审核页当前支持：

- 选择来源并直接生成入队
- 查看顶部概览卡片：待审数、已批准数、今日发送数、最近派发结果
- 查看审核队列和单条详情
- 填写审核备注
- 批准
- 批准并直接发送到钉钉
- 拒绝
- 单条派发 dry-run
- 查看 `/alerts` 告警历史页

## 部署

阿里云部署说明见：

- `docs/deployment-aliyun.md`
- `deploy-to-aliyun.sh`

仓库里已附带：

- `deploy/systemd/teacher-content-api.service`
- `deploy/systemd/teacher-content-scheduler.service`
- `deploy/systemd/teacher-content-scheduler.timer`
- `deploy/nginx/teacher-content-reminder.conf`
- `deploy/scripts/bootstrap_aliyun.sh`
- `deploy/scripts/post_deploy_check.sh`
- `deploy/env/production.env.example`
- 查看最近运行记录、跳过原因和发送结果
- 按活动类型和状态筛选运行记录
- 页面内手动执行一轮定时 dry-run
- 页面内强制拉取来源进入审核队列

页面依赖的主要接口包括：

- `GET /api/dashboard-summary`
- `GET /api/review-queue`
- `GET /api/review-queue/{queue_id}`
- `GET /api/activity-log`
- `POST /api/queue/{source_name}`
- `POST /api/review-queue/{queue_id}/approve`
- `POST /api/review-queue/{queue_id}/reject`
- `POST /api/review-queue/{queue_id}/dispatch`
- `POST /api/scheduled/run`
