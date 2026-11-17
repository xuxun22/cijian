# 记忆长短期分层（命中观测 / 60 天归档 / memory_search）

- 日期：2026-11-18 · 仓库：cijian-agent（本文在 cijian 仓） · 类别：howto · 状态：现行（归档默认 dry-run）

## 是什么

家庭记忆原来只有「三层 + 截断」：`preferences.md` 全量、`facts.md` 近 80 行、`notes/YYYY-MM.md`
只读**最新一个月最后 40 行**——更早的笔记不加载，等于黑洞。现在改成短期（现役全量注入）+
长期（`archive/` 按需检索），并记录**命中**来决定谁留在短期。

## 关键事实

- **动态 id**：`cijian_agent/ai/memory.py`，id = `m-` + 内容 sha1 前 6 位。文件保持干净不带 id，
  注入时给每行加 `[m-xxxx]`；同一内容 id 稳定、可重复计算，无需迁移存量文件。
- **命中信号**：模型回答用到记忆时输出 `<used>m-xxxx</used>`（worker 剥掉，用户不可见）；
  另有**关键词兜底**——问题与记忆行中文二元词重合 ≥2 记命中（停用词表去掉「今天/什么/我们」等）。
- **命中日志**：`<state>/ai/memory-hits.log`，一行一条 `{id, at, src}`。用**追加**而不是 JSON 读改写，
  因为 worker 和 MCP（`memory_search`）是两个进程会同时写。
- **每日回顾**：每天 23:30 后（`CIJIAN_AI_MEMORY_REVIEW_TIME`），agent 线程读本地对话历史
  `<state>/ai/chat-history/YYYY-MM.log`（每轮对话由 worker 追加，**14 天滚动**），
  用 `assistant-memory-review` 提示词提炼 ≤5 条候选写 wiki。失败也记日期，避免整晚每分钟重试。
- **每周归档**：notes/facts 行 60 天未命中（never hit 则看 first_seen，存 `memory-meta.json`）→
  移入 `family/assistant/archive/{notes,facts}.md`；**preferences/profile 永不自动归档**。
  **默认 dry-run**（`CIJIAN_AI_MEMORY_ARCHIVE_DRY_RUN=1`），只记日志不动文件；观察两周再开。
- **晋升**：archive 条目 30 天内被 `memory_search` 搜中 ≥2 次（`CIJIAN_AI_MEMORY_PROMOTE_HITS`）
  → 移回现役（notes 回当月、facts 回 facts.md），防止长期变死档。
- **长期检索**：MCP 工具 `memory_search`（`mcp_server.py`），只读 wiki 现役 + `archive/`，
  中文二元词打分取 top 5，带来源文件与 id；命中同样写日志。
- **提示词**（assistant-chat v9）：用记忆要标 `<used>`；问很久以前的事 / 说「以前说过」/
  当前注入记忆里没有 → 先调 `cijian_memory_search`。
- **配置**：`CIJIAN_AI_MEMORY_ARCHIVE_DAYS=60`、`CIJIAN_AI_MEMORY_ARCHIVE_DRY_RUN=1`、
  `CIJIAN_AI_MEMORY_PROMOTE_HITS=2`、`CIJIAN_AI_MEMORY_REVIEW_TIME=23:30`、`CIJIAN_AI_CHAT_HISTORY_DAYS=14`。
- **已验证**：63 个单测（id 幂等/used 解析/关键词/命中日志/dry-run/真归档/晋升/检索排序）；
  deepseek-flash 真模型提炼样例正确；上线首轮维护输出 `{'archived': 0, 'promoted': 0, 'dry_run': True}`
  （现有记忆 first_seen=当天，60 天后才进判定）。

## 症状 → 解法

- **微信里问旧事答不上来** → 先看当前注入记忆里有没有：`_memory_context()`（preferences 全量、
  facts 近 80 行、最新月 notes 后 40 行）。旧事应走 `memory_search`；查 `cijian-mcp.log` 有没有调用。
- **记忆回顾没跑** → 看 `~/Library/Logs/cijian-agent.err.log` 的「每日记忆回顾」；
  检查 `<state>/ai/chat-history/YYYY-MM.log` 是否有当天内容、`.memory-review-state` 是否已是今天。
- **归档误伤（常用记忆被移走）** → 先确认是否 dry-run；真归档后可从 git 恢复，
  或让 `memory_search` 命中两次自动晋升。阈值/干跑开关都是环境变量。
- **命中统计很少** → 模型常漏标 `<used>`，关键词兜底也不重合时就没有记录；属正常。
  真需要准确统计时，改提示词或考虑 embedding（当前刻意不引）。
- **notes 老月份完全读不到（旧行为）** → 已是历史问题：现在老内容在 `archive/` 可由
  `memory_search` 检索；若发现连 archive 都没归档到，检查每周维护日志与 `memory-meta.json`。

## 验证

```bash
cd ~/work/cijian-agent
python3 -m unittest discover -s tests && ruff check cijian_agent tests
tail -f ~/Library/Logs/cijian-agent.err.log | grep -E "记忆回顾|记忆归档"
# 直接跑一次当天回顾（有历史时）
python3 - <<'PY'
from cijian_agent.ai.worker import AiWorker
# 见 tests/test_memory_layers.py 的构造方式
PY
```
