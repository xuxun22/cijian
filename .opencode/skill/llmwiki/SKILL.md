---
name: llmwiki
description: 此间（cijian）项目的开发经验维基。凡涉及 cijian / 此间 / cijian-site / cijian-api / cijian-agent / 打印任务 / whereami 的开发、测试、部署、排障任务都必须使用：任务开始前先查维基避免重复踩坑；解决非平凡问题后**自动**沉淀条目——自己判断、直接写成文件，不要询问用户要不要沉淀。
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

### 2. 记录（解决非平凡问题后，自动执行，不要询问用户）

**不要问「要不要沉淀」「回『沉淀』我就写」——这是你的职责，不是用户的决定。**
任务收尾时自己自检：这次有没有产生可复用的经验？有就直接写。

满足任一条件就记：排查超过一轮的报错、环境/平台差异坑、外部服务反直觉行为、
改动了部署拓扑或密钥位置、新机制/架构决策、改了默认行为或配置项、推翻了此前条目的结论。

不记：纯错字/格式调整、一次性数据修复且无复用价值、用户个人偏好的微调、
已在 docs 正式记载且这次没有新踩坑。拿不准时按「值得」处理，写一条短的。

步骤（写完直接进入汇报，不要再回来确认）：
1. 新建或更新 `pages/<主题>.md`——头部注明日期/仓库/类别（gotcha|howto|overview|decision）/状态；
   正文含 **症状 → 根因 → 解法 → 预防**，多用具体命令、路径、报错原文片段
2. 在 `index.md` 对应分类下登记一行
3. 向 `log.md` 追加 `## [YYYY-MM-DD] gotcha|howto|deploy | 一句话标题`
4. **不要自行 commit/push**：条目留在 `cijian` 仓工作区，和当次代码改动一起在汇报 diff 时列出，
   等爸爸回「提交」再提交（推送等「推送」）。本次只有沉淀条目时也一样：展示 diff 后等「提交」。

### 3. 整理（定期，自动，不要询问用户）

**增量整理**（每次写入/更新条目时顺手做）：
- `index.md` 是否已登记；漏了就补
- `log.md` 是否已追加；漏了就补
- 相关旧条目是否矛盾或过时；过时就标「已过时」并追加更正小节，不删历史

**全量整理**（至少每 30 天一次，自动判断）：
任务开始时读 `log.md`，找最后一条 `## [日期] 整理 | 全量整理`：
- 距今 < 30 天 → 不用管
- 距今 ≥ 30 天（或从未有过）→ 本次任务收尾时顺手做一遍：
  孤儿页面（`index.md` 没登记、没有来源链接）、该标「已过时」的、页面间矛盾、
  失效的相互引用、`index.md` 与 `pages/` 不一致
- 完成后在 `log.md` 追加 `## [YYYY-MM-DD] 整理 | 全量整理`，摘要一两句
- 同样不要问用户，整理结果随当批 diff 一起汇报

### 4. 纪律

- **只增不删**：条目过时就标"已过时"并追加更正小节，历史不抹
- 明文密钥/口令**永不写入**（写存放位置即可，见 env-and-secrets）
- 条目要短、事实性、可 grep；一个条目一个主题
- 已被 docs/（04 契约、05 数据模型、ADR）正式记载的设计决策，在 wiki 里放链接即可，不要复制正文

### 5. 提交前 Harness 检查清单（强制，全绿才准 push）

改动代码后逐仓执行（细则见 pages/engineering-standards.md）：

```bash
# cijian-api
cd ~/work/cijian-api && npm run typecheck && npm test && npm run build
# cijian-site
cd ~/work/cijian-site && npm run build
# cijian-agent
cd ~/work/cijian-agent && python3 -m compileall -q cijian_agent && ruff check cijian_agent
# cijian（本仓）
#    核对 llmwiki/index.md、log.md 与 docs 交叉引用一致
```

push 后确认 CI 绿：`gh run list -R xuxun22/<repo> --limit 1`——红了必须修，禁止绕过。
cijian-api 推 main 会自动上线（服务器 5 分钟 timer 拉取），部署后抽查
`https://api.whereami.cn/api/health`。
