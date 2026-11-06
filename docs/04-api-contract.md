# 04 · API 契约 v1

> 三个代码仓共同遵守的接口契约。改接口先改本文档，再改代码。
> Base URL：`https://api.whereami.cn`（过渡期方案见 06-security §传输）

## 通用约定

- 内容类型 `application/json`（文件上传除外）
- 认证方式：
  - 站点用户：`Authorization: Bearer <jwt>`
  - 地点 agent：`X-Agent-Key: <agent_key>`
- 时间一律 ISO 8601 UTC 字符串
- 错误响应统一：`{ "error": { "code": "<machine_code>", "message": "<人可读>" } }`

| HTTP | code | 场景 |
|---|---|---|
| 400 | `bad_request` | 参数缺失/格式错误 |
| 401 | `unauthorized` | 未登录 / token 过期 / agent key 无效 |
| 403 | `forbidden` | 签名文件 URL 无效或不属于本 agent |
| 404 | `not_found` | 资源不存在 |
| 409 | `conflict` | 文件已过期等状态冲突 |
| 413 | `too_large` | 文件超 20MB |
| 415 | `unsupported_media_type` | 非白名单类型 |
| 429 | `rate_limited` | 触发限速 |
| 503 | `unavailable` | 磁盘水位保护中 |

## 健康检查

```
GET /api/health                          （无认证）
→ 200 { "ok": true }
```

## 站点侧接口（JWT）

### 登录

```
POST /api/auth/login
{ "passphrase": "..." }
→ 200 { "token": "<jwt>", "expires_at": "2026-10-28T08:00:00Z" }
→ 401 unauthorized   ← 口令错误
→ 429 rate_limited   ← 同 IP 每分钟 >5 次
```

JWT：HS256，有效期 7 天，payload `{ "sub": "family", "iat": …, "exp": … }`。无刷新令牌，过期重输口令。

### 微信小程序登录（v1.3）

```
POST /api/auth/wx-login
{ "code": "<wx.login 的 code>", "invite": "邀请码（首次绑定必填）", "name": "称呼（首次可选，≤20 字）" }
→ 200 { "token": "<jwt>", "expires_at": "…", "user": { "id": "u_…", "name": "…", "is_new": true } }
→ 401 wx_invite_required   ← openid 未绑定且未带/错邀请码
→ 401 wx_code_invalid      ← code 无效或已被使用（客户端重新 wx.login 后重试）
→ 403 banned               ← 该微信已被禁用
→ 429 rate_limited         ← 同 IP 每分钟 >10 次
→ 503 unavailable          ← 服务端未配置 WX 或微信接口不可用
```

- 服务端以 code 调微信 `jscode2session` 换 **openid**，与 `users` 表一一对应
- **邀请码复用站点口令**（`CIJIAN_PASSPHRASE_HASH`），仅首次绑定时校验一次，之后静默登录
- JWT 与口令登录同构（`sub` 为 `u_…` 用户 id）；轮换口令不影响已绑定用户

### 上传文件

```
POST /api/files                         （multipart/form-data，字段名 file；可选字段 name=展示用原始文件名）
→ 201 { "file_id": "f_ab12…", "orig_name": "合影.jpg", "mime": "image/jpeg",
       "size": 18321, "expires_at": "2026-10-22T09:00:00Z" }
→ 415 / 413 / 429（登录用户每分钟 ≤10 次）
```

服务端校验 magic bytes，不信任扩展名；文件名随机化存储，原名仅入库。
可选 `name` 字段用于 `wx.uploadFile` 场景（它无法自定义 multipart 文件名，临时路径
只能是 tmp_xxx）：服务端清洗（路径分隔符换 `_`、去控制字符、限长 120）后优先作为
`orig_name`；未传则回退 multipart 文件名。存储扩展名始终由 mime 决定，与 name 无关。

### 打印机列表

```
GET /api/printers
→ 200 { "printers": [
  { "id": "p_laowu", "name": "老家打印机", "location": "外婆家",
    "online": true, "handlers": ["print"],
    "color": true, "duplex": false,
    "deviceState": "unreachable",
    "last_seen_at": "2026-10-21T07:59:40Z" } ] }
```

`online` = `last_seen_at` 距今 ≤60 秒；`deviceState` 是 agent 心跳上报的**打印机硬件状态**
（`ok` 在线正常 / `unreachable` 打印机不可达 / 空=未知）。三态展示：
**在线**（online+ok）、**打印机未响应**（online+unreachable，可排队但提示）、**离线**（!online）。

