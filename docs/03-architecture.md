# 03 · 系统架构

## 组件

| 组件 | 技术 | 部署 | 职责 |
|---|---|---|---|
| cijian-site | Astro + TypeScript | Vercel | 公开内容 + 登录区（打印工作台 UI） |
| cijian-api | Node 22 + Hono + better-sqlite3 | 腾讯云 1 台 | 鉴权、文件收发、任务调度、心跳、TTL 清理 |
| cijian-agent | Python 3.10+（systemd 常驻） | 每个打印机地点 1 台 | 拉取任务 → 执行（打印）→ 上报状态 |

## 网络拓扑

```
浏览器 ──https──▶ Vercel(site) ──https+JWT──▶ 腾讯云(api)
                                                ▲
                                                │ https+AgentKey（纯出站）
                            地点A agent ────────┤
                            地点B agent ────────┘   → 本地打印机(CUPS)
```

**关键约束：地点服务器零入站端口。** agent 只主动出站连接 api（心跳 30s / 领任务 / 上报），无需公网 IP、无 NAT 问题、攻击面最小。

## 打印闭环时序

```
用户      site        api                    agent(地点X)
 │ 上传文件 │           │                        │
 │─────────▶│──────────▶│ POST /api/files        │
 │          │  file_id  │                        │
 │ 选地点提交│           │                        │
 │─────────▶│──────────▶│ POST /api/print-jobs   │
 │          │  job_id(queued)                    │
 │          │           │◀── POST /agents/heartbeat (30s 一次)
 │          │           │◀── POST /agents/claims │ 领最老的 queued 任务
 │          │           │   job(claimed, lease 120s)
 │          │           │◀── POST /agents/jobs/:id/report {printing}
 │          │           │◀── GET /files/:token ── 签名 URL 下载(15min 有效)
 │          │           │        lp -n 2 ...     │ 调 CUPS 打印
 │          │           │◀── POST /agents/jobs/:id/report {done|failed}
 │ 刷新列表  │           │                        │
 │─────────▶│──────────▶│ GET /api/print-jobs    │
```

## 任务状态机

```
                 ┌─────────────┐
   领取(attempts+1, lease=now+120s)
                 │  queued    │──────────────────────▶ claimed
                 └─▲───▲──────┘                          │
                   │   │                                │ report{printing}
   文件过期(未开印) │   │ 租约超时/失败重试               ▼
      → expired    │   │ (lease=now+30s 退避)        printing ──report{done}──▶ done ✔
                   │   └───────────────────────────────┤
                   │        attempts≥3 时不再重派       │
                   └─────────────────── report{failed} ┴──▶ failed ✔ (终态)
```

- **租约即退避**：`queued` 且 `lease_expires_at` 未到的任务不可被领取——失败重试与领任务超时共用这一机制，无需额外字段。
- **终态**：`done` / `failed` / `expired`。
- 完整字段与转换规则见 `05-data-model.md`。

## 幂等与防重打

1. 领取即占租约，同一任务同时只有一个 agent 持有。
2. agent 崩溃重启后：本地状态文件记录「正在处理」的 job_id；恢复时先 `GET` 该任务归属，租约仍在则继续，不在则放弃——**不重打**。
3. 兜底：提交 CUPS 前检查本地队列中是否已存在同 job 标记的打印请求（`lp` 的 job-name 带上 cijian job_id）。

## 处理器注册表（扩展机制）

呼应「每台服务器注册了不一样的任务处理系统」：agent 是任务框架，打印只是第一个 handler。

- agent 配置启用哪些 handler（如 `print`；未来：相框同步、备份同步…），心跳时上报能力
- 任务带 `handler` 字段（首版恒为 `print`），`claims` 只派发 agent 声明能力内的任务
- 新任务类型 = 新增 handler 模块 + 配置启用，api 无需改动

## 技术选型

| 决策 | 结论 | 详见 |
|---|---|---|
| Agent 通信方向 | 纯拉取（出站） | ADR-001 |
| 后端栈 | Node 22 + Hono + SQLite(WAL) + 磁盘文件 | ADR-002 |
| Agent 栈 | Python 3.10+，requests + lp(CUPS) | ADR-003 |
| 登录 | 单口令 + JWT | ADR-004 |
| 打印结果 | 仅状态，不回传影像 | ADR-005 |
| 文件存储 | 本地磁盘 + TTL（不引入对象存储） | ADR-007 |
