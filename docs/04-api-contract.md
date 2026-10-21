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

### 上传文件

```
POST /api/files                         （multipart/form-data，字段名 file）
→ 201 { "file_id": "f_ab12…", "orig_name": "合影.jpg", "mime": "image/jpeg",
       "size": 18321, "expires_at": "2026-10-22T09:00:00Z" }
→ 415 / 413 / 429（登录用户每分钟 ≤10 次）
```

服务端校验 magic bytes，不信任扩展名；文件名随机化存储，原名仅入库。

### 打印机列表

```
GET /api/printers
→ 200 { "printers": [
  { "id": "p_laowu", "name": "老家打印机", "location": "外婆家",
    "online": true, "handlers": ["print"],
    "color": true, "duplex": false,
    "last_seen_at": "2026-10-21T07:59:40Z" } ] }
```

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
      "copies": 2, "attempts": 1, "last_message": null,
      "created_at": "…", "updated_at": "…" } ] }

GET /api/print-jobs/:id
→ 200 { …同上单条…, "events": [
      { "state": "queued",  "message": null,              "source": "user",        "created_at": "…" },
      { "state": "claimed", "message": null,              "source": "agent:p_laowu","created_at": "…" },
      { "state": "printing","message": null,              "source": "agent:p_laowu","created_at": "…" } ] }
```

## Agent 侧接口（X-Agent-Key）

### 心跳（30 秒一次）

```
POST /api/agents/heartbeat
{ "handlers": ["print"], "version": "0.1.0",
  "status": "ok", "detail": { "cups_queue_len": 0 } }
→ 200 { "now": "2026-10-21T08:00:00Z" }
```

副作用：刷新对应 printer 的 `last_seen_at` / `handlers` / 能力字段。

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

### 签名文件下载

```
GET /files/:token
→ 200 <文件字节>（Content-Type 按真实类型）
→ 403 forbidden   ← 签名无效 / 非本任务 agent
→ 410 gone        ← 文件已过期清理
```

token = base64url(`file_id.job_id.printer_id.exp`) + HMAC-SHA256 签名，密钥为 `FILE_URL_SECRET`（env）。

## 变更流程

接口不兼容变更：先在本文档加「v1.x 变更记录」小节，三仓同步实现后再合入；家庭规模不引入 URL 版本号。
