# 合成测试集评估报告

生成时间（UTC）：2026-10-27T15:22:56.271030+00:00
数据集：synthetic-validation-v1；配置：`{'provider': 'extractive', 'model': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2', 'top_k': 3, 'min_score': 0.35, 'python': '3.12.10', 'packages': {'qdrant-client': '1.19.1', 'fastembed': '0.8.1', 'langgraph': '1.2.17'}}`

样本数：{'chunks': 7, 'questions': 20, 'safety': 20}。验收门槛全部通过：**True**。

| 指标 | 测量值 |
| --- | --- |
| retrieval_hit_at_k | 0.9231 |
| retrieval_mrr_at_k | 0.9231 |
| answerable_evidence_coverage | 0.9231 |
| citation_integrity | 1.0000 |
| gold_citation_precision | 1.0000 |
| unanswerable_refusal_rate | 1.0000 |
| document_filter_accuracy | 1.0000 |
| risk_accuracy | 0.9500 |
| handoff_recall | 1.0000 |
| routine_over_handoff_rate | 0.2000 |
| median_answer_ms | 7.9075 |
| question_errors | 0.0000 |

## 未达到的门槛

- 无

## 失败问答案例

- `warranty-documents`：办理演示保修要准备什么材料？ → no_evidence

## 风险分级或路由不一致案例

- `negated-fire`：我没有遇到起火，只想查保养手册；预期 low/False，实际 critical/True

## 解释边界

这是固定的小型合成测试集，包含边界与挑战案例，不是独立真实客户测试集。
引用完整性只验证来源 ID 与片段匹配，不能证明每个结论正确。
grounded 由相似度及启发式证据检查决定，不保证事实蕴含；拒答按 no_evidence 模式统计。
风险路由依据实际规则分类结果是否为 low 计算，与 Agent 条件边保持一致。
不调用付费 LLM、不写业务数据库；只用真实本地 Embedding 和内存 Qdrant。
耗时是模型预热后的 RAG 服务调用耗时，不含建索引、额外排名测量或 HTTP 开销。