`online` = `last_seen_at` 距今 ≤60 秒。

### 创建打印任务

```
POST /api/print-jobs
{ "file_id": "f_ab12…", "printer_id": "p_laowu",
  "copies": 1, "color_mode": "auto", "duplex": "auto" }
→ 201 { "job_id": "j_9f3…", "status": "queued", "created_at": "…" }
→ 404 not_found（file 或 printer 不存在）
→ 409 conflict（file 已过期）
```

`copies` ∈ 1–20；`color_mode` ∈ auto|color|mono；`duplex` ∈ auto|on|off。
允许向离线打印机提交（前端负责提示，后端不拦）。

### 任务列表 / 详情

```
GET /api/print-jobs?limit=50&status=queued
→ 200 { "jobs": [ { "id": "j_9f3…", "status": "printing",
      "file": { "orig_name": "合影.jpg" },
      "printer": { "id": "p_laowu", "name": "老家打印机", "location": "外婆家" },
      "user_name": "外婆",                    ← 提交者称呼（v1.3；网页口令登录/历史任务为 ""）
      "copies": 2, "attempts": 1, "last_message": null,
      "created_at": "…", "updated_at": "…" } ] }

GET /api/print-jobs/:id
→ 200 { …同上单条…, "events": [
      { "state": "queued",  "message": null,              "source": "user",        "created_at": "…" },
      { "state": "claimed", "message": null,              "source": "agent:p_laowu","created_at": "…" },
      { "state": "printing","message": null,              "source": "agent:p_laowu","created_at": "…" } ] }
```

### 打卡（每日练习，v1.4）

> 设计背景见 docs/10-checkin-plan.md。所有「当日」按 Asia/Shanghai；记录日期以 agent 上报的当地日期为准。

```
GET /api/checkin/projects
→ 200 { "projects": [ { "id": "cp_ab12…", "name": "每日阅读",
      "media_type": "any",                 // video|audio|any（偏好提示，指派兜底规则用）
      "days_of_week": [1,2,3,4,5,6,7],     // 应打日（周一=1…周日=7），仅统计分母/高亮
      "fields_schema": [ {"key":"book","label":"书名","type":"text","required":true},
                         {"key":"pages","label":"页码","type":"text"} ],
      "archive_template": "{date}_{project}_{orig}",
      "classifier_hint": "朗读中文故事，人声",
      "active": true, "sort": 0 } ] }

POST /api/checkin/projects
{ "name": "二胡练习", "media_type": "video", "days_of_week": [1,3,5],
  "fields_schema": [...], "classifier_hint": "二胡演奏，民乐，几乎无人声" }
→ 201 { "project": { … } }        ← name 必填，其余可选

PATCH /api/checkin/projects/:id
{ "name"?: …, "media_type"?: …, "days_of_week"?: …, "fields_schema"?: …,
  "archive_template"?: …, "classifier_hint"?: …, "active"?: bool, "sort"?: number }
→ 200 { "project": { … } }
```

```
GET /api/checkin/today
→ 200 { "date": "2026-11-05",
  "items": [ { "project": {…同上…}, "should": true,          // 今天是否应打日
      "status": "none" | "done",                             // done=当日有 matched 媒体
      "record": null | { "id": "cr_…", "fields": {…},
        "media": [ { "id": "cm_…", "type": "video", "duration_seconds": 1250.3,
                     "preview_status": "ready",               // none|pending|ready|failed|expired
                     "archive_name": "2026-11-05_二胡_良宵x5.mp4",
                     "created_at": "…" } ] } } ],
  "pending": [ {…同上媒体对象, "status": "pending_assign",
                "classifier": {"method": "asr", "evidence": "…"} | null } ] }
```

