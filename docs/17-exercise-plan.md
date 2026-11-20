# 17 · 错题本（习题整理）设计

> 状态：设计定稿（2026-11-20，三个关键决策已由爸爸确认） · 依赖：docs/13/14 任务平面、docs/10 checkin 扫描模式、docs/08? 打印不涉及
> 铁律约束见 llmwiki `pages/privacy-iron-law.md`。

## 1. 目标与约束

把小朋友的试卷（特别是错题）收集、识别、整理，按需生成复习卷（原题重组 / AI 变式），
全程微信交互。

**第一约束（隐私铁律，已细化）**：服务器只是缓存/通道——短期（≤7 天）存在可以，
判据是「**随时删除腾讯云主机，数据不丢失**」。真相源 = Mac mini。

已确认的三个决策：
1. 微信直接发图可用（图片字节短途过服务器，转发后即删，兜底 sweeper ≤1h）；
2. 复习卷 PDF 经**企微文件消息**直发（服务器作为发送通道，**即发即删**）；
3. 识别/变式调用外部大模型 API（图片发给模型服务商处理）。

## 2. 总体架构

```
投卷（三入口）
  a. 微信发图 ──► 企微回调(服务器) ──内存/≤1h TTL──► 任务 payload 带签名 URL
  b. AirDrop → Mac mini papers-inbox（checkin 扫描模式，零上云）
  c. 二期：本地 Web 上传（零上云）
                    │
                    ▼
        ai_task: paper.ingest（Mac mini worker）
        vision 读卷头 → 自动归属 → 切题判错 → 微信预览 → 确认
                    │
                    ▼
        Mac mini 本地 SQLite（错题库，唯一真相源）
        原卷图：<state>/papers/<child>/<yyyy-mm>/<paper_id>/*.jpg（永久）
                    │
     ┌──────────────┴──────────────┐
     ▼                             ▼
ai_task: paper.query        ai_task: paper.sheet（出卷）
（微信问：多少错题…）        参数解析 → 选题（原题/变式）→ HTML 模板
                             → chrome --headless --print-to-pdf
                             → PDF 存 Mac mini + 上传服务器(即发即删)
                             → 企微文件消息直发 → 微信收到 PDF
```

## 3. 儿童建模（年级自动成长）

表 `children`（agent 本地）：

```sql
CREATE TABLE children (
  id         TEXT PRIMARY KEY,            -- ch_…
  name       TEXT NOT NULL,               -- 卷面手写姓名的匹配目标（可多个，逗号分隔）
  nicknames  TEXT NOT NULL DEFAULT '',    -- 布丁/奶茶/英文名等口语称呼
  entry_year INTEGER NOT NULL             -- 入学年份（一年级那年的 9 月所在公历年）
);
-- 种子：布丁 entry_year=2022（本学年 5 年级）；奶茶 entry_year=2024（3 年级）
```

年级 = `school_year(today) - entry_year + 1`；`school_year`：9 月 1 日前算上一学年
（2026-11 → 2026 学年 → 布丁 5、奶茶 3；2027-09-01 起自动 6、4）。**永不手工改。**

**自动归属（能不问就不问）**：
1. 卷头手写姓名 → 精确/模糊匹配 name/nicknames → 直接归属；
2. 卷面印刷年级+科目 → 对当前学年各孩子年级做唯一匹配 → 直接归属；
3. 都失败 → 微信问（附识别出的卷头文字），回「布丁的」即入。

## 4. 数据模型（Mac mini 本地 SQLite，`<state>/papers/papers.db`）

