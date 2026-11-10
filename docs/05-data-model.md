# 05 · 数据模型

> cijian-api 使用 SQLite（WAL 模式）+ 本地磁盘文件。单机单文件，家庭规模足够（ADR-002/007）。

## 存储布局

```
$CIJIAN_DATA_DIR/
├── cijian.db                  # SQLite
├── files/
│   └── ab/                    # 按 file_id 前 2 位分桶
│       └── f_ab12cd34.pdf     # 随机名存储，原名只入库
└── media/                     # 打卡预览片（v1.4；无 TTL，按保留天数清理）
    └── 2026-11/
        └── cm_ab12cd34.mp4    # 文件名 = media_id，目录按月
└── artifacts/                 # AI 任务产物（v1.5；报告/diff/log，30 天 TTL）
    └── <task_id>/
        └── aa_ab12cd34.json  # 文件名 = artifact_id
```

文件目录在 Web 静态根之外，只能通过签名 URL（04 §签名文件下载 / §媒体播放）读出。

## 表结构

```sql
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

-- 打印机 = 地点 agent 的注册身份（一地一 agent 一 key）
CREATE TABLE printers (
  id            TEXT PRIMARY KEY,             -- p_laowu（创建时定，可读）
  name          TEXT NOT NULL,                -- 老家打印机
  location      TEXT NOT NULL,                -- 外婆家
  key_hash      TEXT NOT NULL,                -- agent key 的 SHA-256（明文只在发放时显示一次）
  handlers      TEXT NOT NULL DEFAULT '["print"]',
  color         INTEGER NOT NULL DEFAULT 1,   -- 能力：彩色
  duplex        INTEGER NOT NULL DEFAULT 0,   -- 能力：双面
  status        TEXT NOT NULL DEFAULT 'offline',
  device_state  TEXT NOT NULL DEFAULT '',     -- agent 心跳上报的打印机硬件状态（ok/unreachable）
  last_seen_at  TEXT,
  created_at    TEXT NOT NULL
);

CREATE TABLE files (
  id            TEXT PRIMARY KEY,             -- f_ab12…
  orig_name     TEXT NOT NULL,
  mime          TEXT NOT NULL,
  size          INTEGER NOT NULL,
  sha256        TEXT NOT NULL,
  path          TEXT NOT NULL,                -- 相对 DATA_DIR
  expires_at    TEXT NOT NULL,                -- 默认 created_at+24h
  created_at    TEXT NOT NULL
);

CREATE TABLE print_jobs (
  id            TEXT PRIMARY KEY,             -- j_9f3…
  file_id       TEXT NOT NULL REFERENCES files(id),
  printer_id    TEXT NOT NULL REFERENCES printers(id),
  user_id       TEXT,                         -- 提交者 users.id（网页口令登录为 'family'，历史任务 NULL）
  handler       TEXT NOT NULL DEFAULT 'print',
  params        TEXT NOT NULL DEFAULT '{}',   -- {copies,color_mode,duplex}
  status        TEXT NOT NULL DEFAULT 'queued',
                -- queued|claimed|printing|done|failed|expired
  attempts      INTEGER NOT NULL DEFAULT 0,   -- 领取即 +1，上限 3
  lease_expires_at TEXT,                      -- 占用/退避共用：未过期不可被领取
  last_message  TEXT,
  created_at    TEXT NOT NULL,
  updated_at    TEXT NOT NULL
);

-- 微信小程序用户（openid 绑定制，见 docs/06 §认证）
CREATE TABLE users (
  id            TEXT PRIMARY KEY,             -- u_ab12…
  openid        TEXT NOT NULL UNIQUE,         -- 微信 openid（仅服务端可见，不下发客户端）
  name          TEXT NOT NULL DEFAULT '',     -- 展示称呼（首次绑定时可选提供，admin 可改）
  status        TEXT NOT NULL DEFAULT 'active', -- active | banned
  created_at    TEXT NOT NULL,
  last_login_at TEXT
);

CREATE TABLE job_events (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id        TEXT NOT NULL REFERENCES print_jobs(id),
  state         TEXT NOT NULL,
  message       TEXT,
  source        TEXT NOT NULL,                -- user | api | agent:<printer_id>
  created_at    TEXT NOT NULL
);

CREATE INDEX idx_jobs_status  ON print_jobs(status, created_at);
CREATE INDEX idx_jobs_list    ON print_jobs(created_at DESC);
CREATE INDEX idx_files_expiry ON files(expires_at);
CREATE INDEX idx_events_job   ON job_events(job_id, created_at);
CREATE INDEX idx_users_openid ON users(openid);

-- ── 每日打卡（v1.4，见 docs/10-checkin-plan.md）─────────────────────────────
-- 项目 = 配置不是代码；记录由媒体管线自动生成（投递即打卡）
CREATE TABLE checkin_projects (
  id               TEXT PRIMARY KEY,            -- cp_ab12…
  name             TEXT NOT NULL,               -- 每日阅读 / 二胡练习
  media_type       TEXT NOT NULL DEFAULT 'any', -- video|audio|any（偏好，指派兜底规则用）
  days_of_week     TEXT NOT NULL DEFAULT '[1,2,3,4,5,6,7]',  -- 应打日（统计分母/高亮）
  fields_schema    TEXT NOT NULL DEFAULT '[]',  -- [{key,label,type,required}] 补字段表单动态渲染
  archive_template TEXT NOT NULL DEFAULT '{date}_{project}_{orig}',
  classifier_hint  TEXT NOT NULL DEFAULT '',    -- AI 分类提示语（"朗读中文故事，人声"）
  min_duration     INTEGER NOT NULL DEFAULT 0,  -- 保留不启用（2026-11-05 决策：不参与判定）
  dingtalk_rules   TEXT,                        -- 休眠字段（钉钉通道 A，将来加配置即接入）
  active           INTEGER NOT NULL DEFAULT 1,
  sort             INTEGER NOT NULL DEFAULT 0,
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL
);

CREATE TABLE checkin_records (
  id          TEXT PRIMARY KEY,                 -- cr_ab12…
  project_id  TEXT NOT NULL REFERENCES checkin_projects(id),
  date        TEXT NOT NULL,                    -- 当地日 YYYY-MM-DD（agent 上报）
  user_id     TEXT,                             -- 补字段/指派操作者（users.id 或 'family'）
  fields      TEXT NOT NULL DEFAULT '{}',       -- {"book":"夏洛的网","pages":"P32-45"}
  created_at  TEXT NOT NULL,                    -- 由媒体管线创建
  updated_at  TEXT NOT NULL,
  UNIQUE(project_id, date)
);

CREATE TABLE checkin_media (
  id                 TEXT PRIMARY KEY,          -- cm_ab12…
  record_id          TEXT REFERENCES checkin_records(id),  -- 空 = 待指派
  type               TEXT NOT NULL,             -- video | audio
  orig_name          TEXT NOT NULL,             -- IMG_1240.MOV
  duration_seconds   REAL NOT NULL,
  size               INTEGER NOT NULL,
  sha256             TEXT,                      -- 去重（近 7 天窗口）
  date               TEXT NOT NULL,             -- 上报的当地日（待指派后 assign 用）
  agent_id           TEXT NOT NULL,             -- printers.id（上报的 agent）
  classifier         TEXT,                      -- JSON {method,project_hint,confidence,evidence}
  status             TEXT NOT NULL DEFAULT 'pending_assign',  -- pending_assign|matched|dismissed
  archive_name       TEXT,                      -- agent 确认过的归档文件名
  archive_path       TEXT,                      -- agent 上报的完整路径（展示用）
  preview_path       TEXT,                      -- data/media/2026-11/cm_….mp4（相对 DATA_DIR）
  preview_size       INTEGER,
  preview_status     TEXT NOT NULL DEFAULT 'none',  -- none|pending|ready|failed|expired
  preview_expires_at TEXT,                      -- ready 时 = now + 7 天
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL
);

CREATE INDEX idx_checkin_records_range ON checkin_records(project_id, date);
CREATE INDEX idx_checkin_media_record  ON checkin_media(record_id);
CREATE INDEX idx_checkin_media_status  ON checkin_media(status, created_at);
CREATE INDEX idx_checkin_media_sha     ON checkin_media(sha256);
CREATE INDEX idx_checkin_media_preview ON checkin_media(preview_expires_at);
```

