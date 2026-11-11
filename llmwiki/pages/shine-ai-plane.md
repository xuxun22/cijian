# 看见闪光 AI 平面（agent 任务 + 家庭 Wiki）

- 日期：2026-11-11 · 仓库：cijian-api / cijian-agent / cijian-site / cijian-mp · 类别：architecture · 状态：有效

## 是什么

「看见闪光」的完整实现链路：站点/小程序提交 → API 排队（不调模型）→ 家里 agent 领任务 →
`opencode run` 执行 → 结果/视图写回 API。设计见主仓 `docs/12`、`docs/13`、ADR-008/009。

## 关键事实

- **API 不持有模型 key 与 GitHub 凭证**；`ai_tasks` 只存 payload/结果/审计。家庭 wiki 原文只在
  `github.com:xuxun22/cijian-family-wiki`（PRIVATE）+ agent 本地克隆。
- analyze：`POST /api/shine/entries` → 202 + `task_id`，agent 长轮询（≤25s）领取，20s 心跳续租，
  `POST /tasks/:id/result` 落条目并在**同一事务**入队 `shine.wiki.ingest`。
- wiki 类任务**全局串行**（同类型同时只一单）：claim SQL 用 `NOT EXISTS` 排除同类型 claimed/running。
- 视图 `PUT /api/agents/ai/views` 带 `commit_count`（`git rev-list --count HEAD`），≤ 已存值直接 409。
- agent 侧：`cijian_agent/ai/worker.py` 能力线程；无 `wiki_deploy_key` 的机器只报 `shine.analyze`。
- 模型只改文件；git commit/push 与视图发布由 worker 做（`shine-wiki` profile 禁 shell）。
- 实测：文字 analyze 7~17s、图片 12s；wiki ingest/redact 各 ~6 分钟（可接受，异步）。

## 踩坑

- **`tx()` 不支持嵌套**：报果事务里链式入队会 `cannot start a transaction within a transaction`。
  已给 `tx()` 加可重入（WeakMap 深度计数），内层并入外层。
- **小程序 `wx.request` 不支持 PATCH**（typings 也没有）：条目更新同端点挂 POST（API 已双挂），
  不要在前端用 PATCH。
- **opencode agent 目录是 `.opencode/agents/`（复数）**，正文即 system prompt；见
  [opencode-runner](opencode-runner.md)。
- **微信 `wx.chooseMedia` 后必须先上传拿 file_id**，再带 `image_file_id` 建条目；图片 24h TTL。
- **agent 子进程 env 白名单**：剔掉 `CIJIAN_*`，但保留 `HOME`（opencode 的模型登录在 `~/.local/share/opencode`），
  不要照搬「HOME 指向工作区」的设想，否则模型未登录。
- **本地全链路联调**：本地起 api（`npx tsx src/index.ts` + `CIJIAN_DATA_DIR`）+ 本地 bare wiki 仓
  （`git init --bare`，`CIJIAN_AI_WIKI_REPO` 指过去），`python3 -m cijian_agent --once` 跑一轮，避免污染真实家庭 wiki。
- **api 部署**：push 触发的 Deploy 可能因 Tailscale SSH 超时失败（dial tcp :22 timeout），
  服务器有 5 分钟自拉取 timer 兜底；失败可 `gh run rerun <id>`。

## 相关

- 成长判据与证据纪律：wiki 仓 `AGENTS.md`（5 维度、≥3 次/≥2 场景/≥3 周、达不到写「还不能判断」）。
- 契约：主仓 `docs/04-api-contract.md` v1.5；数据模型 `docs/05`；内容边界 `docs/06`。
