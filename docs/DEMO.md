# 本地一键演示与最终验收记录

本地全链路验收开始于 2026-10-27，重启持久化与启动工具收尾于 2026-10-28。
原始报告的 UTC 时间保留不变；不回填提交时间。

## 已验证状态

| 项目 | 证据与状态 |
| --- | --- |
| 本地一键启动 | 实际执行 `start.ps1 -Port 8765`，自动建立独立数据库并运行迁移 |
| 真实 HTTP 链路 | 13 项检查通过，非 Mock / TestClient 替代运行 |
| 跨进程重启持久化 | 停止并重启相同数据目录后，6 项只读检查通过 |
| 功能回归与脚本检查 | 160 passed、Ruff 通过、PowerShell AST 无语法错误 |
| Docker 配置 | Dockerfile、Compose、构建排除规则和入口已提供；YAML 解析与关键配置检查通过 |
| Docker 镜像与容器 | 未实测：本机未安装 Docker CLI/Desktop，WSL 也未安装 |

这些是本地演示的验证结果，不代表生产部署验收或真实车辆诊断认证。

## 准备环境

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

已有 `.venv` 时直接复用，不必重建。配置文件不存在时才复制：

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

本地启动器优先复用 `.env` 或环境变量中的 `REVIEW_API_KEY`；未配置时自动生成
独立演示目录内的 `.review-key`，后续启动会复用，密钥不会输出到日志或验收报告。
Swagger 审核时将实际私有密钥填到 **Authorize / ReviewKey** 中。

## 一键启动

```powershell
.\start.ps1
```

端口已占用时：

```powershell
.\start.ps1 -Port 8765
```

也可直接使用 Python：

```powershell
.\.venv\Scripts\python.exe -m scripts.local --port 8765
```

API 默认只监听 `127.0.0.1`，环境标记固定为 `demo`，采用无需 API Key 的 extractive 模式。
服务保持前台运行，`Ctrl+C` 停止；应用正常关闭时释放 Qdrant 文件锁。

演示 SQLite、上传文件和 Qdrant 都保存在 `data/private/local-demo/`，与根目录的
`autoservice.db` 及原有 `data/qdrant/` 分离。模型缓存默认复用 `data/models/`，首次使用
可能下载模型；健康检查只表示 API 进程可响应，不表示模型已预热。
每次启动先执行 Alembic 迁移，迁移失败不会启动 API。Qdrant Local 使用单 worker。
如需独立的另一份演示数据，可传 `scripts.local --data-dir <新目录>`；未配置审核密钥时，
验收脚本需要用 `--key-file <新目录>/.review-key` 指定对应密钥文件。

## 真实 HTTP 验收

第二个终端在项目根目录执行：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke --base-url http://127.0.0.1:8765 --output reports/demo-acceptance-local.json
```

脚本只接受 loopback HTTP 地址，并在任何数据写入前检查目标 `ENVIRONMENT=demo`。
禁止把它当作生产环境探测脚本；每次运行会创建一辆合成车辆、一份合成资料、两张演示工单，
不会自动删除历史演示数据。合成审核事件署名为 `automated-synthetic-smoke`，不是实际客户审核。

检查项包含：健康环境、车辆创建、上传解析索引、文档过滤、RAG 引用、缺少事实时拒答、
Agent 待审核工单、风险转人工、无密钥禁止审核、显式合成审核、过期版本冲突、关闭和审计历史。
任何一步失败会以非零退出码停止，只有全部成功才输出 `passed=true` 的新报告。

实际记录：[13 项 HTTP 验收](../reports/demo-acceptance-2026-10-27.json)。

## 重启与持久化核验

停止前台 API，重新运行相同的启动命令，随后对上一份报告执行只读核验：

```powershell
.\.venv\Scripts\python.exe -m scripts.smoke --base-url http://127.0.0.1:8765 --verify-report reports/demo-acceptance-local.json --output reports/demo-restart-local.json
```

核验先前的车辆、已处理文档、已关闭工单、待审核风险工单、审核历史和向量检索结果。
实际记录：[6 项重启核验](../reports/demo-restart-2026-10-28.json)。

## 验收结论与剩余工作

本地后端演示链路已经跑通，既有两个小型合成评估集也已通过内部质量门槛。
Docker 构建、容器启动、容器内 HTTP 验收和容器卷重启验收仍待有运行环境后执行，
不能用本地成功替代容器成功。当前提供的是后端 API / Swagger 演示，不包含独立前端页面。
