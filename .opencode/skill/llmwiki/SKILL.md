---
name: llmwiki
description: 此间（cijian）项目的开发经验维基。凡涉及 cijian / 此间 / cijian-site / cijian-api / cijian-agent / 打印任务 / whereami 的开发、测试、部署、排障任务都必须使用：任务开始前先查维基避免重复踩坑；解决非平凡问题后立即沉淀条目。
---

# llmwiki · 此间开发经验维基

模式来源：Karpathy 的 llmwiki——LLM 在真实工作中增量维护的持久知识库，
编译一次、持续保鲜，而不是每次会话从零重新踩坑。

## 维基位置（固定，勿改动）

`/Users/xuxun22/work/cijian/llmwiki/`（cijian 文档仓，随 git 提交推送）

- `index.md` —— 条目目录（按 gotcha / howto / overview 分类，带一行摘要）
- `log.md` —— 时间线，追加式，每条以 `## [YYYY-MM-DD] 类型 | 标题` 开头
- `pages/*.md` —— 条目正文
- `HOME.md` —— 使用说明

## 工作流

### 1. 任务开始（必做）

```bash
ls /Users/xuxun22/work/cijian/llmwiki/pages/
grep -ri "<任务关键词>" /Users/xuxun22/work/cijian/llmwiki/
```

读到与当前任务相关的条目（部署拓扑、打印状态机、已知坑）就先读完再动手。
**重蹈 llmwiki 里已记录的覆辙是不可接受的。**

### 2. 记录（解决非平凡问题后，必做）

满足任一条件就记：排查超过一轮的报错、环境/平台差异坑、外部服务反直觉行为、
改动了部署拓扑或密钥位置、推翻了此前条目的结论。

步骤：
1. 新建或更新 `pages/<主题>.md`——头部注明日期/仓库/类别（gotcha|howto|overview|decision）/状态；
   正文含 **症状 → 根因 → 解法 → 预防**，多用具体命令、路径、报错原文片段
2. 在 `index.md` 对应分类下登记一行
3. 向 `log.md` 追加 `## [YYYY-MM-DD] gotcha|howto|deploy | 一句话标题`
4. `cd /Users/xuxun22/work/cijian && git add llmwiki && git commit && git push`

### 3. 纪律

- **只增不删**：条目过时就标"已过时"并追加更正小节，历史不抹
- 明文密钥/口令**永不写入**（写存放位置即可，见 env-and-secrets）
- 条目要短、事实性、可 grep；一个条目一个主题
- 已被 docs/（04 契约、05 数据模型、ADR）正式记载的设计决策，在 wiki 里放链接即可，不要复制正文
