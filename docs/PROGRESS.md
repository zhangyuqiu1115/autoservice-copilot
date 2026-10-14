# AutoService Copilot 开发进度

本文件记录实际完成的开发阶段。日期使用真实完成日期，不回填或伪造历史。

## 已完成

### 2026-10-14：Embedding 与 Qdrant 语义检索

- 接入 FastEmbed 多语言模型
- 使用 Qdrant Local Mode 持久化文本块向量
- 文档处理完成后自动建立或替换向量索引
- 新增支持文档过滤和 Top-K 的语义检索 API
- 增加 Embedding、向量存储和检索 API 自动化测试
- 完成中英文跨语言检索验证

## 后续实际开发日

- [ ] RAG 答案生成、引用和无证据拒答
- [ ] LangGraph Agent、安全风险分流和售后工单
- [ ] 人工审批、评估、Docker 与本地演示文档
