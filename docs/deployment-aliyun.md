# 阿里云服务器部署说明

这套系统适合先以单机方式部署到一台阿里云 ECS 上，当前默认方案是：

- `FastAPI + uvicorn` 提供审核台和导出访问
- `systemd timer` 定时触发 `run-scheduled`
- `SQLite` 保存队列、活动日志和生成结果
- `Nginx` 做反向代理，统一暴露 `80/443`

当前阶段是 beta，小流量单机部署足够。后续如果用户量上来，再把 `SQLite` 换成 `PostgreSQL`。

如果你希望从本机直接一把推上去，仓库根目录还有一个总控脚本：

- `deploy-to-aliyun.sh`

它会串联：

- `rsync` 同步代码
- 可选同步本地 `.env`
- 远端安装依赖
- 初始化虚拟环境和数据库
- 安装 `systemd`
- 安装 `nginx`
- 执行部署后检查

脚本默认已经内置国内镜像参数：

- `PIP_INDEX_URL=https://mirrors.aliyun.com/pypi/simple/`
- `PIP_TRUSTED_HOST=mirrors.aliyun.com`

## 1. 服务器建议

- 系统：`Ubuntu 22.04/24.04` 或 `Alibaba Cloud Linux 3`
- CPU：`2 vCPU` 起步
- 内存：`2 GB` 起步，建议 `4 GB`
- 磁盘：`40 GB SSD`
- 时区：`Asia/Shanghai`

## 2. 系统依赖

### Ubuntu / Debian

```bash
sudo apt update
sudo apt install -y git python3.11 python3.11-venv python3-pip build-essential nginx
sudo timedatectl set-timezone Asia/Shanghai
```

### Alibaba Cloud Linux 3

```bash
sudo dnf install -y git python3.11 python3.11-pip gcc gcc-c++ make nginx
sudo timedatectl set-timezone Asia/Shanghai
```

如果系统没有 `python3.11-venv` 包，也可以直接用：

```bash
python3.11 -m venv .venv
```

## 3. 推荐部署用户与目录

建议单独创建一个系统用户，而不是直接用 `root` 或 `www-data`：

- 用户：`teacherreminder`
- 目录：`/opt/teacher-content-reminder`

仓库里已经附带一个初始化脚本：

- `deploy/scripts/bootstrap_aliyun.sh`

它会做这些事：

- 安装系统依赖
- 创建 `teacherreminder` 用户
- 创建 `/opt/teacher-content-reminder`
- 设置时区

直接执行：

```bash
chmod +x deploy/scripts/bootstrap_aliyun.sh
./deploy/scripts/bootstrap_aliyun.sh
```

## 4. 代码目录建议

建议统一放在：

```text
/opt/teacher-content-reminder
```

部署步骤：

```bash
sudo mkdir -p /opt/teacher-content-reminder
sudo chown -R $USER:$USER /opt/teacher-content-reminder
cd /opt/teacher-content-reminder
git clone <your-repo-url> .
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[api]"
```

如果服务器在中国大陆，建议优先使用阿里云镜像源：

```bash
.venv/bin/pip install --upgrade pip setuptools wheel \
  --index-url https://mirrors.aliyun.com/pypi/simple/ \
  --trusted-host mirrors.aliyun.com
.venv/bin/pip install -e ".[api]" --no-build-isolation \
  --index-url https://mirrors.aliyun.com/pypi/simple/ \
  --trusted-host mirrors.aliyun.com
```

如果你希望服务器上也能直接运行 `pytest` 或扩展调试工具，可以改成：

```bash
.venv/bin/pip install -e ".[api,dev]"
```

## 5. 环境变量

服务器上至少要配置这些：

```bash
DASHSCOPE_API_KEY=
MOONSHOT_API_KEY=
DEEPSEEK_API_KEY=

DINGTALK_WEBHOOK_URL=
DINGTALK_SECRET=

DINGTALK_ALERT_WEBHOOK_URL=
DINGTALK_ALERT_SECRET=

ALERT_VIEW_HOST=https://your-domain.example.com
```