### 看见闪光 + AI 任务平面（v1.5）

> 设计见 docs/12-shine-plan.md 与 docs/13-ai-agent-plan.md；**API 零 wiki 原文**（ADR-009）——
> 家庭记忆只在私有 GitHub 仓 + agent 本地，API 只存条目、任务、审计、产物和 agent 编译后的视图。

```sql
-- 孩子（默认一个「孩子」；多孩子时 UI 才出现切换）
CREATE TABLE IF NOT EXISTS shine_children (
  id          TEXT PRIMARY KEY,              -- sc_…
  name        TEXT NOT NULL,                 -- 称呼，≤20
  birth_year  INTEGER,                       -- 可选，年龄段校准
  sort        INTEGER NOT NULL DEFAULT 0,
  active      INTEGER NOT NULL DEFAULT 1,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);

-- 一条闪光观察（原文 = 家长输入，存 API；AI 结果由 agent 任务写回）
CREATE TABLE IF NOT EXISTS shine_entries (
  id                TEXT PRIMARY KEY,        -- sh_…
  child_id          TEXT NOT NULL REFERENCES shine_children(id),
  user_id           TEXT,                    -- JWT sub（网页口令 = 'family'）
  author_name       TEXT NOT NULL DEFAULT '',
  client_id         TEXT,                    -- 幂等（UNIQUE(user_id, client_id)）
  source            TEXT NOT NULL DEFAULT 'web',  -- web|mp
  date              TEXT NOT NULL,           -- YYYY-MM-DD（Asia/Shanghai）
  input_type        TEXT NOT NULL DEFAULT 'text', -- text|image
  raw_text          TEXT NOT NULL DEFAULT '', -- ≤500；纯图片可为空
  image_file_id     TEXT,                    -- 指向 files（24h TTL），不长期保存
  kind              TEXT NOT NULL DEFAULT 'notice', -- praise|notice|listen
  highlight         TEXT NOT NULL DEFAULT '',
  strength          TEXT NOT NULL DEFAULT '',
  growth_note       TEXT NOT NULL DEFAULT '',
  say_this          TEXT NOT NULL DEFAULT '',
  lighter           TEXT NOT NULL DEFAULT '',
  avoid             TEXT NOT NULL DEFAULT '',
  tags              TEXT NOT NULL DEFAULT '[]',
  need_more         TEXT NOT NULL DEFAULT '',
  said_at           TEXT,
  feedback          TEXT NOT NULL DEFAULT '', -- ''|too_much|not_like|good
  ai_task_id        TEXT,
  ai_status         TEXT NOT NULL DEFAULT 'pending', -- pending|ok|degraded|failed
  wiki_task_id      TEXT,
  wiki_status       TEXT NOT NULL DEFAULT 'pending', -- pending|ok|failed|skipped
  ai_model          TEXT,
  ai_prompt_version TEXT,
  created_at        TEXT NOT NULL,
  updated_at        TEXT NOT NULL,
  deleted_at        TEXT                     -- 软删；sweeper 30 天后硬删
);
CREATE INDEX idx_shine_entries_child_date ON shine_entries(child_id, date DESC);
CREATE INDEX idx_shine_entries_deleted   ON shine_entries(deleted_at);
CREATE UNIQUE INDEX idx_shine_entries_client ON shine_entries(user_id, client_id) WHERE client_id IS NOT NULL;

-- AI 任务队列（与 print_jobs 不同队列：长轮询领取、心跳续租、报果）
CREATE TABLE IF NOT EXISTS ai_tasks (
  id               TEXT PRIMARY KEY,          -- at_…
  type             TEXT NOT NULL,             -- shine.analyze|shine.wiki.ingest|shine.review.monthly|shine.wiki.lint|shine.wiki.redact
  status           TEXT NOT NULL DEFAULT 'queued', -- queued|claimed|running|succeeded|failed|cancelled|expired
  priority         INTEGER NOT NULL DEFAULT 100,
  payload          TEXT NOT NULL DEFAULT '{}', -- {entry_id, child_id, prompt_version, …}（无家庭内容正文）
  result           TEXT,                      -- 小的结构化结果
  runner           TEXT NOT NULL DEFAULT 'opencode',
  model            TEXT,
  prompt_version   TEXT,
  dedupe_key       TEXT,                      -- 如 shine.analyze:sh_…（UNIQUE，重放返回已有）
  parent_task_id   TEXT,
  agent_id         TEXT,                      -- printers.id（执行者）
  attempts         INTEGER NOT NULL DEFAULT 0,
  max_attempts     INTEGER NOT NULL DEFAULT 2,
  lease_expires_at TEXT,
  heartbeat_at     TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0,
  tokens_in        INTEGER, tokens_out INTEGER,
  duration_ms      INTEGER,
  last_error       TEXT,
  created_at       TEXT NOT NULL, started_at TEXT, finished_at TEXT
);
CREATE UNIQUE INDEX idx_ai_tasks_dedupe ON ai_tasks(dedupe_key) WHERE dedupe_key IS NOT NULL;
CREATE INDEX idx_ai_tasks_queue ON ai_tasks(status, priority, created_at);
CREATE INDEX idx_ai_tasks_lease ON ai_tasks(lease_expires_at);

CREATE TABLE IF NOT EXISTS ai_task_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  task_id TEXT NOT NULL REFERENCES ai_tasks(id),
  state TEXT NOT NULL, message TEXT, source TEXT NOT NULL, created_at TEXT NOT NULL
);

-- 产物（报告/diff/log；wiki 全文不进这里），data/artifacts/<task_id>/，30 天 TTL
CREATE TABLE IF NOT EXISTS ai_artifacts (
  id TEXT PRIMARY KEY, task_id TEXT NOT NULL REFERENCES ai_tasks(id),
  kind TEXT NOT NULL, path TEXT NOT NULL, mime TEXT NOT NULL,
  size INTEGER NOT NULL, sha256 TEXT NOT NULL, expires_at TEXT, created_at TEXT NOT NULL
);

-- agent 编译后发布的 UI 视图（wiki 原文永不来 API；每孩子每类一条）
CREATE TABLE IF NOT EXISTS shine_views (
  id               TEXT PRIMARY KEY,
  child_id         TEXT NOT NULL REFERENCES shine_children(id),
  kind             TEXT NOT NULL,             -- growth | analyze_context
  content          TEXT NOT NULL,             -- 渲染契约 JSON（04 §看见闪光 growth）
  commit_count     INTEGER NOT NULL DEFAULT 0, -- git rev-list --count HEAD，单调防回退
  produced_by_task TEXT,
  updated_at       TEXT NOT NULL,
  UNIQUE(child_id, kind)
);
```

