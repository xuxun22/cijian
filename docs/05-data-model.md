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

## TTL 与保留策略

| 数据 | 保留 | 清理方 |
|---|---|---|
| 上传文件 | 24 小时（`expires_at`） | sweeper 物理删除 |
| print_jobs | 30 天（终态与非终态一并） | sweeper 删除 + 对应 events 级联 |
| job_events | 随任务删除 | 同上 |
| 打卡预览片 `data/media/` | 7 天（`preview_expires_at`） | sweeper 物理删除 + 置 `expired`（v1.4） |
| 待指派媒体 | 14 天未处理 | sweeper 置 `dismissed`（v1.4） |

打卡记录/项目/归档元数据**永久保留**；全质量原件在 Mac mini 归档目录，不经过 api。

**Sweeper**：api 内置，每 10 分钟一轮：① 过期文件清理（含 expired 标记）② 租约超时重置 ③ 超龄任务清理 ④ 磁盘水位检查——`DATA_DIR` 所在盘使用率 >90% 时拒收新上传（503 unavailable）并记日志，直到回落到 85% 以下 ⑤ 预览片到期清理（v1.4）⑥ 待指派超龄 dismissed（v1.4）。

## 备份

- `cijian.db`：每日 `sqlite3 cijian.db ".backup backup/cijian-$(date +%F).db"`，保留最近 7 份（cron，见 07-deploy-cicd §运维）。
- `files/` 不备份（24h TTL，属中转数据，无备份价值）。
- `media/` 预览片不备份（7 天保留、可由 Mac mini 原件重新生成）；`cijian.db` 备份已覆盖打卡记录与归档元数据。