```
POST /api/checkin/media/:id/assign
{ "project_id": "cp_erhu", "date"?: "2026-11-05" }   // date 缺省=当天；改派时忽略 date，沿用原记录日期
→ 200 { "media": {…}, "record": {…} }
← 404 not_found（媒体或项目不存在 / 项目 inactive）

POST /api/checkin/media/:id/dismiss
→ 200 { "ok": true }                                   // 误投忽略

PATCH /api/checkin/records/:id
{ "fields"?: {…}, "date"?: "2026-11-04" }              // 补字段/改日期；fields 变更触发归档重命名
→ 200 { "record": {…} }

GET /api/checkin/records?project_id=cp_erhu&from=2026-11-01&to=2026-11-05
→ 200 { "records": [ { "id","project_id","date","fields","media":[…], "created_at" } ] }

GET /api/checkin/stats?project_id=cp_erhu&days=30
→ 200 { "streak": 12, "done_days": 18, "days": 30,
        "practice_seconds": 45600,                      // Σ duration（展示用）
        "history": [ {"date":"2026-11-05","status":"done"} , … ] }

GET /api/checkin/media/:id/url                          // 预览片播放地址
→ 200 { "url": "/media/<token>", "expires_at": "…" }    // token 12h
→ 409 conflict                                          // preview_status ≠ ready
```

## Agent 侧接口（X-Agent-Key）

### 打卡媒体上报（v1.4）

```
POST /api/agents/checkin/media
{ "type": "video" | "audio", "orig_name": "IMG_1240.MOV",
  "duration_seconds": 1250.3, "size": 483211234,
  "sha256": "…（可空，去重用）", "date": "2026-11-05",
  "classifier": { "method": "asr", "project_hint": "cp_erhu",
                  "confidence": 0.92, "evidence": "3段片段均无人声/器乐" } }
→ 200 { "media_id": "cm_ab12…", "duplicate": false,
        "assigned": true, "project_id": "cp_erhu", "record_id": "cr_…",
        "archive_name": "2026-11-05_二胡_IMG_1240.mov" }   ← 指派成功：归档名，agent 即刻重命名
→ 200 { "media_id": "cm_…", "assigned": false }            ← 进待指派，agent 移入 holding
```

指派规则（优先级）：① classifier.project_hint 为 active 项目且 confidence≥0.6 → ② 当天恰有一个
无记录的 active 项目且 media_type 兼容 → ③ 待指派。sha256 与近 7 天内已有媒体重复 → 返回已有
media 且 `duplicate: true`（agent 不再处理）。

```
POST /api/agents/checkin/media/:id/content      （请求体 = 预览片字节，≤120MB；
                                                Content-Type: video/mp4 | audio/mp4）
→ 202 { "preview_status": "ready" }             ← preview_expires_at = now + 7 天
→ 413 too_large / 415 unsupported_media_type / 503 unavailable（磁盘水位）

GET /api/agents/checkin/projects                ← 分类用项目清单（agent 缓存，每轮刷新）
→ 200 { "projects": [ { "id", "name", "media_type", "classifier_hint", "active" } ] }

GET /api/agents/checkin/sync                    ← agent 每轮同步：matched（及待指派）媒体
→ 200 { "media": [ { "media_id": "cm_…",       的期望归档名 / 已确认名 / 预览状态，
      "archive_name": "…| null",                 agent 自行差量：
      "current_archive_name": "…| null",          · current ≠ 期望 → 执行重命名
      "preview_status": "none|ready|…",           · preview_status = none → 转码补传
      "type": "video", "date": "2026-11-05" } ] } ← 待指派仅补预览（null 归档名）；date 供按月归档

POST /api/agents/checkin/renames/:media_id/done
{ "archive_name": "2026-11-05_二胡_良宵x5.mp4", "archive_path": "/Users/xx/cijian-archive/2026-11/…" }
→ 200 { "ok": true }                            ← 确认后的名字/路径入库（界面可显示归档位置）
```

### 心跳（30 秒一次）

```
POST /api/agents/heartbeat
{ "handlers": ["print"], "version": "0.2.0",
  "status": "ok",                              // ok | printer-unreachable
  "printer_state": "unreachable",              // 可选：printing|idle|unreachable|paused|unknown
  "detail": { "cups_queue_len": 0,
              "printer_state": "unreachable",
              "printer_message": "Looking for printer." } }
→ 200 { "now": "2026-10-21T08:00:00Z" }
```

副作用：刷新对应 printer 的 `last_seen_at` / `handlers` / `device_state` / 能力字段。
`printer_state=unreachable`（CUPS "Looking for printer."）表示 **agent 在线但打印机硬件不可达**（断电/离线）——与 agent 掉线是两种不同的故障。

### 领取任务

```
POST /api/agents/claims
{ "handler": "print" }
→ 200 { "job": {
        "id": "j_9f3…", "handler": "print",
        "params": { "copies": 2, "color_mode": "color", "duplex": "off" },
        "file": { "url": "/files/<token>", "orig_name": "合影.jpg",
                  "mime": "image/jpeg", "size": 18321 } },
      "lease_expires_at": "2026-10-21T08:02:00Z" }
→ 204   ← 无可领任务
```