`printers` 增列：`ai_capabilities TEXT NOT NULL DEFAULT '[]'`（能力路由：无 wiki deploy key 的机器只报 analyze）。

## 状态转换规则（api 实现依据）

打卡媒体（v1.4）：

| 动作 | 变更 |
|---|---|
| agent 上报且指派成功 | 建/复用 `checkin_records(project_id,date)`，media → `matched`，响应归档名 |
| agent 上报未指派 | media → `pending_assign`（agent 移入 holding） |
| 用户 `assign` | 建/复用目标记录，media → `matched`（改派 = 换 record 归属，日期沿用原记录） |
| 用户 `dismiss` / sweeper：pending 超 14 天 | → `dismissed`（终态） |
| 预览片上传完成 | `preview_status` → `ready`，`preview_expires_at = now+7d` |
| sweeper：预览到期 | 删 `data/media/` 文件，`preview_status → expired`（记录与归档名保留） |

（print_jobs 部分不变，略——见下方原表。）

| 动作 | 变更 |
|---|---|
| `claims` 领取 | `queued→claimed`，`attempts+=1`，`lease=now+120s`；`attempts≥3` 的 queued 不再派发，sweeper 将其置 `failed` |
| `report printing` | `printing`，`lease=now+600s` |
| `report done` | `done`，`lease=NULL` |
| `report failed` | `attempts<3`：`queued` + `lease=now+30s`（退避）；否则 `failed`，`lease=NULL` |
| sweeper：租约超时 | `claimed/printing` 且 `lease<now` → `queued`（等下次领取），`last_message='租约超时，等待重派'` |
| sweeper：文件过期 | 先把该文件名下 `queued` 的任务置 `expired`，再删文件记录与磁盘文件 |

