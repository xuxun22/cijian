# 错题本管线（docs/17 实现）

> 2026-11-20 · 类别：overview · 仓库：cijian-agent / cijian-api / cijian-mp · 状态：第 1 步已上线

## 是什么

「习题整理」：试卷拍照投递 → AI 识别切题判错 → 本机错题库 → 一句话出复习卷
（原题重组 / AI 变式）→ 企微文件消息直发。设计真相源 `docs/17-exercise-plan.md`。

**隐私铁律**：真相源是 Mac mini，服务器只是 ≤7 天缓存/通道（判据=随时删腾讯云不丢数据）。

## 已落地（2026-11-20 第 1 步）

- 模块 `cijian_agent/papers/{store.py,watch.py}`；背景能力名 **`papers`**
  （`registry.BACKGROUND`，`CIJIAN_HANDLERS` 需含 `papers`）。
- 本地库 `~/.local/share/cijian-agent/papers/papers.db`（stdlib sqlite，WAL）：
  `children / papers / questions / sheets / meta`；`papers.child_id` 允许 NULL
  （识别前不知道是谁），`files_dir` 记原图目录。
- 孩子种子：布丁 `ch_buding` entry_year=2022、奶茶 `ch_naicha` entry_year=2024；
  年级 = 当前学年 − entry_year + 1，**9/1 自动进级**（`grade_for`，永不手工改）。
- 扫描：inbox 默认 `~/Downloads`（AirDrop 落点），图片后缀
  `.jpg/.jpeg/.png/.heic/.heif/.webp`；稳定判定同 checkin（首见静置 >60s，
  或连续两轮同大小且静置 5s）；水位线 `last_seen-600` 防吞历史。
  **落地时间 `arrival=max(mtime,birthtime)`**——AirDrop 会保留拍摄 mtime，
  只看 mtime 会把「昨天拍的卷今天投」当历史文件跳过。
- 分组：相邻图片 **mtime 间隔 ≤180s**（`CIJIAN_PAPERS_GROUP_GAP`）= 同一份卷的多页；
  每页命名 `p01__原名` 保证页序；移入 `<papers>/inbox/<pp_id>/`；
  建 `papers` 行 `status=ingesting`，等第 2 步识别归属。
- 幂等：处理即移出 inbox；启动 `reconcile` 认领残留 `pp_*` 目录（移文件后崩溃不丢卷）。
- 配置：`CIJIAN_PAPERS_DIR`（默认 `<state>/papers`）、`CIJIAN_PAPERS_INBOX`、
  `CIJIAN_PAPERS_SCAN_INTERVAL`（30s）、`CIJIAN_PAPERS_GROUP_GAP`（180s）。

## 已落地（2026-11-20 第 2 步，本地引擎）

- `cijian_agent/papers/ingest.py` + `ai/prompts/paper-ingest.md`（agent 名 `paper-ingest`）：
  多页多图（`runner.run(images=[...])`，≤8 页）→ 严格 JSON（`runner.extract_json`）→
  校验（题号/题干/对错/标签，重复题号保留首条）→ 归属 → 写库 `status=preview`。
- 归属顺序：卷面姓名/昵称（归一化、去「同学/的卷」）→ 印刷年级唯一匹配当前学年 →
  `asked`（预览里问「回『布丁的』…」）。**姓名优先于年级**。
- 单元归一：`第X单元`/`Unit X`（中文数字 1~99）→ int；期中/期末 → None。
- 写库：`questions` 覆盖式（重识别不累加）；`stats` 存 total/wrong/uncertain/attribution/name_hint；
  归属确定后原图 `inbox/<pp>/` → `originals/<child>/<yyyy-mm>/<pp>/`，未归属留在 inbox。
- 预览文案：`奶茶 · 3年级数学 · 第4单元：5 题错 3—— 分数加减×2、口算×1。` +
  不确定题号 + 「回『入库』或告诉我哪里认错了」。
- 本地联调：`cd ~/work/cijian-agent && python3 -m cijian_agent.papers.ingest <pp_id>`
  （自动读 `~/.config/cijian/agent.env`，不需要 export）。
- **未接线**：AirDrop 分组封口后不会自动识别，也没有微信预览/确认——属第 3 步
  （api 微信图入口 + 通知通道 + 企微文件直发）。

## 已落地（2026-11-20 第 3 步，微信入口 + 确认回路）

- **入口**：微信连发照片后回「收卷 / 收一下卷 / 识别试卷 / 这是试卷 / 收错题」。
  api 取该用户 **15 分钟**内 `wecom_messages` 的图片（`paper_intake` 按 MsgId 幂等，
  同张照片只进一份卷），按发送时间升序 → 页序。
- **中转**：照片下载进 `files` 表（`saveFile` 支持自定义 TTL，错题本用 **1h**），
  payload 只带 `file_id`；worker 取走后，识别成功 → `deliverChat` 里**立即删文件 + 行 + intake**；
  失败则靠 1h TTL + sweeper 兜底。删服务器不丢数据（本地已落盘）。
- **任务类型**：`paper.ingest`（priority 12，maxAttempts 1，serialized）、
  `paper.confirm`（14，2，serialized）；worker 心跳能力已包含二者。
- **预览**：`deliverChat` 对 paper.* 直接发结果文本给 `payload.from_user`；
  成功时把 `result.paper_id` 写 `paper_sessions`（每用户最近一份卷）。
- **确认**：同一用户有 session 时，「入库」「第N题没错」「布丁的/奶茶的」→ `paper.confirm`；
  worker 用 `confirm_paper()` 改 `is_wrong`/归属/原图迁移，`status=ready`。
- **vision**：`CIJIAN_PAPERS_VISION_MODEL=deepseek/deepseek-flash` 实测可读多页试卷
  （correctly 识别姓名/年级/单元/错题）；GLM 周额度打满时 deepseek 不受影响。
- 仍待：出卷第 4 步（参数解析 + A4 模板 + Chrome PDF + 企微文件直发）、paper.query。

## 坑与决策

- `papers.child_id` 必须可空：第 1 步建卷时归属未知（docs/17 已同步，别照抄 v1 的 NOT NULL）。
- sqlite 连接 `check_same_thread=False`：watcher 在主线程构造、后台线程使用。
- 分组关闭按**墙钟 last_seen**，不按图片 mtime——否则老照片（拍摄时间早）会一页一份卷。
- 免费额度坑见 `gotcha-opencode-free-quota`；识别模型走付费档（每卷几分钱）。

## 下一步（docs/17 §11）

2. ingest worker + vision prompt + 归属规则（姓名 → 印刷年级唯一匹配 → 问一句）
3. api：微信图意图分流 + ≤1h 中转 + 企微文件消息直发（发完即删）
4. 出卷：参数解析 + A4 模板 + headless Chrome PDF + 交付
5. paper.query + 微信剧本联调；6. 按 DoD §10 验收
