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

## 已落地（2026-11-21 照片自动分流 + 口算打卡）

- **不再需要「收卷」**：每张图入 `photo_batches`（due_at = 最后一张 +45s）；
  `createPhotoBatchLoop`（index.ts，5s tick）到期 → 下载 `files`（1h TTL）→
  `paper.ingest`（`silent_other: true`）。「收卷」保留为立即处理的后门。
- **vision 一次调用同时分类 + 切题**：`kind = exam | oral | other`。
  - `oral`：口算题卡，**逐题验算孩子写的答案**（不依赖红叉），tags 是错误类型
    （进位/退位/口诀/除法/混合）；合成卷实测：12 题准确找出 3 道错（45÷9=6、
    36+27=62、54÷6=8），归属「奶茶」。
  - `other`：本地删卷删图、服务器中转即删、**不回微信**（安静）。
- **确认词**：「收 / 收吧 / 收了 / 确认 / 入库」→ 入库；「不收 / 不要 / 丢掉 / 算了」
  → `paper.confirm {discard:true}` 删卷删原图并清 session；仍有「第N题没错」「奶茶的」。
- **口算自动打卡**：`paper.confirm` 成功且 `kind=oral` → agent 调
  `POST /api/agents/checkin/manual`（`{project_name:"每日口算", child:"奶茶"}`；
  服务端按名+孩子找 `media_type=none` 项目，`manualCheckin` 当日幂等）→
  回复「… 口算打卡成功（奶茶 · 11-21）」或「今天已经打过口算卡了」；打卡失败不推翻入库，
  回复里给出补救说法。
- 新增 api 表 `photo_batches`；papers 表新增 `kind`（老库 `ALTER` 自动补，默认 exam）。
- 测试：api 152、agent 132 全绿（含批次到期/下载失败释放/口算确认打卡/丢弃删卷）。

## 坑：扫描器认领 vs 微信任务 staging 竞态（2026-11-21 实测）

`paper.ingest` 原来先建 `papers/inbox/<pp_id>/` 再下载照片、最后建卷行；
但 `PapersWatcher._reconcile` 每 30 秒会把「有目录没行」的 `pp_*` 目录当成残留认领，
抢先插入同一 `paper.id`，worker 随后 `create_paper` 撞 `UNIQUE constraint failed: papers.id`。
**修法**：先建卷行、再建目录/下图（扫描器看到 ingesting 行就跳过）；下载失败删行+删目录。
回归测试 `test_paper_row_created_before_download` 固定这个顺序。

## 纠错双向（2026-11-21）

- 「第N题没错」→ `wrong_off`（is_wrong=0）；「第N题错了 / 算错了」→ `wrong_on`（is_wrong=1）；
  两者都会把该题从 `uncertain` 移除，并重算 wrong。
- 实测：84 题口算里第 21 题不确定，确认「收」后其余 8 题如实入库，口算打卡成功。

## 口算误分类导致漏打卡（2026-11-22）

**症状**：11-21 奶茶的「三上口算练习（12）」发图 → 预览说「回『收』入库」→ 回「收」后
只回复「记好了：…全对」，没有「口算打卡成功」；`checkin_records` 里当天只有布丁，没有奶茶。

**根因**：vision 把 75 道纯算式的口算卡判成 `kind=exam`（可能被姓名栏/页眉误导）。
`paper.confirm` 只在 `kind=oral` 时调 `POST /api/agents/checkin/manual`，exam 分支只入库，
所以不报错、也不打卡。

**修复**：
- prompt `paper-ingest.md`：标题含「口算/口算练习/计算练习/速算」→ `oral`，有卷头也算；
  ≥20 题、≥85% 是 `calc` → `oral`。
- `parse_payload()` 兜底：标题含口算/计算练习 → `oral`；标题含单元/期中/期末/测试/试卷
  → `exam`（口算词优先）；无明确标题时 ≥20 题且 ≥85% 是 `calc` → `oral`；
  `answered_count` 仍保留（用于「还没做」判定）。
- API 确认词补 `存 / 存吧 / 存了 / 保存 / 保存吧`（用户口述「存」也能确认）。
- 数据修复：补录 `2026-11-21` 奶茶 `每日口算`（`cr_fcf0f38c411c053c`）；
  本地 `pp_21e5dd5b2a57fd3c` 的 `kind/stats.kind` 从 `exam` 改为 `oral`。

**预防**：口算卡的「标题」比题型更可靠；只靠模型分类会偶发误判，必须有确定性兜底。
排查时先看 `papers.kind` 和 `paper.confirm` result 的 `kind`，没有 `checkin` 字段基本就是走了 exam。

## 口算「还没做」防谎报（2026-11-21）

- vision 对 `kind=oral` 额外输出 `answered_count`（真写了答案的题数，空着/只有印刷体不算）。
- agent 判定：`未作答 ≥ 80%` → 视为整页/大部分没做 → **删临时卷、不建错题、不打卡**，
  回「这张口算还没做…」或「还没做完（84 题里只写了 5 题），做完拍给我…」。
- `answered_count` 缺失/非法 → 不触发（宁可照常判，避免误伤）；试卷不受影响（空白=错）。
- 真实视觉实测：空白 12 题 → 「还没做」；只写 2 题 → 「还没做完（12 题里只写了 2 题）」，
  均未建卷、未生成打卡记录。

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