AI 任务（v1.5）：

| 动作 | 变更 |
|---|---|
| `POST /entries` | 建 `shine_entries(ai_status=pending)` + 入队 `shine.analyze`（dedupe=`shine.analyze:<id>`） |
| claim（长轮询 ≤25s） | `queued→claimed`，`attempts+=1`，`lease=now+120s`；**serialized 类型（wiki.*/review.*）同类型已有 claimed/running 时不再派发** |
| agent heartbeat（20s） | `lease=now+60s`；`cancel_requested=true` 时响应 cancel |
| report result（analyze） | 条目写回 AI 字段 `ai_status=ok`；**同一事务**入队 `shine.wiki.ingest`（dedupe=`shine.wiki.ingest:<id>:<n>`） |
| report fail | `attempts<max` → `queued`（lease=now+30s 退避）；否则 `failed`；analyze 失败同步置条目 `ai_status=failed` |
| DELETE entry（软删） | 入队 `shine.wiki.redact`（agent 清 wiki 引用并重发视图） |
| sweeper：租约超时 | `claimed/running` 且 `lease<now` → 按 attempts 规则重派或 `expired` |
| agent 上报视图 | `shine_views` upsert；`commit_count ≤ 已存值` → 409 拒绝（防回退） |
| retry（用户） | 新 dedupe 序号入队 `shine.analyze:<id>:<n>` |