说明：

- `DINGTALK_*` 是正常内容推送机器人
- `DINGTALK_ALERT_*` 是告警机器人
- `ALERT_VIEW_HOST` 用来拼出告警详情页和导出讲义页的公网链接
- 当前默认模型链就是 `router`，顺序为 `qwen -> kimi -> deepseek`
- 没填 key 的 provider 会被自动跳过，不会阻塞服务启动
- 如果部署脚本里的 `DOMAIN` 没填或保持 `_`，脚本会自动用服务器 IP 作为 `nginx` 的 `server_name`

生产环境建议把 `.env` 放在项目根目录：

```text
/opt/teacher-content-reminder/.env
```

你也可以直接从模板开始：

- `deploy/env/production.env.example`

## 6. 上线前检查

先跑这些命令：

```bash
cd /opt/teacher-content-reminder
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests
PYTHONPATH=src .venv/bin/teacher-content-reminder doctor
PYTHONPATH=src .venv/bin/teacher-content-reminder beta-check --live
PYTHONPATH=src .venv/bin/teacher-content-reminder alert-smoke-test
```

如果你只想先测页面，不立刻跑定时发送，也可以先不开 timer，只启动 API 服务。

仓库里还带了一个部署后检查脚本：

- `deploy/scripts/post_deploy_check.sh`

用法：

```bash
chmod +x deploy/scripts/post_deploy_check.sh
APP_DIR=/opt/teacher-content-reminder ./deploy/scripts/post_deploy_check.sh
```

## 7. systemd

仓库里已经准备好了这些模板：

- `deploy/systemd/teacher-content-api.service`
- `deploy/systemd/teacher-content-scheduler.service`
- `deploy/systemd/teacher-content-scheduler.timer`

复制到系统目录：

```bash
sudo cp deploy/systemd/teacher-content-api.service /etc/systemd/system/
sudo cp deploy/systemd/teacher-content-scheduler.service /etc/systemd/system/
sudo cp deploy/systemd/teacher-content-scheduler.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now teacher-content-api
sudo systemctl enable --now teacher-content-scheduler.timer
```

检查运行状态：

```bash
sudo systemctl status teacher-content-api
sudo systemctl status teacher-content-scheduler.timer
journalctl -u teacher-content-api -n 100 --no-pager
journalctl -u teacher-content-scheduler.service -n 100 --no-pager
```

注意：模板里默认用户已经设置为 `teacherreminder`，如果你用了别的用户，需要一起改。

## 8. Nginx

仓库里也准备了示例配置：

- `deploy/nginx/teacher-content-reminder.conf`

复制后按你的域名改：

```bash
sudo cp deploy/nginx/teacher-content-reminder.conf /etc/nginx/conf.d/teacher-content-reminder.conf
sudo nginx -t
sudo systemctl enable --now nginx
sudo systemctl reload nginx
```

## 9. 安全组和端口

至少放行：

- `22`：SSH
- `80`：HTTP
- `443`：HTTPS

`8000` 不建议直接暴露公网，交给 `Nginx` 反向代理即可。

## 10. 当前上线建议

beta 阶段建议这样跑：

- API 服务先对外开放，便于人工审核
- `systemd timer` 每 `10` 分钟跑一次 `run-scheduled`
- 定时任务先保留 `--send`，但继续保持人工审核主策略
- 告警开启，这样内容推送失败、来源抓取失败、定时任务异常都会进入告警机器人

## 11. 当前已知边界

- 当前数据库是 `SQLite`，适合单机单实例
- 当前导出默认写在 `.exports/`
- 告警详情页默认写在 `.data/alerts/`
- 如果你未来做多实例或高并发审核，建议先迁移数据库，再扩机器
