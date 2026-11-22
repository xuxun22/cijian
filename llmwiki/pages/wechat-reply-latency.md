# 微信回复慢：图片无对话通路 + 45s 防抖 + 慢链路（耗时拆解）

> 更新：2026-11-22 · 仓库：cijian-agent / cijian-api · 类别：gotcha · 状态：现行（改进计划已定，未实施）

## 症状

- 发图片 ≈1 分钟才有回复（识别为试卷/口算时）；不是试卷的图**永远沉默**（`silent_other: true`）。
- 对着图片提问，助手回「这张图我看不到内容，你把题目打出来」（实例：11-21 20:59 rachel「第7题不会」）。
- 文字回复普遍 15~30s，重试场景 40~60s；ack「收到，我想一下」8~20s 后才来。

## 根因（耗时拆解，2026-11-22 实测）

### 图片路径（~60s 起步）

`routes/wecom.ts`：图片消息**不产生 chat 任务**，只记消息 + `upsertPhotoBatch`（45s 静默防抖，`PHOTO_BATCH_DELAY_MS`）。之后：5s tick 循环 → 服务端下载 media → 入队 `paper.ingest` → agent 从**美国服务器**拉中转文件（家宽 RTT ~350ms、丢包 0~20%）→ vision（deepseek/deepseek-flash）分类+切题 → 预览回复。

- 1 张图 vision 12s（最好情况），实测也有 92s/33s；2 张 190s。
- **45s 防抖 + 12s vision ≈ 用户口中的「1 分钟」**。
- `chat.reply` 的 payload 只塞一行提示词「你看不到画面内容，不要描述它」——模型看图能力从未接入对话（`worker._chat` 只传 media_id 字符串；`runner.run` 明明已有 `images=[...]` → `--file` 附件能力，papers 管线在用）。

### 文字路径（15~30s）

- 排队等待 ≈0s（长轮询正常时秒领）。
- glm-5.3-flash 首轮推理 **10~13s**（含记忆注入的大 prompt），工具轮再 +5~8s。
- `_chat` 的 search-retry / dev-retry 各再跑一整轮 → 28~60s 长尾；额度兜底重试同样翻倍。
- ack 兜底默认 20s（`CIJIAN_WECOM_ACK_DELAY_MS`）——回复 <20s 到达时用户全程零反馈。

### 网络层（偶发 +60s）

- agent → api.whereami.cn（腾讯云美国圣克拉拉）领取偶发 502/read timeout，退避指数到 60s。日志累计 9642 条领取异常：11-11~14 每天 3000+（迁移前），近期 4~43/天。
- 图片中转文件下载走同一慢链路，是 vision 任务 92~190s 的主要嫌疑。

## 顺手发现的 bug（已修，2026-11-22）

- **papers 投递扫描循环每 30s 报 `UNIQUE constraint failed: papers.id`（11-21 21:15 起）**：
  根因是 `PapersWatcher._reconcile` 的 known 只查 `status='ingesting'`，而 AirDrop 卷进 preview 后
  **目录保留**（预览要用原图）→ 每轮重复 INSERT 同 id → 异常炸掉整轮扫描，**AirDrop 投递管线停摆**。
  修复：known 覆盖所有状态（`list_papers()` 不带 status），回归测试
  `test_reconcile_skips_dirs_with_row_in_any_status`。agent 992a6be。
- 11-20 16:56 photo auto 分流出现过同因 failed task（paper_intake 幂等没兜住并发）——本次改造后
  收集路径统一走 `pendingPaperImages` + 用户级互斥，该场景已覆盖；如再现有新证据再查。

## 解法 / 改进计划

**P0（图片体验）——2026-11-22 已实施（待部署 + E2E）**

api 侧（`paper.ts` / `wecom.ts` / `config.ts`）：
1. 自适应防抖：首图 8s 短窗口（`CIJIAN_WECOM_PHOTO_FIRST_DELAY_MS`，`upsertPhotoBatch` 返回是否首图），
   窗口内来第二张才升级 45s 完整防抖——单图不再陪跑多页卷。
2. 首图即时回执「收到，我看看」（仅首图一次）；回调内同步 `reservePaperImages` 登记，
   异步**预下载**企微 media 存 1h 中转并 `setPaperIntakeFile` 回填——下载移出关键路径。
3. `consumePhotoForChat`：文本带 `recent_media_id` 时——未被分流占用且已预下载 → 删行消费
   （图归对话，错题本不抢）；已被占用 → 只读共享 file（对话看图 + 分流预览并存）；
   payload 新增 `recent_file_id`。
4. 收卷路径与 auto 分流 tick 改用 `pendingPaperImages`（复用预下载 file，缺的现下载兜底）；
   用户级互斥 `beginCollect/endCollect` 替代原「先查后抢」防并发（改 pending 语义后必须，见下）。
5. **缩图未做**（对批准方案的偏离）：papers vision 靠原图分辨率读多页试卷，缩图有识别质量
   回归风险，且预下载前置后下载已不在关键路径——收益 3~5s 不值。留观察项：先看 agent 拉图耗时数据。

agent 侧（`config.py` / `ai/worker.py` / `papers/ingest.py`）：
6. `CIJIAN_CHAT_VISION_MODEL`（空=跟主模型）：带图轮次切看图模型；部署配 `deepseek/deepseek-flash`
   （已验证有视觉、与主模型不同家）。glm-5.3-flash 是否多模态未验证（shell 401，见下），E2E 再试。
7. `_chat` 收 `recent_file_id` → `_fetch_chat_image` 拉本地 tmp → `runner.run(images=[...])`；
   提示词删「你看不到画面内容」改为「已作为附件附在消息里」；下载失败/非图降级纯文本；
   打印 media_id 透传不变。
8. `ingest_paper` kind=other 自动分流话术：不再静默，回引导话术
   （「图收到了，看着不像试卷或口算……要我看图直接说」）；`silent_other` 参数名保留、语义改为
   「自动分流场景话术」。

**测试**：api 183（新增自适应窗口/预下载复用/消费三态/图片回调通路）；
agent 154（新增 ChatVisionTest 四例：附件+模型切换/下载失败降级/非图/未配模型）。
新旧部署任意顺序兼容（旧 agent 忽略 `recent_file_id`，新 agent 缺字段自动降级）。

**踩坑（测试）**：wecom.test.ts 的前置文本测试没 stub fetch → `ensureUser` 的 getUserName
真网络请求把 WecomClient 的 token `inflight` 占住几秒 → 后续图片测试的 sendText 复用这个
注定失败的 inflight → 首图回执「没发出去」。修法：前置测试也 stub。单跑过、全量挂的
典型测试间干扰，值得记住。

**P1（文字提速，未做）**：ack 20s→8s；重试轮短预算；「第N题不会」直达 vision。

**P2（结构，未做）**：tailscale/迁region；papers UNIQUE 循环 bug；分阶段耗时观测。

## 预防

- 新消息类型接入时先问一句「模型看得到内容吗」——通道存在（`--file`）≠ 已接线。
- 防抖/静默类窗口必须配即时用户反馈，否则用户感知就是「死了」。
- 慢链路上的文件中转要并行/前置，别串在关键路径上。

## 相关

- [assistant-architecture](assistant-architecture.md)（三层架构与两个队列）
- [papers-pipeline](papers-pipeline.md)（错题本管线，vision 细节）
- [checkin-pipeline](checkin-pipeline.md)（美国服务器慢链路的数据）
