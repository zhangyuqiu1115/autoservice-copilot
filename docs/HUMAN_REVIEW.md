# 人工审核与工单流转

实际开发日期：2026-10-27。本阶段沿用 Agent 的待审核工单，增加显式人工决策、
最终答复、关闭流程以及可追溯的状态变更记录。

## 状态规则

| 操作 | 原状态 | 新状态 | 必填内容 |
| --- | --- | --- | --- |
| approve | pending_review | approved | reviewer、expected_version、final_response |
| reject | pending_review | draft | reviewer、expected_version、comment |
| resubmit | draft | pending_review | reviewer、expected_version |
| close | approved | closed | reviewer、expected_version |

所有状态操作必须通过审核密钥校验。`closed` 是终态，不能继续批准、退回、送审或重复关闭。
批准后 `requires_human_review=false`；退回和重新送审时为 `true`。
关闭保留审批时间和最终答复，并设置关闭时间。AI 的 `recommended_action` 始终保留，
最终答复必须由审核请求显式提供，系统不会自动把 AI 建议当作人工答复。

## 本地配置与迁移

1. 在项目目录执行 `python -m alembic upgrade head`。
2. 用 `python -c "import secrets; print(secrets.token_urlsafe(32))"` 生成私有随机密钥。
3. 在本地 `.env` 设置 `REVIEW_API_KEY=<生成的密钥>`，重启 API。
4. 打开 `/docs`，点击 **Authorize**，在 `ReviewKey` 中输入密钥。

`.env` 已被 Git 忽略，请勿把真实密钥写入 README、示例或提交。
未配置密钥时审核与历史接口返回 `503`；没有或提供错误密钥返回 `403`。
密钥使用常量时间比较，配置采用 Pydantic `SecretStr` 隐藏调试表示中的值。
实现基于 [FastAPI APIKeyHeader](https://fastapi.tiangolo.com/reference/security/#fastapi.security.APIKeyHeader)。

这是本地演示用的共享密钥。`reviewer` 是密钥持有者填写的署名，并非经账号系统
验证的身份；普通业务接口也未实现统一鉴权，不应直接暴露到公网。

## Swagger 操作示例

通过 Agent 创建工单后，GET 工单详情获得最新 `version`。假设工单 ID 为 1、版本为 1，
向 `POST /api/v1/service-tickets/1/review` 提交：

```json
{
  "reviewer": "本地演示审核员",
  "expected_version": 1,
  "decision": "approve",
  "final_response": "已由售后人员确认，请联系授权服务中心安排检查。",
  "comment": "已核对资料和建议"
}
```

返回 `approved`、`version=2`、`approved_at` 和人工最终答复。
然后向 `POST /api/v1/service-tickets/1/close` 提交：

```json
{
  "reviewer": "本地演示审核员",
  "expected_version": 2,
  "comment": "已完成沟通处理"
}
```

退回示例使用 `decision=reject`，提供非空 `comment`，不传 `final_response`。
退回后通过 `POST /api/v1/service-tickets/1/submit-for-review` 重新送审，使用当时的
版本号和意见说明。现阶段不提供修改原问题或 AI 建议的接口；补充确认说明写入 `comment`。

## 查阅与冲突处理

- `GET /api/v1/service-tickets?status=pending_review`：筛选待审核工单。
- `GET /api/v1/service-tickets/{id}`：读取最新版本和状态。
- `GET /api/v1/service-tickets/{id}/events?offset=0&limit=20`：读取按事件 ID 排序的历史。
- 不存在的工单返回 `404`；非法字段或空最终答复返回 `422`。
- 非法流转、重复操作或过期版本返回 `409`；重新读取工单后由人工决定下一步。
- 数据库写入失败返回 `503`，工单与事件一起回滚。

每次成功变更会让 `version` 加一。SQL 更新同时匹配工单 ID、原状态和版本号，
避免陈旧页面或另一个数据库会话覆盖新决策；这也能阻止退回并送审后重新使用最初的版本。
实现采用 [SQLAlchemy 条件 UPDATE](https://docs.sqlalchemy.org/en/20/orm/queryguide/dml.html#orm-update-and-delete-with-custom-where-criteria)。
审核事件保存前后状态、版本、署名、意见、最终答复快照及 UTC 生成的时间。
API 只提供事件读取，不提供修改或删除。直接数据库访问仍可修改记录，因此这不是防篡改审计系统。

## 数据迁移与验证

迁移 `a8f3c92d6710` 为既有工单回填 `version=1`，新增 `ticket_events` 表，不删除现有工单。
迁移升级、降级、再升级使用临时 SQLite 测试验证，覆盖旧数据保留。
真实本地数据库只执行升级；降级会删除审核历史，仅应在明确需要时操作。
审批测试覆盖批准关闭、退回再送审、鉴权、字段校验、重复操作、陈旧会话冲突和事件写入失败回滚。
