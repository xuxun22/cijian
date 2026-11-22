# llmwiki · 此间开发经验维基

> 模式来源：[Karpathy 的 llmwiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)。
> 由 LLM 在开发过程中**增量维护**的持久知识库——不是"每次重新踩坑"，而是"编译一次、持续保鲜"。

## 这是什么

此间（cijian）所有开发/测试/部署/排障过程中产生的**非平凡问题与解法**都沉淀在这里。
任何 LLM 会话在动 cijian 的代码之前，先查这里；解决新问题之后，往这里写。

## 三层结构（Karpathy 模式）

| 层 | 位置 | 说明 |
|---|---|---|
| 原始素材 | 各代码仓的 git 历史、服务器、日志 | **不可变**，只读不改 |
| wiki 本体 | 本目录 `pages/*.md` + `index.md` + `log.md` | **LLM 全权维护** |
| schema | `SKILL.md`（已安装为 OpenCode skill） | 约定与工作流，人机共同演化 |

## 工作流

1. **查阅（任务开始）**：grep `index.md` / `log.md` 里与任务相关的关键词，读相关页面。
2. **记录（任务中/后，自动）**：解决了一个非平凡问题（报错、环境坑、设计纠偏、外部服务行为）→
   自己判断并直接新建/更新 `pages/` 条目 → 更新 `index.md` → 追加 `log.md`。
   **不要询问用户「要不要沉淀」**；拿不准时按「值得」处理。提交统一等爸爸回「提交」；
   **「提交」= commit + push**（含 CI 绿与部署确认，见 [devflow-commit-push](pages/devflow-commit-push.md)）。
3. **整理（定期，自动）**：增量——每次写条目顺手核对 index/log 与旧条目矛盾；
   全量——`log.md` 里最后一次「全量整理」超过 30 天时自动做一遍（孤儿页、过时状态、断链、矛盾），
   完成后记 `## [YYYY-MM-DD] 整理 | 全量整理`。**不要询问用户**，随当批 diff 汇报。

## 约定

- 条目头部：日期、仓库、类别（gotcha / howto / overview / decision）、状态（现行 / 已过时）
- **只增不删**：过时的写"已过时"并追加更正小节，不删除历史
- 保持条目短小、事实性、可 grep（多用具体命令、路径、报错原文片段）
- `log.md` 每条以 `## [YYYY-MM-DD] 类型 | 标题` 开头（可被 `grep "^## \[" log.md` 解析）

## 入口

- 目录：[index.md](index.md)
- 时间线：[log.md](log.md)
- 系统总览：[pages/overview.md](pages/overview.md)