```sql
CREATE TABLE papers (
  id         TEXT PRIMARY KEY,           -- pp_…
  child_id   TEXT REFERENCES children(id), -- 识别/归属前为 NULL（第 1 步只建卷）
  subject    TEXT NOT NULL,              -- math | chinese | english
  source     TEXT,                       -- 卷头识别的卷名原文
  unit_no    INTEGER,                    -- 归一单元号（第4单元→4；期中/期末/专项→NULL）
  grade_hint INTEGER,                    -- 卷面印刷年级（归属用，非真相）
  shot_at    TEXT,                       -- 拍摄/投递时间
  status     TEXT NOT NULL DEFAULT 'ingesting',  -- ingesting|preview|ready|failed|discarded
  stats      TEXT,                       -- JSON：{total, wrong}
  files_dir  TEXT NOT NULL DEFAULT '',   -- 原图目录（inbox 分组 → 归属后迁 originals）
  created_at TEXT NOT NULL
);

CREATE TABLE questions (
  id          TEXT PRIMARY KEY,          -- q_…
  paper_id    TEXT NOT NULL REFERENCES papers(id),
  child_id    TEXT NOT NULL,
  subject     TEXT NOT NULL,
  q_no        INTEGER NOT NULL,
  stem        TEXT NOT NULL,             -- 题干（识别文本）
  q_type      TEXT,                      -- choice|fill|calc|word|geometry|reading|…
  tags        TEXT,                      -- JSON：知识点粗标 ["分数加减","约分"]
  is_wrong    INTEGER NOT NULL DEFAULT 0,
  wrong_count INTEGER NOT NULL DEFAULT 1, -- 同题去重后累计（二期）
  mastery     INTEGER NOT NULL DEFAULT 0, -- 0 未掌握 | 1 复习过 | 2 已毕业（二期）
  page_no     INTEGER, page_ref TEXT,    -- 原卷图定位（一期整页缩略卡用）
  created_at  TEXT NOT NULL,
  UNIQUE(paper_id, q_no)                 -- 幂等：重识别不重入库
);

CREATE TABLE sheets (
  id          TEXT PRIMARY KEY,          -- sh_…
  child_id    TEXT NOT NULL,
  subject     TEXT NOT NULL,
  spec        TEXT NOT NULL,             -- JSON：出卷指令原文+解析后参数
  question_ids TEXT NOT NULL,            -- JSON：选题 id + 每题 origin(原题)|variant
  pdf_path    TEXT NOT NULL,             -- Mac mini 本地路径
  sent_at     TEXT,                      -- 企微文件消息发送时间
  created_at  TEXT NOT NULL
);
```

## 5. 任务契约（走现有 ai_tasks 平面，worker 新增三类）

### 入口（已实现，2026-11-20 第 3 步；2026-11-21 自动分流）

**自动分流（默认）**：微信发照片后不再需要「收卷」——服务器把照片挂进 `photo_batches`，
最后一张后**静默 45 秒**，把这一批下载成一份材料（`files` 中转，TTL 1h），入队 `paper.ingest`。
vision 先分类 `kind = exam | oral | other`：

- `oral`（口算题卡，逐题验算答案）→ 回预览「这是奶茶的口算：12 题错 3——…」；
- `exam`（有卷头/题号/题型混合）→ 回现有试卷预览；
- `other` → **安静不处理**（本地/服务器临时副本都清掉）。

**确认**：回「收」→ 入库；回「不收」→ 删除；「第2题没错」→ 纠错；「奶茶的」→ 补归属。
**口算确认后自动打当天「每日口算」卡**（项目 `cp_math` 布丁 / `cp_math_nc` 奶茶，
`media_type=none`），并回复「口算打卡成功（奶茶 · 11-21）」或「今天已经打过口算卡了」。

手动路径仍保留：回「收卷」可立即处理最近 15 分钟照片（跳过 45 秒等待）。

### paper.ingest
```
payload: { source: "wecom"|"wecom-auto", from_user, requester,
           silent_other: true,              # 自动分流时 other 不回消息
           media: [{file_id}…] }            # file_id = api files 表（1h 中转）
worker:  下载图 → 本地 inbox 分组 → vision（deepseek/deepseek-flash）
         → kind 分类 → 归属/切题判错 → 写 papers(kind, status=preview)
result:  { ok, kind, paper_id, child_id, subject, unit, total, wrong,
           attribution: "name|grade|asked", text: 微信预览文案 }
```
- 预览文案格式（微信）：试卷 `奶茶 · 3年级数学 · 第4单元：6 题错 2——…回「收」入库；回「不收」丢掉。`
  口算 `这是奶茶的口算：12 题错 3——口诀×2、除法×2…回「收」= 记错题 + 今天口算打卡；回「不收」= 丢掉。`

