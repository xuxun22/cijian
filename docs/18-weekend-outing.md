# 18 · 周六出门建议（周末亲子选项）

> 状态：v1 已实现（2026-11-21）· 依赖：docs/13/14 任务平面、opencode websearch、企微通道

## 1. 目标

每周六早上 08:30，给爸妈推 3 个「今天可带孩子去」的上海亲子选项：

- 按当天天气给**室内/室外**倾向；每个选项带**距家大概距离/通勤**（家在世纪公园附近，仅作参照）；
- 覆盖不同类型（展览 / 当季景色的公园 / 特别亲子活动），**不许每次都是逛公园**；
- 适合家里两个孩子（11 岁 & 9 岁；姐姐哮喘，室外花粉/剧烈运动要提醒）；
- 联网搜索真实档期，**排序 + 筛选**后只给 3 个；
- 爸妈回 **1/2/3** 选择、**「都不想」**跳过、**「反馈：……」**记偏好；
  反馈**一到就固化进家庭 wiki**（`family/assistant/outing.md`，真源），
  下周生成时读整页 + 最近 6 次原始记录，越用越合口味；
  页面里的「我们喜欢 / 不喜欢」可爸妈手工编辑，模型优先遵守。

## 2. 链路

```
scheduler（weekly 6 08:30，dedupe sched:sch_outing_suggest:<next_run_at>）
   └─ ai_task: outing.suggest（priority 25，maxAttempts 2）
        agent：GET /api/agents/ai/outing/input?date=
          （孩子年龄 + 最近 6 次 outing 的选项/选择/反馈）
          + 读家庭 wiki 偏好页（family/assistant/outing.md）
        opencode「outing-suggest」agent：只开 websearch（install_websearch，
          不挂能力 MCP、不带家庭令牌）→ 查天气 → 分类型搜 → 排序出 3 个
        输出严格 JSON：weather + options[3]
        （兜底）把最近反馈追加进 wiki 偏好页
   └─ 报果 applyOutingResult → outings 表（UNIQUE(date)，同日重跑覆盖）
   └─ deliverChat → outingMessage → 发给 active 爸妈
爸妈回 1/2/3、「都不想」、「反馈：……」
   └─ wecom 回调确定性识别（不经过模型）→ outing_feedback 表
      + outings.status → chosen/skipped → 回一句确认
      + 入队 outing.prefs（dedupe outingprefs:<feedback_id>）
          agent：GET /api/agents/ai/outing/feedback-input?outing_id=
             → 追加进 wiki 偏好页（幂等；Mac mini 是真相源）
```

## 3. 数据模型（docs/05 同步）

```sql
outings(id, date UNIQUE, weather JSON, options JSON[3],
        status sent|chosen|skipped, chosen_no, task_id, created_at, updated_at)
outing_feedback(id, outing_id→outings, user_id, choice 1-3, comment, created_at)
schedules: sch_outing_suggest = weekly "6 08:30" → outing.suggest（Asia/Shanghai）
ai_tasks: outing.suggest（priority 25）/ outing.prefs（priority 26）
wiki: family/assistant/outing.md（偏好长期记忆，真源）
```

## 4. 提示词要点（`ai/prompts/outing-suggest.md`）

- 工具**只有 websearch**（deny * → allow websearch，steps 60，超时 600s）；
- 先搜「上海 今天 周六 天气」判室内外；再按展览/当季公园/亲子活动各搜一次；
- 硬规则：3 个选项类型不得相同；最近几次都是公园则本次最多 1 个公园；
  只推荐搜索到、档期对得上的；哮喘室外提醒；不编价格；
  距离按常识估算（世纪公园为原点，`distance` = 公里 + 通勤方式），
  **搜索词里不得出现家/世纪公园**；
- 模型默认 `CIJIAN_AI_MODEL`，可用 `CIJIAN_OUTING_MODEL` 单独指定；
  `CIJIAN_OUTING_TIMEOUT` 默认 600s。

## 5. 反馈与偏好（家庭 wiki 固化）

- 识别：`1/2/3`、`选N`、`N.`、`都不想/不想去/下次再说`、`反馈|记下|记住：……`；
- 只对**今天或昨天**发出的最新一条建议生效（任意状态）；选完仍可补「反馈：……」，
  隔天起不再接管普通聊天；数字回执只认 `1/2/3`、`1.`、`选1` 这类纯选择；
- **即时固化**：反馈落库后立刻入队 `outing.prefs`，agent 拉本次出门的反馈，
  追加到家庭 wiki `family/assistant/outing.md`；Mac 不在线时，下周六生成会兜底补写；
- **页面结构**（手工区与自动区分离，重写不丢手工内容）：
  ```markdown
  # 周六出门偏好
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

## 6. 隐私

- websearch 查询词只含公开信息（上海天气/展览/公园），不带家庭数据，
  也**不带家的位置**——距离由模型按地理常识估算，不进搜索；
- 发给模型的输入含孩子称呼/年龄与反馈摘要（家长已确认模型 API 使用）；
- **偏好真源在家庭 wiki**（Mac mini）：反馈一到就写；腾讯云的 `outing_feedback`
  只作运营副本/中转，comment 固化后置空，随时删库不丢长期偏好；
- 反馈 `comment` 由家长主动写，会进入 wiki 与模型输入；提示文案不要求填地址等敏感信息。

## 7. 验收（DoD）

- [ ] 周六 08:30 爸妈各收到一条：天气 + 3 个不同类型选项 + 回执指引；
- [ ] 回「2」→ 回复「记下了：<标题>。玩得开心！」，状态 chosen；
- [ ] 回「都不想」→ 状态 skipped，回复确认；
- [ ] 回「反馈：喜欢科普类」→ 记录，并在本次反馈后就把该行写进 wiki；
- [ ] 下周生成输入包含 `preferences`（wiki 整页）与最近 6 次 `history`；
- [ ] 同一反馈重复处理不重复追加、不产生空提交；手工区内容不被覆盖；
- [ ] 连续几周类型不重复（公园不连庄）；
- [ ] 非周六/无建议时，普通聊天不受影响。