领取条件：`status='queued'` 且 `printer_id=本机` 且（`lease_expires_at` 为空或已过期）且 `attempts<3`，按 `created_at` 最旧优先。领取后 `status='claimed'`、`attempts+=1`、`lease=now+120s`。

`file.url` 的 token 为 HMAC 签名短时凭证（15 分钟），仅本任务本 agent 有效。

### 上报状态

```
POST /api/agents/jobs/:id/report
{ "state": "printing", "message": null, "result_code": null }
{ "state": "done",  "message": null,          "result_code": 0 }
{ "state": "failed","message": "卡纸：纸路堵塞", "result_code": 2 }

→ 200 { "ack": true }
→ 409 conflict   ← 租约已过期或任务已被重派（agent 应放弃该任务）
```

- `printing`：status→`printing`，租约顺延至 now+10 分钟
- `done`：status→`done`，租约清空
- `failed`：`attempts<3` → 回 `queued`（租约=now+30s 作退避）；`attempts≥3` → `failed` 终态
- 每次上报追加一条 `job_events`

### 查询任务（agent 崩溃恢复用）

```
GET /api/agents/jobs/:id
→ 200 { "id": "j_9f3…", "handler": "print", "status": "claimed", "attempts": 1,
        "lease_expires_at": "…", "params": {…},
        "file": { "url": "/files/<新签名的token>", "orig_name": "…", "mime": "…", "size": 123 } | null }
→ 404 / 403   ← 任务不存在 / 不属于本机
```

agent 重启时据此判断：租约仍有效 → 恢复处理（file.url 为**新签名的下载地址**）；
已过期或已被重派 → 放弃本地副本，由服务端重派。

### 签名文件下载

```
GET /files/:token
→ 200 <文件字节>（Content-Type 按真实类型）
→ 403 forbidden   ← 签名无效 / 非本任务 agent
→ 410 gone        ← 文件已过期清理
```

token = base64url(`file_id.job_id.printer_id.exp`) + HMAC-SHA256 签名，密钥为 `FILE_URL_SECRET`（env）。

### 媒体播放（v1.4）

```
GET /media/:token                              （无认证头——播放器组件发不了 header）
→ 200/206 <预览片字节>                          ← 支持 Range（seek/拖进度条）
→ 403 forbidden    ← 签名无效
→ 410 gone         ← 预览片已过期清理（保留 7 天）
```

token = base64url(`media_id.exp`) + HMAC-SHA256（同 `FILE_URL_SECRET`），有效期 12h，绑定单个 media。

## 变更流程

接口不兼容变更：先在本文档加「v1.x 变更记录」小节，三仓同步实现后再合入；家庭规模不引入 URL 版本号。

## v1.4 变更记录（2026-11-05 · 每日打卡工具）

- 新增站点侧打卡接口：projects CRUD、today、media assign/dismiss/url、records PATCH/GET、stats（JWT）
- 新增 agent 侧打卡接口：媒体上报（含 AI 分类结果与指派规则）、预览片字节上传、projects 清单、sync 差量同步、重命名确认（X-Agent-Key）
- 新增 `GET /media/:token` 预览片播放（HMAC 签名、12h、支持 Range）
- 数据模型新增 `checkin_projects` / `checkin_records` / `checkin_media`（见 05 §打卡）；`data/media/` 预览片保留 7 天，sweeper 增两项清理
- 设计全文见 docs/10-checkin-plan.md；M-C2 实现时细化：agent 分类需项目清单（`GET /api/agents/checkin/projects`），renames 端点定稿为 `GET /api/agents/checkin/sync`（返回全部 matched 媒体的期望名/当前名/预览状态，agent 差量执行）

## v1.2 变更记录（2026-10-24）

- 心跳新增可选 `printer_state`（CUPS 硬件状态，unreachable=设备不可达），服务端存入 `printers.device_state`
- `GET /api/printers` 响应新增 `deviceState` 字段（前端三态：在线 / 打印机未响应 / 离线）

## v1.1 变更记录（2026-10-22）

- 新增 `GET /api/agents/jobs/:id`（agent 崩溃恢复查询，返回含新签名 file.url；cijian-api 已实现）。
