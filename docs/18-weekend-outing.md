# 18 · 周末亲子活动（周五晚推荐周六/周日）

> 状态：v2 已实现（2026-11-27，替代 v1「周六出门建议」）· 依赖：docs/04/05/13/14 任务平面、opencode websearch、企微通道

## 1. 目标

每周五 **19:00** 给爸妈推 1-5 个「本周末可带孩子去」的上海亲子选项（北京时间）：

- 先看**周六/周日两天天气**，据此决定室内/室外倾向；天气差时多推室内；
- 从**上海浦东出发、单程 1 小时交通圈**内挑地点，按 `minutes`（单程分钟数）由近到远排序；
- 每个选项写清**年龄适配**（2015/2017 年出生，小学阶段）、**是否收费及大概费用**、
  **预约要求与截止时间**；
- 覆盖展览 / 公园 / 亲子活动 / 公益等不同类型，避开最近 6 次，持续保持新鲜；
- 一次最多 5 个；**没有合适的就返回 0 个并说明原因**，不硬凑；
- 爸妈回 **1-N** 选择、**「都不想」**跳过、**「反馈：……」**记偏好；
  反馈一到就固化进家庭 wiki（`family/assistant/outing.md`，真源），
  下周生成时读整页 + 最近 6 次原始记录，越用越合口味。

## 2. 链路

```
scheduler（weekly 5 19:00，dedupe sched:sch_outing_suggest:<next_run_at>）
   └─ 入队时把计划日（周五）转成本周六，写入 payload.date
   └─ ai_task: outing.suggest（priority 25，maxAttempts 2）
        agent：GET /api/agents/ai/outing/input?date=<周六>
          （孩子年龄 + 本周六/周日日期 + 最近 6 次 outing 的选项/选择/反馈）
          + 读家庭 wiki 偏好页（family/assistant/outing.md）
        opencode「outing-suggest」agent：只开 websearch（install_websearch，
          不挂能力 MCP、不带家庭令牌）
          → 查周六/周日天气 → 分类型搜索 → 排 0-5 个
        输出严格 JSON：weather + reason + options[0-5]
        （兜底）把最近反馈追加进 wiki 偏好页
   └─ 报果 applyOutingResult → outings 表（date 存周六，UNIQUE(date)，同日重跑覆盖）
   └─ deliverChat → outingMessage（超 2048 字节按约 1800 字节分片）→ 发给 active 爸妈
爸妈回 1-N、「都不想」、「反馈：……」
   └─ wecom 回调确定性识别（不经过模型）→ outing_feedback 表
      + outings.status → chosen/skipped → 回一句确认
      + 入队 outing.prefs（dedupe outingprefs:<feedback_id>）
          agent：GET /api/agents/ai/outing/feedback-input?outing_id=
             → 追加进 wiki 偏好页（幂等；Mac mini 是真相源）
```

## 3. 数据模型（docs/05 同步）

```sql
outings(id, date UNIQUE /* 本周六 */, weather JSON, options JSON[0-5],
        reason, status sent|chosen|skipped, chosen_no, task_id, created_at, updated_at)
outing_feedback(id, outing_id→outings, user_id, choice 1-5, comment, created_at)
schedules: sch_outing_suggest = weekly "5 19:00" → outing.suggest（Asia/Shanghai）
ai_tasks: outing.suggest（priority 25）/ outing.prefs（priority 26）
wiki: family/assistant/outing.md（偏好长期记忆，真源）
```

`options[]` 字段：

- `no`：1..N（按 `minutes` 升序重排）；
- `title` / `type` / `indoor` / `location` / `distance`；
- `minutes`：单程交通分钟数，整数且 ≤60（排序依据）；
- `cost`：统一口径为 `免费`、`收费：<大概金额>` 或 `收费情况以现场为准`；
- `booking`：预约要求与**截止时间**；不需要预约写「无需预约」；
- `detail` / `why` / `source`。

`reason`：0 个选项时必填，说明为什么这周没有合适去处；有选项时可为空。

## 4. 日期语义

- 排程计划日是**周五**，`payload.date` 在入队时转成**本周六**；
- `outings.date` 始终存周六，历史按周六归档；文案展示「周六-周日」；
- 反馈窗口覆盖**周五（推送当晚）到周日**，周一不再接管普通聊天；
- 老库迁移：检测到旧值 `weekly 6 08:30` 时改回 `weekly 5 19:00` 并重置
  `next_run_at`，已部署实例下周五生效。

