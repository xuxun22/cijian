# 周末亲子活动（docs/18）

> 2026-11-27 · 类别：overview · 仓库：cijian-api / cijian-agent · 状态：v2 已实现

## 是什么

每周五 19:00 给爸妈推 0-5 个本周六/周日可去的上海亲子地点：先查两天天气定室内外，
从浦东出发 1 小时交通圈内挑，按单程分钟数由近到远排序；每个选项写清年龄适配、
费用（免费/收费）、预约截止。没有合适的就返回 0 个并说明原因，不硬凑。
爸妈回 1-N 选择、「都不想」跳过、「反馈：……」记偏好。
反馈**一到就固化进家庭 wiki** `family/assistant/outing.md`（真相源），
下周生成读整页 + 最近 6 次原始记录，越用越准。

## 关键事实

- **调度**：`schedules` 种子 `sch_outing_suggest`（weekly `5 19:00` → `outing.suggest`）；
  入队时把计划日（周五）转成**本周六**写入 `payload.date`，dedupe `sched:<id>:<next_run_at>`；
  老库旧值 `6 08:30` 会自动迁移并重置 `next_run_at`。
- **日期语义**：`outings.date` 统一存周六，历史按周六归档；文案展示「周六-周日」；
  反馈窗口覆盖周五到周日（周一不再接管普通聊天）。
- **任务**：`outing.suggest` priority 25 / maxAttempts 2；agent 侧
  `GET /api/agents/ai/outing/input?date=<周六>` 拿孩子年龄、`weekend` 与历史，然后跑
  `outing-suggest` agent（**只开 websearch**：`runner.install_websearch()` 写
  plugins+websearch 配置，不挂能力 MCP、不带家庭令牌）。
- **落库/发送**：`applyOutingResult` 校验（0-5 个、`minutes` ≤60、按 `minutes` 升序、
  0 个必须有 `reason`）→ `outings`（UNIQUE(date)，同日重跑覆盖）；
  `deliverChat` 用 `outingMessage` 发 active 爸妈，超 2048 字节按约 1800 字节分片。
- **选项字段**：`minutes`（单程分钟数，排序依据）、`cost`（`免费` / `收费：…` /
  `收费情况以现场为准`）、`booking`（预约要求与截止时间）。
- **反馈**（确定性，不经过模型）：`1`-`5`、`选N`、`N.`、`都不想/下次再说`、
  `反馈|记下|记住：……`；只对周五到周日发的最新一条生效（任意状态），
  选完仍可补反馈；越界编号不落库，回复实际可选范围。
- **偏好固化**：反馈落库后入队 `outing.prefs`（priority 26，dedupe
  `outingprefs:<feedback_id>`）→ agent `GET /outing/feedback-input?outing_id=`
  → 追加进 wiki `family/assistant/outing.md`；下周五生成还会兜底补写。
  页面分「我们喜欢 / 不喜欢」（手工区，原样保留）与「历史反馈」
  （自动区：只追加、日期倒序、最多 32 行、按整行去重，无变化不提交）。
  下周 prompt 输入 `preferences`（整页≤4000 字）+ `history`（最近 6 次）；
  优先级：天气/安全 > preferences > history > 通勤。
- **距离**：选项带 `distance`（世纪公园为原点，常识估算，公里+通勤）与 `minutes`；
  **搜索词不得含家/世纪公园**（隐私：家的位置不进搜索引擎）。
- **多样性**：prompt 硬规则——避开最近 6 次、公园不连庄；
  类型枚举：展览/公园/活动/科普/运动/手工/演出/市集/公益/其他。
- **配置**：`CIJIAN_OUTING_MODEL`（默认 ai_model）、`CIJIAN_OUTING_TIMEOUT`（600s）。

## 坑

- `prepare_workspace` 之后必须 `install_websearch`：隔离 XDG 里没有 websearch 插件配置时，
  模型会说「我做不到」（同 install_mcp 的老坑，只是这次不挂 MCP）。
- 解析偏好页时**只收集 `## 历史反馈` 之后的列表行**：否则手工区
  「我们喜欢 / 不喜欢」里的 bullet 会被当成历史搬到自动区并被限长挤掉。
- 自动区按整行去重：同一反馈被 wecom 重试/重复任务处理时不会重复追加；
  内容没变就返回 `skipped`，不产生空 commit。
- `outing.prefs` 只在 wiki deploy key 存在时才声明能力；否则任务留在队列，
  由下周五 `outing.suggest` 的兜底写补上。
- **新增任务类型必须同时加进 `AiWorker.capabilities()`**：只加 API `TASK_TYPES`
  会让任务永远停在 `queued`。本次 `outing.suggest` 就漏了（2026-11-21 实发时发现，
  agent 重启后日志只有「AI 任务并发槽」、没有领取记录；修于 4a6a309）。
- `CIJIAN_AI_MODEL` 的 GLM 周额度打满时报 `provider.quota: Usage limit reached`；
  出门任务在 `~/.config/cijian/agent.env` 单独设 `CIJIAN_OUTING_MODEL=deepseek/deepseek-flash`
  （实测 43s 出结果），不必等 5 小时额度重置。
- 反馈路由放在 wecom 回调早期、纸类触发之后；普通文本不受影响
  （只有命中模式且存在可反馈的 outing 才接管）。
- websearch 查询词只含公开信息；发给模型的输入含孩子年龄/称呼与反馈摘要
  （模型 API 使用已获家长确认）。
- **偏好真源在家庭 wiki**（Mac mini）；API `outing_feedback` 是运营副本，
  agent 报果带 `synced_feedback_ids`，API 把已固化的 `comment` 置空（`choice` 保留），
  删腾讯云不丢长期偏好。
