# DeepSched

## Linux 本地开发

环境要求：Python 3.11+、Node.js 20+（需包含 Corepack）。

首次安装依赖：

```bash
./setup-linux.sh
```

需要通过本机代理下载依赖时：

```bash
DEEPSCHED_PROXY=http://127.0.0.1:7897 ./setup-linux.sh
```

启动带热更新的前后端：

```bash
./start-linux.sh
```

- 前端：`http://<本机 IP>:5889`（监听 `0.0.0.0`）
- 后端接口文档：http://127.0.0.1:8000/docs
- 本地数据：`server/cro_scheduler.db`（SQLite，首次启动自动创建）

停止服务时在启动终端按 `Ctrl+C`。前后端日志写入 `.runtime/logs/`。

## Docker 部署

复制 `.env.example` 为 `.env`，替换其中全部密码，再执行：

```bash
docker compose up --build -d
```

Docker Compose 使用 MySQL，适合部署验证；日常开发建议使用上面的本地开发模式。

## Linux 生产运行

公网反向代理到 5889 端口时，使用生产启动脚本：

```bash
./start-production.sh
```

该脚本会构建前端，由 FastAPI 生产入口在 5889 端口同时提供 `web/dist` 和 `/api/`，并对静态文件开启 GZip。不要在公网环境使用 `start-linux.sh`。
