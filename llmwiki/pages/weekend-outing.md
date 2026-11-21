# 周六出门建议（docs/18）

> 2026-11-21 · 类别：overview · 仓库：cijian-api / cijian-agent · 状态：v1 已实现

## 是什么

每周六 08:30 给爸妈推 3 个上海亲子出门选项：按天气定室内外、联网搜真实档期、
按家里两个孩子（11/9 岁，姐姐哮喘）筛选排序、类型多样化（不连庄公园）。
爸妈回 1/2/3 选择、「都不想」跳过、「反馈：……」记偏好。
反馈**一到就固化进家庭 wiki** `family/assistant/outing.md`（真相源），
下周生成读整页 + 最近 6 次原始记录，越用越准。

## 关键事实

- **调度**：`schedules` 种子 `sch_outing_suggest`（weekly `6 08:30` → `outing.suggest`）；
  scheduler 给 payload 补 `date`（计划时间的上海日期），dedupe `sched:<id>:<next_run_at>`。
- **任务**：`outing.suggest` priority 25 / maxAttempts 2；agent 侧
  `GET /api/agents/ai/outing/input?date=` 拿孩子年龄 + 历史，然后跑
  `outing-suggest` agent（**只开 websearch**：`runner.install_websearch()` 写
  plugins+websearch 配置，不挂能力 MCP、不带家庭令牌）。
- **落库/发送**：`applyOutingResult` 校验（正好 3 个选项，缺一抛错重试）→
  `outings`（UNIQUE(date)，同日重跑覆盖）；`deliverChat` 用 `outingMessage`
  发 active 爸妈。
- **反馈**（确定性，不经过模型）：`1/2/3`、`选N`、`N.`、`都不想/下次再说`、
  `反馈|记下|记住：……`；只对今天/昨天发的最新一条生效（任意状态），
  选完仍可补反馈，隔天不再接管；写 `outing_feedback` + 置 `chosen/skipped`，回一句确认。
- **偏好固化**：反馈落库后入队 `outing.prefs`（priority 26，dedupe
  `outingprefs:<feedback_id>`）→ agent `GET /outing/feedback-input?outing_id=`
  → 追加进 wiki `family/assistant/outing.md`；下周六生成还会兜底补写。
  页面分「我们喜欢 / 不喜欢」（手工区，原样保留）与「历史反馈」
  （自动区：只追加、日期倒序、最多 32 行、按整行去重，无变化不提交）。
  下周 prompt 输入 `preferences`（整页≤4000 字）+ `history`（最近 6 次）；
  优先级：天气/安全 > preferences > history > 通勤。
- **距离**：选项带 `distance`（世纪公园为原点，常识估算，公里+通勤）；
  **搜索词不得含家/世纪公园**（隐私：家的位置不进搜索引擎）。
- **多样性**：prompt 硬规则——3 个选项类型不得相同、公园不连庄；
  类型枚举：展览/公园/活动/科普/运动/手工/演出/市集/其他。
- **配置**：`CIJIAN_OUTING_MODEL`（默认 ai_model）、`CIJIAN_OUTING_TIMEOUT`（600s）。

## 坑

- `prepare_workspace` 之后必须 `install_websearch`：隔离 XDG 里没有 websearch 插件配置时，
  模型会说「我做不到」（同 install_mcp 的老坑，只是这次不挂 MCP）。
- 解析偏好页时**只收集 `## 历史反馈` 之后的列表行**：否则手工区
  「我们喜欢 / 不喜欢」里的 bullet 会被当成历史搬到自动区并被限长挤掉。
- 自动区按整行去重：同一反馈被 wecom 重试/重复任务处理时不会重复追加；
  内容没变就返回 `skipped`，不产生空 commit。
- `outing.prefs` 只在 wiki deploy key 存在时才声明能力；否则任务留在队列，
  由下周六 `outing.suggest` 的兜底写补上。
- 反馈路由放在 wecom 回调早期、纸类触发之后；普通文本不受影响
  （只有命中模式且存在可反馈的 outing 才接管）。
- websearch 查询词只含公开信息；发给模型的输入含孩子年龄/称呼与反馈摘要
  （模型 API 使用已获家长确认）。
- **偏好真源在家庭 wiki**（Mac mini）；API `outing_feedback` 是运营副本，
  agent 报果带 `synced_feedback_ids`，API 把已固化的 `comment` 置空（`choice` 保留），
  删腾讯云不丢长期偏好。