## TTL 与保留策略

| 数据 | 保留 | 清理方 |
|---|---|---|
| 上传文件 | 24 小时（`expires_at`） | sweeper 物理删除 |
| print_jobs | 30 天（终态与非终态一并） | sweeper 删除 + 对应 events 级联 |
| job_events | 随任务删除 | 同上 |
| 打卡预览片 `data/media/` | 7 天（`preview_expires_at`） | sweeper 物理删除 + 置 `expired`（v1.4） |
| 待指派媒体 | 14 天未处理 | sweeper 置 `dismissed`（v1.4） |
| shine 软删条目 | 30 天 | sweeper 硬删（v1.5） |
| ai_artifacts `data/artifacts/` | 30 天（`expires_at`） | sweeper 物理删除 + 删行（v1.5） |
| ai_tasks（终态） | 90 天 | sweeper 删除 + events 级联（v1.5） |

打卡记录/项目/归档元数据、shine 条目/视图**永久保留**；全质量原件在 Mac mini 归档目录，不经过 api。
**家庭 Wiki 不在 api**（私有 GitHub 仓 + agent 本地克隆，ADR-009）。

**Sweeper**：api 内置，每 10 分钟一轮：① 过期文件清理（含 expired 标记）② 租约超时重置 ③ 超龄任务清理 ④ 磁盘水位检查——`DATA_DIR` 所在盘使用率 >90% 时拒收新上传（503 unavailable）并记日志，直到回落到 85% 以下 ⑤ 预览片到期清理（v1.4）⑥ 待指派超龄 dismissed（v1.4）⑦ AI 任务租约超时重派（v1.5）⑧ shine 软删/ai_artifacts/终态 ai_tasks 清理（v1.5）。

## 备份

- `cijian.db`：每日 `sqlite3 cijian.db ".backup backup/cijian-$(date +%F).db"`，保留最近 7 份（cron，见 07-deploy-cicd §运维）。
- `files/` 不备份（24h TTL，属中转数据，无备份价值）。
- `media/` 预览片不备份（7 天保留、可由 Mac mini 原件重新生成）；`cijian.db` 备份已覆盖打卡记录与归档元数据。