## 5. 提示词要点（`ai/prompts/outing-suggest.md`）

- 工具**只有 websearch**（deny * → allow websearch，steps 60，超时 600s）；
- 先分别搜周六、周日天气；雨/大风/严寒/高温/空气差 → 多推室内；
- 按展览 / 当季公园 / 亲子活动 / 公益等分类型搜索，避开最近 6 次；
- 硬规则：0-5 个、`minutes` ≤60 且升序、费用与预约截止必须写；
  不编价格，查不到写「收费情况以现场为准 / 建议提前确认」；
  只推荐搜索到、档期对得上的；哮喘室外提醒；
  距离按常识估算（世纪公园为原点），**搜索词里不得出现家/世纪公园**；
- 没有合适选项时返回 `options: []` 且 `reason` 非空；
- 模型默认 `CIJIAN_AI_MODEL`，可用 `CIJIAN_OUTING_MODEL` 单独指定；
  `CIJIAN_OUTING_TIMEOUT` 默认 600s。

## 6. 反馈与偏好（家庭 wiki 固化）

- 识别：`1`-`5`、`选N`、`N.`、`都不想/不想去/下次再说`、`反馈|记下|记住：……`；
- 只对**周五到周日**发出的最新一条建议生效（任意状态）；选完仍可补「反馈：……」；
  越界编号（如只有 3 个却回 5）不落库，回复「这次只有 N 个选项，回 1-N 选一个」；
- **即时固化**：反馈落库后立刻入队 `outing.prefs`，agent 拉本次出门的反馈，
  追加到家庭 wiki `family/assistant/outing.md`；Mac 不在线时，下周五生成会兜底补写；
- **页面结构**（手工区与自动区分离，重写不丢手工内容）：
  ```markdown
  # 周末亲子活动偏好
  ## 我们喜欢 / 不喜欢
  - （爸妈可手工补充）
  ## 历史反馈
  - 2026-11-21 · 爸爸 · 选了「世纪公园」
  - 2026-11-21 · 妈妈 · 反馈：喜欢动手类
  ```
  —— 只追加、按日期倒序、最多保留 32 行、同一行不重复；有变化才 `git commit/push`。
- **下周生成**：读整页（≤4000 字）作为 `preferences`，连同最近 6 次原始
  `history` 一起给模型；优先级：天气/安全 > preferences > history > 通勤。
- API 里的 `outing_feedback` 是运营副本；wiki 是真相源，删腾讯云不丢偏好。
  agent 报果带 `synced_feedback_ids`，API 只把**已写进 wiki 的 comment 置空**
  （choice 保留作运营状态），家庭手写内容不长期留在腾讯云。

## 7. 隐私

- websearch 查询词只含公开信息（上海天气/展览/公园），不带家庭数据，
  也**不带家的位置**——距离由模型按地理常识估算，不进搜索；
- 发给模型的输入含孩子称呼/年龄与反馈摘要（家长已确认模型 API 使用）；
- **偏好真源在家庭 wiki**（Mac mini）：反馈一到就写；腾讯云的 `outing_feedback`
  只作运营副本/中转，comment 固化后置空，随时删库不丢长期偏好；
- 反馈 `comment` 由家长主动写，会进入 wiki 与模型输入；提示文案不要求填地址等敏感信息。

## 8. 验收（DoD）

- [ ] 周五 19:00 爸妈各收到一条：周六/周日天气 + 0-5 个选项（按距离排序）+ 回执指引；
- [ ] 每个选项有年龄适配、`cost`（免费/收费）、`booking`（含预约截止）；
- [ ] 0 个选项时文案说明 `reason`，不硬凑；
- [ ] 5 个选项超 2048 字节时按约 1800 字节分片发送；
- [ ] 回「2」→ 回复「记下了：<标题>。玩得开心！」，状态 chosen；回 1-N 按实际数量提示；
- [ ] 回越界编号不落库，回复实际可选范围；
- [ ] 回「都不想」→ 状态 skipped，回复确认；
- [ ] 回「反馈：喜欢科普类」→ 记录，并在本次反馈后就把该行写进 wiki；
- [ ] 下周生成输入包含 `preferences`（wiki 整页）与最近 6 次 `history`；
- [ ] 同一反馈重复处理不重复追加、不产生空提交；手工区内容不被覆盖；
- [ ] 连续几周类型不重复（公园不连庄）；
- [ ] 非周五至周日/无建议时，普通聊天不受影响。