### paper.confirm
```
payload: { from_user, paper_id, discard?: true, wrong_off: [2], child_name: "奶茶" }
worker:  discard → 删本地卷与原图；wrong_off → 对应题 is_wrong=0；child_name → 归属并迁移原图；
         归属仍未知 → 回一句追问（不落 ready）；否则 status=ready。
         kind=oral 且确认成功 → 调 api 手动打卡「每日口算」（当日幂等），回复打卡结果。
result:  { ok, paper_id, kind, child_name, total, wrong, checkin?, text: 「记好了… 口算打卡成功」 }
```

### paper.sheet（出卷）
```
payload: { requester, text: 指令原文 }   # 「出3年级第4单元到第6单元的数学复习卷」
worker:  参数解析（LLM，输出 JSON：child|grade / subject / unit_from / unit_to /
         date_from / count / mode: original|variant|mixed）
         → 唯一匹配孩子则静默；歧义则 result.text 问一句
         → 选题 → 排版 → chrome headless PDF → 上传服务器(临时) → 触发企微文件消息 → 删
result:  { ok, sheet_id, picked: n, mode, text: 「卷好了，已发文件。18 题（原 15 + 变式 3）」 }
```

### paper.query
```
payload: { requester, text }   # 「布丁现在有多少数学错题」「奶茶这周错了什么」
result:  { ok, text }          # 本地查库，模板化回答
```

## 6. 识别设计（vision prompt 要点）

- 输入：一卷全部页图（`--file` 逐页）；输出**严格 JSON**（禁 markdown 围栏）：
  ```json
  { "header": {"name":"奶茶","printed_grade":3,"subject":"数学","title":"第四单元测试","unit":4},
    "questions": [{"no":1,"stem":"…","type":"fill","tags":["时间单位"],"wrong":true,"page":1}] }
  ```
- 判错依据：红叉/红圈/扣分痕迹/订正痕迹；不确定 → `wrong:null` → 预览里列出让家长定。
- 单元归一：`第X单元|Unit X` → X；期中/期末/专项/模拟 → null（靠题目标签）。
- 解析失败/字段非法 → 整卷 failed + 微信说明，不静默丢。
- 幂等：`UNIQUE(paper_id, q_no)`；重识别 = 覆盖式更新。

## 7. 出卷与排版

- 参数记忆：出卷偏好（默认 mode、默认题量）写 preferences（家庭 wiki 记忆层）。
- **变式题**：prompt 给原题（题干+标签+答案若有）→ 同知识点同结构新题；卷面标注
  「本题 AI 生成，请家长过目」；页脚列变式题的原题来源。
- 排版模板（HTML → A4 print CSS）：卷头（`{child}{subject}复习卷 · {范围} · 日期` +
  姓名栏 `____`），题目流式，按题型留作答区（选择 1 行/计算 3 行/应用 6 行/画图留白框），
  页脚页码 + 来源标注。**图题一期 = 题干文本 + 所在原页缩略图卡**（保真不重排）；
  三期 bbox 精裁。
- PDF：`chrome --headless --print-to-pdf`（Mac mini 本地，零外部依赖）。

## 8. 交付（企微文件消息，即发即删）

1. worker 把 PDF `POST /api/agents/papers/delivery`（X-Agent-Key，服务器临时文件，
   不进公开存储目录）；
2. 服务器调企微素材上传接口得 `media_id` → 发送**文件类型应用消息**给 requester；
3. 发送成功/失败都**立即删除**该临时文件；sweeper 兜底（≤1h）；
4. worker 记 `sheets.sent_at`。发送失败 → 微信文本兜底：「卷好了但在发送上失败了，
   已存 Mac mini `<path>`」。

删服务器不丢数据的验证：PDF 本体 + sheets 记录都在 Mac mini，随时可重发。

## 9. 分期

- **一期 MVP（约 4~5 天）**：微信发图入口 + AirDrop inbox、ingest/归属/预览/纠错、
  本地库、出卷（原题+变式）、chrome PDF、企微文件直发、paper.query。
