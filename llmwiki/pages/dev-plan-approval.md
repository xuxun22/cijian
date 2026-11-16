# 编码通道「计划先行」+ 小程序看板

> 日期：2026-11-16 · 仓库：cijian-api / cijian-agent / cijian-mp · 类别：howto + gotcha · 状态：已落地

## 是什么

编码通道原先是「提需求 → 一次性跑完 → 看 diff」，现在改成：

```
提需求 → planning（只读 dev-plan 出方案）
       → waiting_plan（等爸爸批）──批准──→ queued → execute（dev agent）
       → waiting_input（执行中卡住，等选项）──回答──→ 继续 execute
       → done（等提交/算了/继续改）→ committed / discarded
```

`dev_tasks.status` 增加 `planning` / `waiting_plan` / `waiting_input`；`dev_tasks` 增加 `plan` / `question`。

## 关键实现点

- **两段用同一个任务类型** `dev.task`，payload 里 `phase: "plan" | "execute"`。不要新增 `dev.plan` 类型：`ai.ts` 的串行锁是按 type 的，两种类型会并发撞同一个 worktree。
- plan agent 是只读 profile：`cijian_agent/ai/prompts/dev-plan.md`（read/glob/grep + 只读 shell，禁 edit/npm/commit）。
- 执行 agent 卡住时写工作区根目录 `.cijian-ask.json`：
  ```json
  {"question": "两个标签放哪？", "options": ["顶部", "底部导航"]}
  ```
  `devwork.take_question()` 读取并删除（在 `stage_and_stat` 之前），报 `needs_input`；API 落 `waiting_input`。
- 批准执行时用**新会话**、复用同一个 worktree；计划会话只用于讨论，不带进改代码。
- 小程序：`pages/dev/board` + `pages/dev/detail`，新增「开发」tab；API 是 JWT 面 `/api/assistant/dev/*`。

## 踩坑 1：小程序 JWT 用户 ≠ 企业微信用户

- `users.id` 是 `u_…`（wx.login 建的用户），`dev_tasks.requester` 是企微 UserID（如 `XuXun`）。
- 直接拿 `c.get('userId')` 查任务永远为空。
- 解法：`users` 加 `wecom_user_id`；`wx-login` 带名字时按 `wecom_users.name`/`user_id` 精确匹配自动绑，匹配不到在看板里手动绑一次（`POST /api/assistant/dev/bind`）。只有 `role=dad` 能看看板。
- 绑定按姓名是「家庭内信任」模型；真要收紧，需要再加一次口令/验证码。

## 踩坑 2：同毫秒入库，`ORDER BY created_at DESC` 会挑错

- 计划任务和执行任务可能在同一毫秒创建，`created_at` 相同，SQLite 返回顺序不稳定。
- 单测里表现为：`reportExecute()` 把结果报给了计划任务，状态一直是 `waiting_plan`。
- 解法：所有「最近一条」和看板查询加 `rowid DESC` 兜底；测试里取最新 ai_task 也按 `rowid`。

## 踩坑 3：问题文件在 worktree 根目录

- `.cijian-ask.json` 放在各仓库子目录之外，本身不会进 diff；但仍要在读完后删除，避免下一轮误读。
- 顺序必须是：`take_question()` → `verify()` → `stage_and_stat()`。

## 踩坑 4：AI 任务异常不会走 applyDevResult

- agent 超时/崩溃走 `/api/agents/tasks/:id/fail`，只更新 `ai_tasks`，不会调用 `applyDevResult`。
- 结果是 `dev_tasks` 永远停在 `planning` / `queued`，看板一直显示「在出方案」。
- 解法：`reportAiFail` 返回终态 `failed` 后调用 `markDevTaskFailed`；可重试的失败先保持原状态等重派。

## 踩坑 5：能力面也要限爸爸

- 小程序 JWT 面有 `requireDad`，但 MCP 能力面（`/api/assistant/cap/dev/*`）原来只校验 requester。
- 孩子说一句「批准」，worker 也能替爸爸批计划。
- 解法：所有 `/dev` 能力路由统一 `requireDevDad`（查 `wecom_users.role`），并给对话提示词注入 `<身份>role=…</身份>`。

## 验证

```bash
cd ~/work/cijian-api && npm run typecheck && npm test          # 110 项
cd ~/work/cijian-agent && python3 -m unittest discover -s tests # 33 项
cd ~/work/cijian-mp && npm run typecheck
```

真实链路：提需求 → 微信收到方案 → 回「批准」→ 执行 → 改完通知 → 小程序可见并提交；执行中造一个问题 → 小程序点选项 → 继续完成。

## 相关

- 设计正本：`docs/14-assistant-plan.md` §9.8、`docs/15-assistant-architecture.md` §4.5
- 小程序计划：`docs/09-miniprogram-plan.md` M-mp-5
