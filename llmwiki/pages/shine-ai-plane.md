# 看见闪光 AI 平面（agent 任务 + 家庭 Wiki）

- 日期：2026-11-11 · 仓库：cijian-api / cijian-agent / cijian-site / cijian-mp · 类别：architecture · 状态：有效

## 是什么

「看见闪光」的完整实现链路：站点/小程序提交 → API 排队（不调模型）→ 家里 agent 领任务 →
`opencode run` 执行 → 结果/视图写回 API。设计见主仓 `docs/12`、`docs/13`、ADR-008/009。

## 关键事实

- **v2 每日看见（2026-11-20 决策 + P1 实现）**：`shine.daily` 每天 20:45 由 scheduler 入队，
  agent `_daily` 生成（`shine-daily-v1`），API 落 `shine_dailies` 并推给 active 爸妈；每天按日期
  指定一人「今天你来说」；微信回「说了 / 还没说 / 他笑了 / 换我说」走确定性意图；21:30 只跟催一次。
  小程序不再有闪光 tab，微信是主入口；网页 `/api/shine/daily` 只读档案。见 `docs/12 §0`。
- **每日看见的素材**：当天打卡（按 `checkin_projects.child` 归属，不混家庭项目）+ 近 7 天打卡基线 +
  近 7 天手动观察 + `growth.next_observation` + 最近反馈；没有素材输出 `invite`，不硬夸。
- **只有完成数据时，notice 不能只写一句描述**：必须给 `ask_back`（轻问题）+ `deeper`（过程/方法/难点），
  按活动名选问题（二胡问哪一段/哪句卡、口算问哪题易错/怎么检查、跳绳问哪组最累/怎么找节奏）；
  不要写「今天有两条记录」这种系统口吻。否则家长收到会觉得单薄、没法接着聊。
- **孩子**：`shine_children` 种入 `sc_buding`/`sc_naicha`，每日按日期轮换；`sc_default` 保留给历史条目。
  网页手动记录现在可选孩子；`GET /api/shine/entries` 省略 `child_id` = 全部孩子。
- **API 不持有模型 key 与 GitHub 凭证**；`ai_tasks` 只存 payload/结果/审计。家庭 wiki 原文只在
  `github.com:xuxun22/cijian-family-wiki`（PRIVATE）+ agent 本地克隆。
- analyze：`POST /api/shine/entries` → 202 + `task_id`，agent 长轮询（≤25s）领取，20s 心跳续租，
  `POST /tasks/:id/result` 落条目并在**同一事务**入队 `shine.wiki.ingest`。
- wiki 类任务**全局串行**：写家庭 wiki 的任务（`shine.wiki.*` / `shine.review.*` / `shine.daily` /
  `assistant.wiki.write` / `assistant.skill.review`）同属一个 **wiki 组**，跨类型同时只一单。
- 视图 `PUT /api/agents/ai/views` 带 `commit_count`（`git rev-list --count HEAD`），≤ 已存值直接 409。
- agent 侧：`cijian_agent/ai/worker.py` 能力线程；无 `wiki_deploy_key` 的机器不报 wiki 类任务，但仍报 `shine.analyze`/`shine.daily`（每日看见可生成，wiki 落档 best-effort）。
- 模型只改文件；git commit/push 与视图发布由 worker 做（`shine-wiki` profile 禁 shell）。
- 实测：文字 analyze 7~17s、图片 12s；wiki ingest/redact 各 ~6 分钟（可接受，异步）。
- **P1 单测**：cijian-api 146 绿、cijian-agent 122 绿；site build / mp typecheck 绿（2026-11-20）。

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
- **每日看见也写 wiki，必须进 wiki 组串行**：只按「同类型 serialized」挡不住 `shine.daily` 与
  `shine.wiki.ingest` 同时改同一个 git 仓；claim SQL 的跨类型 `NOT EXISTS` 是必须的。
- **scheduler 的每日日期用「计划时间」算**：`shanghaiToday()` 在 tick 晚一点（跨零点）会串天；
  用 `Intl` 按 `next_run_at` 取上海日期。
- **测试 mock 企业微信的 msgid 必须唯一**：`wecom_messages.msg_id` 有 UNIQUE，两个 send 同毫秒
  返回同一个 `Date.now()` 会触发 `UNIQUE constraint failed`；生产由企微保证唯一。
- **`GET /api/shine/entries` 省略 child_id = 全部孩子**（v1.6）：网页档案要同时显示布丁/奶茶；
  `POST /entries` 仍默认 `sc_default`，所以网页表单必须显式带 `child_id`。
- **每日卡最终态是「家长说没说」**：`shine_daily_feedback` 以 (daily_id, user_id) 唯一；
  「他笑了」这类反应默认 `said=1`，避免家长只回反应时被当成没说。

## 相关

- 成长判据与证据纪律：wiki 仓 `AGENTS.md`（5 维度、≥3 次/≥2 场景/≥3 周、达不到写「还不能判断」）。
- 契约：主仓 `docs/04-api-contract.md` v1.5；数据模型 `docs/05`；内容边界 `docs/06`。
