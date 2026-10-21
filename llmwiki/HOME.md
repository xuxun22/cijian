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
2. **记录（任务中/后）**：解决了一个非平凡问题（报错、环境坑、设计纠偏、外部服务行为）→
   新建/更新 `pages/` 条目 → 更新 `index.md` → 追加 `log.md`。
3. **lint（周期性）**：检查条目间矛盾、过时信息、孤儿页面；修正并在 log 记录。

## 约定

- 条目头部：日期、仓库、类别（gotcha / howto / overview / decision）、状态（现行 / 已过时）
- **只增不删**：过时的写"已过时"并追加更正小节，不删除历史
- 保持条目短小、事实性、可 grep（多用具体命令、路径、报错原文片段）
- `log.md` 每条以 `## [YYYY-MM-DD] 类型 | 标题` 开头（可被 `grep "^## \[" log.md` 解析）

## 入口

- 目录：[index.md](index.md)
- 时间线：[log.md](log.md)
- 系统总览：[pages/overview.md](pages/overview.md)
