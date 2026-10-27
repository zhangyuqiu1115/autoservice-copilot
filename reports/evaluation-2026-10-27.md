# 合成测试集评估报告

生成时间（UTC）：2026-10-27T15:07:59.003036+00:00
数据集：synthetic-v1；配置：`{'provider': 'extractive', 'model': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', 'top_k': 3, 'min_score': 0.35, 'python': '3.12.10', 'packages': {'qdrant-client': '1.19.1', 'fastembed': '0.8.1', 'langgraph': '1.2.17'}}`

样本数：{'chunks': 8, 'questions': 20, 'safety': 20}。验收门槛全部通过：**False**。

| 指标 | 测量值 |
| --- | --- |
| retrieval_hit_at_k | 1.0000 |
| retrieval_mrr_at_k | 1.0000 |
| answerable_evidence_coverage | 1.0000 |
| citation_integrity | 1.0000 |
| gold_citation_precision | 0.4000 |
| unanswerable_refusal_rate | 0.3333 |
| document_filter_accuracy | 1.0000 |
| risk_accuracy | 0.8000 |
| handoff_recall | 0.8000 |
| routine_over_handoff_rate | 0.2000 |
| median_answer_ms | 5.9895 |
| question_errors | 0.0000 |

## 未达到的门槛

- unanswerable_refusal_rate: 要求 0.8
- handoff_recall: 要求 1.0
- risk_accuracy: 要求 0.9

## 失败问答案例

- `missing-exact-warranty`：这辆车保修具体是几年？ → extractive
- `missing-exact-range`：这辆车现在充满电一定能跑多少公里？ → extractive
- `wrong-document`：预约保养时需要提供哪些信息？ → extractive
- `missing-wiper-period`：雨刷具体每多少个月必须更换？ → extractive

## 风险分级或路由不一致案例

- `negated-smoke`：没有冒烟，只是想问保养；预期 low/False，实际 critical/True
- `burning-smell`：充电时闻到了烧焦的味道；预期 high/True，实际 low/False
- `tire-symptom`：轮胎漏气了，还能开去充电吗？；预期 high/True，实际 low/False
- `english-overheating`：The charging cable is extremely hot；预期 medium/True，实际 low/False

## 解释边界

这是固定的小型合成测试集，包含边界与挑战案例，不是独立真实客户测试集。
引用完整性只验证来源 ID 与片段匹配，不能证明每个结论正确。
grounded 是分数阈值标记，不证明证据足以回答问题；拒答按 no_evidence 模式严格统计。
风险路由依据实际规则分类结果是否为 low 计算，与 Agent 条件边保持一致。
不调用付费 LLM、不写业务数据库；只用真实本地 Embedding 和内存 Qdrant。
耗时是模型预热后的 RAG 服务调用耗时，不含建索引、额外排名测量或 HTTP 开销。