- **二期（3~4 天）**：本地错题本 Web UI（家庭 Wi-Fi/Tailscale：浏览/修题/可视化出卷）、
  重做判定闭环（mastery 流转）、复习提醒（reminders + 艾宾浩斯）、同题去重（wrong_count）。
- **三期**：图题 bbox 精裁、答案页、语音速记、变式题库沉淀。

## 10. 一期验收（DoD）

- [ ] 微信连发 5 张卷图 → 预览文案正确（含自动归属姓名）→ 回「入库」→ Mac mini
      `papers/` 出现原图 + 本地库可查
- [ ] 微信发一张口算照片 → 45 秒内回「这是奶茶的口算：N 题错 M」→ 回「收」→
      错题入库 + 「口算打卡成功」；再发一张非试卷照片 → 安静不打扰
- [ ] 一份无姓名、印着「五年级数学」的卷 → 自动归属布丁，不问
- [ ] 一份匹配不上的卷 → 微信问，回「奶茶的」→ 入库
- [ ] 「出3年级第4单元到第6单元的数学复习卷」→ 微信收到 PDF 文件消息；服务器上
      该临时文件已删（`ls` 验证）；Mac mini 留有本体
- [ ] 「给布丁出 5 道分数错题，出类似的题」→ 变式卷，卷面有 AI 标注
- [ ] 「布丁现在有多少数学错题」→ 正确数字
- [ ] 删除服务器模拟：停 api 容器 → Mac mini 数据完好，恢复后 query/sheet 正常
- [ ] 纠错回路：「第②题没错」→ 该题 is_wrong=0

## 11. 实施顺序（走 dev 通道）

1. agent：children 种子 + papers.db 迁移 + inbox 扫描（借 checkin 稳定判定模式）
   - **2026-11-20 已落地**：`cijian_agent/papers/{store.py,watch.py}`，背景能力名 `papers`；
     库 `<state>/papers/papers.db`，扫描 `~/Downloads` 图片（HEIC/JPG/PNG/WEBP），
     mtime 间隔 ≤180s 聚成一份卷，页名 `p01__原名`，行 `status=ingesting` 等识别；
     单测 13 项（分组/稳定/水位线/重启认领/年级成长）。
2. agent：ingest worker + vision prompt + 归属规则（单测：归属/解析/幂等）
   - **2026-11-20 已落地本地引擎**：`cijian_agent/papers/ingest.py` + prompt
     `ai/prompts/paper-ingest.md`；多页多图 vision → 严格 JSON 校验 → 归属三级
     （姓名/昵称 → 印刷年级唯一匹配 → asked）→ `status=preview` + 覆盖式写题
     → 微信预览文案。归属确定后原图迁 `originals/<child>/<yyyy-mm>/<pp_id>/`。
     本地联调：`python3 -m cijian_agent.papers.ingest <pp_id>`；14 项单测。
     **待第 3 步**：微信发图入口、预览下发与「入库/改错」确认回路。
3. api：wecom 图意图分流 + 临时媒体转发（≤1h sweeper）+ 企微文件消息发送
   - **2026-11-20 已落地收集/确认通道**：微信「收卷」触发（15 分钟照片窗口、
     `paper_intake` 幂等、`files` 1h TTL）→ `paper.ingest`；预览/确认走任务结果直发，
     `paper_sessions` 记住最近一份卷；「入库/第N题没错/奶茶的」→ `paper.confirm`；
     识别成功即删服务器中转文件。vision 固定 `deepseek/deepseek-flash`（多模态，实测可用）。
   - **2026-11-21 自动分流**：照片最后一张后静默 45 秒 → `photo_batches` 到期 → 自动
     `paper.ingest`（`silent_other`）；vision 分 `exam|oral|other`，其他类不打扰；
     口算确认后 agent 调 `POST /api/agents/checkin/manual` 自动打当天「每日口算」卡
     （项目名+孩子，幂等），回复「口算打卡成功」。「收/不收」= 确认/丢弃。
     企微文件消息直发（出卷 PDF）仍属第 4 步。
4. agent：sheet 参数解析 + 排版模板 + chrome PDF + 交付
5. agent：paper.query + 微信剧本联调
6. E2E：按 §10 DoD 逐条过
