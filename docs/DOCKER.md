# Docker 本地演示配置

配置与本地启动工具收尾日期：2026-10-28。

**当前未进行真实镜像构建或容器运行。** 本机没有 Docker CLI / Docker Desktop，
`wsl --list --quiet` 也明确报告尚未安装 WSL。以下配置已完成 YAML 解析及关键路径、
凭证排除、监听地址等静态检查，尚未执行 `docker compose config` 或 `docker compose up`。

## 文件与设计

- `Dockerfile`：Python 3.12 slim-bookworm、安装运行依赖、使用 UID/GID 10001 运行。
- `.dockerignore`：排除 `.env`、Git 历史、主机 `.venv`、业务数据、数据库和日志。
- `compose.yaml`：只向主机 `127.0.0.1` 发布端口，命名卷保存 `/app/data`。
- `scripts.serve`：准备目录、执行迁移，再启动单 worker Uvicorn，直接处理停止信号。

数据库、上传文件、Qdrant、模型缓存均位于可写的 `/app/data`，镜像其余文件系统只读。
`/tmp` 使用临时文件系统。没有复制主机 `.env` 或既有业务数据库到镜像。
本演示直接使用 Qdrant Local，不再启动单独的 Qdrant 服务；不可启用多 worker 或多副本
共同写入同一目录。镜像当前沿用项目 requirements，包含测试工具，不宣称已优化为最小生产镜像。

已只读核对 PyPI 官方文件元数据：固定的 `xxhash 3.6.0`、`mmh3 5.2.0`、
`py-rust-stemmers 0.1.5` 均提供 CPython 3.12 Linux x86_64 wheel。
这只确认分发文件存在，不等于已验证完整 Linux 依赖安装或容器可运行。

配置方式参考 [Docker Compose 环境变量说明](https://docs.docker.com/compose/how-tos/environment-variables/variable-interpolation/)
及 [构建上下文排除说明](https://docs.docker.com/build/concepts/context/#dockerignore-files)。

## 先决条件

安装并启动 [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)，
使用 Linux containers。安装可能需要启用 WSL 2 / 虚拟化和重启，属于系统环境修改；
本阶段没有自动安装或修改这些系统组件。

在项目根目录的私有 `.env` 中配置非空随机 `REVIEW_API_KEY`，不要提交该密钥。
本机已存在的审核密钥可以复用。Compose 从 `.env` 插值，不会把文件复制进镜像。
变量未配置时会报错停止，避免提供一个无审核密钥的容器。

## 有运行环境后的验证顺序

```powershell
docker version
docker compose version
docker compose config --quiet
.\start.ps1 -Docker
```

`config --quiet` 只做校验，不把解析后的私有密钥打印到终端。
启动器执行 `docker compose up --build --detach --wait`，失败时查看：

```powershell
docker compose logs api
```

指定主机端口：`./start.ps1 -Docker -Port 8765`。默认访问 `http://127.0.0.1:8000/docs`。
API 的环境标记是 `demo`，默认 extractive 模式；镜像不预装模型权重，首次文档处理
可能下载模型到命名卷。容器健康不等于模型已经加载。

在主机已配置 Python 环境时可运行：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke --base-url http://127.0.0.1:8000 --output reports/demo-acceptance-local.json
```

或者在容器内执行（报告放到可写数据卷）：

```powershell
docker compose exec -T api python -m scripts.smoke --base-url http://127.0.0.1:8000 --output /app/data/reports/smoke.json
```

容器内的评估报告也应显式输出至 `/app/data`：

```powershell
docker compose exec -T api python -m evaluation.run --check --output /app/data/reports/evaluation.json
```

## 停止与数据保留

```powershell
docker compose down
```

默认会保留命名卷，之后再次启动可复用数据与模型。不要在需要保留数据时执行 `down -v`。
首次 HTTP 验收完成后，重启容器，再使用 smoke 的 `--verify-report` 对旧报告做持久化核验。
只有实际完成构建、启动、HTTP 链路和重启卷验证后，才可把该项验收改为已通过。
