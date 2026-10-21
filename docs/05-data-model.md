# 05 · 数据模型

> cijian-api 使用 SQLite（WAL 模式）+ 本地磁盘文件。单机单文件，家庭规模足够（ADR-002/007）。

## 存储布局

```
$CIJIAN_DATA_DIR/
├── cijian.db                  # SQLite
└── files/
    └── ab/                    # 按 file_id 前 2 位分桶
        └── f_ab12cd34.pdf     # 随机名存储，原名只入库
```

文件目录在 Web 静态根之外，只能通过签名 URL（04 §签名文件下载）读出。

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
```

## 状态转换规则（api 实现依据）

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

**Sweeper**：api 内置，每 10 分钟一轮：① 过期文件清理（含 expired 标记）② 租约超时重置 ③ 超龄任务清理 ④ 磁盘水位检查——`DATA_DIR` 所在盘使用率 >90% 时拒收新上传（503 unavailable）并记日志，直到回落到 85% 以下。

## 备份

- `cijian.db`：每日 `sqlite3 cijian.db ".backup backup/cijian-$(date +%F).db"`，保留最近 7 份（cron，见 07-deploy-cicd §运维）。
- `files/` 不备份（24h TTL，属中转数据，无备份价值）。
