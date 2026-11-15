# 家庭助手架构（微信 → 任务平面 → agent）

> 更新：2026-11-15 · 类别：overview · 状态：现行
> 正式设计见 `docs/15-assistant-architecture.md`（架构图 + 六条流程图），本页只记要点与查证入口。

## 三层

1. **入站**（cijian-api `routes/wecom.ts`）：企业微信回调 → 按 `msg_id` 去重 → 记 `wecom_messages` → 签**能力令牌**（15 min，sub=说话人）→ 入队 `ai_tasks(chat.reply)`。
2. **执行**（Mac mini `cijian-agent`）：长轮询领任务 → `AiWorker` 分派 → opencode 子进程（`assistant-chat` / `dev` agent）→ 报果。
3. **回消息**：由 API 的 `deliverChat` 发微信，agent 不直接发（防重发、离线也有兜底话术）。

## 三种身份（越权边界）

| 身份 | 持有者 | 范围 |
|---|---|---|
| 家庭用户 | `wecom_users`（role；只有 dad 能批仓库） | 数据归属、审批 |
| agent key | 本机 `agent.env` | 心跳/领取/报果/素材 |
| 能力令牌 | API 每次入队临时签，放 payload | 只能 `/api/assistant/cap/*` |

对话进程没有文件/shell 权限，只能调 MCP 的 26 个工具；编码 agent 只能动自己的 worktree，commit 由 worker 做。

## 两个队列别混

- `print_jobs`：短任务，`/api/agent/claims`，防重打靠租约 + 本地 `state.json` 的 `phase=submitted`；
- `ai_tasks`：长任务，`/api/agent/ai/tasks/claim` 长轮询 25s、心跳续租、`maxAttempts` 重试、`serialized` 串行（`dev.task`、wiki 类）、终态 90 天清理。

## 小模型不稳定 → worker 兜底

固定意图不交给模型：身份类 canned、裸「批准」、看板（在改/待确认/已提交）、裸「提交/算了」都由 worker 直接执行（`_repo_approve_reply` / `_board_reply` / `_decide_reply`）。模型侧再加：`CIJIAN_USER_TEXT` 原文兜底、工具名写全 `cijian_dev_task`、「做不到」重试一次。

## 技能自改进 + 记忆分层（2026-11-15）

- 技能仍在 wiki `family/assistant/skills/`，归档在**同级** `family/assistant/skills-archive/`
  （放 skills 里会被 opencode 递归扫到，见 [gotcha-skill-archive-recursive](gotcha-skill-archive-recursive.md)）；
- 遥测/台账在本地 `<state>/ai/`：`skills-usage.json`（use/view/patch）、`skills-ledger.jsonl`、`skills-blobs/`；
- 能力工具从 26 → 30：新增 `skill_stats` / `skill_history` / `skill_restore` / `skill_pin`（后两个只有 dad 能做）；
- 回合后回顾（`assistant.skill.review`）：纠正词即时触发 + 每天 21:40 兜底；模型只出 JSON，
  lint/写盘/台账/commit/通知都在 worker；没改不发；回顾模型用 `deepseek/deepseek-flash`，
  避免和对话抢免费额度（见 [gotcha-opencode-free-quota](gotcha-opencode-free-quota.md)）；
- 记忆三层：`preferences.md`（全量注入）/ `facts.md`（近 80 行）/ `notes/YYYY-MM.md`（近 40 行）。

## 查证入口

```bash
tail -f ~/Library/Logs/cijian-mcp.log        # 每次工具调用 + 参数
tail -f ~/Library/Logs/cijian-agent.err.log  # 任务领取/完成/失败
ssh ubuntu@43.173.111.191 "docker exec app-api-1 node -e \"const{DatabaseSync}=require('node:sqlite');const d=new DatabaseSync('/data/cijian.db');console.table(d.prepare('select type,status,count(*) c from ai_tasks group by 1,2').all())\""
```
