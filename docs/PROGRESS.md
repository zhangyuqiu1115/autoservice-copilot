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

### 2026-10-15：有引用的 RAG 问答

- 新增检索、证据过滤和回答生成服务
- 默认提供无需 API Key 的原文型回答
- 支持可选 OpenAI-compatible Chat Completions 服务
- 回答返回来源编号、文档与文本块标识、分数和证据原文
- 低于证据阈值时明确拒答，避免无依据回答
- 增加上下文长度限制和检索内容指令隔离
- 增加 RAG 服务及 API 自动化测试

## 后续实际开发日

- [ ] LangGraph Agent、安全风险分流和售后工单
- [ ] 人工审批、评估、Docker 与本地演示文档
