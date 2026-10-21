# 「此间」执行计划 v1

> 本仓（cijian）定位：**只存需求与设计文档 + 仓库自动化脚本**，不放业务代码。
> 业务代码各自成仓，由脚本自动创建，CI/CD 在各代码仓内配置。

- 日期：2026-10-21
- 状态：Phase 1 已完成；Phase 2（建仓）待 `gh auth login` 后执行

---

## 1. 现状

| 组件 | 现状 | 部署位置 |
|---|---|---|
| 此间站点 | Astro 站点已开发（暂存于本仓，未提交，需迁出） | Vercel，域名 whereami.cn |
| 后端 API | 提供 API + 临时本地文件存储 | 腾讯云服务器 1 台 |
| 任务处理系统 | 每个打印机地点一台服务器，注册各自的任务处理系统；打印系统轮询 API → 打印 → 上报状态 | 各地点服务器 N 台 |
| 本仓 cijian | 已改造为纯文档仓；Astro 站点代码暂存于 `../cijian-site`，bootstrap 时并入 cijian-site 仓 | — |

## 2. 目标仓库拓扑

```
cijian（本仓）        需求 + 设计文档 + 仓库自动化          → 不部署
├── cijian-site       站点：公开内容 + 登录区（上传/打印/结果） → Vercel
├── cijian-api        后端：鉴权 / 文件 / 打印任务 API        → 腾讯云
└── cijian-agent      任务守护进程：可注册多种任务处理器        → 各打印机地点服务器
```

命名与归属已确认：个人账号 `xuxun22` 下（§7 决策 0/1）。

### 系统架构总览

```
                    ┌────────────────────┐
                    │  用户浏览器          │
                    └─────────┬──────────┘
                       https://whereami.cn
                                 ▼
   Vercel            ┌────────────────────┐
                     │  cijian-site       │ 公开内容 + 登录区
                     └─────────┬──────────┘
                               │ HTTPS + JWT
                               ▼
   腾讯云            ┌────────────────────┐
                     │  cijian-api        │ 鉴权/文件/任务 API
                     │  SQLite + 临时文件  │ 磁盘 TTL 清理
                     └────┬─────────▲─────┘
                签名URL下载 │         │ 心跳/领任务/上报状态 (Agent Key)
                            ▼         │
   打印机地点   ┌─────────────────────────┐     ┌────────┐
                │  cijian-agent           │ ──▶ │ 打印机  │
                │  处理器注册表: print, … │     │ (CUPS) │
                └─────────────────────────┘     └────────┘
                 地点A / 地点B / …：全部出站连接，无需公网入站端口
```

关键设计原则：

1. **Agent 拉取式**：地点服务器不开放任何入站端口，只主动出站连接 API（轮询/长轮询）。安全、免公网 IP、穿透 NAT。
2. **处理器注册表**：agent 是「任务框架」，打印只是第一个 handler；每个地点按配置启用不同处理器（呼应“每台服务器注册了不一样的任务处理系统”）。
3. **临时文件短命**：上传文件落盘即带 TTL，任务完成或过期即清，磁盘水位双保险。
4. **任务幂等**：领取任务带租约（lease）+ 尝试次数上限，agent 崩溃重启不会重复打印。

## 3. 本仓目录规划（Phase 1 产出）

```
docs/
├── 00-execution-plan.md     本计划
├── 01-vision.md             站点定位与内容规划
├── 02-prd-print.md          打印功能 PRD（用户故事 + 验收标准）
├── 03-architecture.md       系统架构（组件、时序图、状态机）
├── 04-api-contract.md       API 契约 v1（site↔api↔agent 全量接口）
├── 05-data-model.md         数据模型与文件存储策略
├── 06-security.md           鉴权、密钥、上传与传输安全
├── 07-deploy-cicd.md        各仓 CI/CD 与部署手册
└── adr/                     架构决策记录（每条决策一页纸）
repos.yaml                   代码仓清单（名称/可见性/部署目标/脚手架目录）
scaffold/                    各仓最小脚手架（骨架 + CI workflow，无业务逻辑）
scripts/bootstrap-repos.sh   gh 自动建仓 + 推送脚手架
```

> scaffold 的定位是「仓库骨架的结构定义」：README、CI workflow、目录占位。
> 若你希望本仓绝对零代码文件，可改为脚本内联 heredoc 生成——见 §7 决策 6。

## 4. 阶段计划

### Phase 0 · 准备（人工，~10 分钟）

1. `gh auth login` 重新登录（当前 token 已失效，已验证）
2. 确认 §7 决策清单
3. 确认现有 Vercel 站点是否已有对应 GitHub 仓库（见 §7 决策 0）

### Phase 1 · 文档仓改造（我来做）

- 把本仓现有 Astro 站点代码**暂存本地**（Phase 2 迁入 site 仓），本仓只保留 `docs/` + `repos.yaml` + `scaffold/` + `scripts/`
- 写齐 §3 所列文档（API 契约、数据模型按 §7 确认后的决策写）

### Phase 2 · 自动建仓（跑一次脚本）

`scripts/bootstrap-repos.sh` 流程：

1. 校验 `gh auth status`
2. 读 `repos.yaml`，逐仓执行 `gh repo create <owner>/<name> --private`
3. 拷贝 `scaffold/<name>/` → 初始化 git → push
4. site 仓：把暂存的 Astro 站点代码作为首个业务提交推入
5. 终端打印各仓需要配置的 secrets 清单（下一步用）

产出：3 个代码仓就位，均含 CI workflow 骨架。

### Phase 3 · 实现里程碑（在各自代码仓进行）

| 里程碑 | 内容 | 验收标准 |
|---|---|---|
| M1 鉴权 | 登录（方式见 §7 决策 4）、JWT、site 登录态 | 匿名访问受控接口 401 |
| M2 上传+建任务 | multipart 上传 → 临时文件；选择打印机地点；建打印任务 | 浏览器完整走通「上传→选地点→入队」 |
| M3 Agent 打印闭环 | 轮询领任务（租约）→ 下载 → CUPS 打印 → 上报 | 地点服务器自动出纸；状态流转可见 |
| M4 查看结果 | 任务列表 + 状态流（queued→printing→done/failed） | 站点实时看到每单进度（范围见 §7 决策 5） |
| M5 运维收尾 | TTL 清理、重试策略、心跳掉线告警、限流 | kill agent 中途不重复打印；磁盘可回收 |

每个里程碑 = 代码仓一次 PR/推送 + 本仓对应文档更新。

### Phase 4 · CI/CD 接线（我出 workflow，你填 secrets）

| 仓 | 方式 | 你要配的 secrets |
|---|---|---|
| cijian-site | Vercel 关联仓库，push 即部署，PR 出预览 | 无（Vercel 网页点一次授权） |
| cijian-api | Actions：push main → SSH 到腾讯云 → docker compose 拉起 | `DEPLOY_HOST` `DEPLOY_USER` `DEPLOY_SSH_KEY` |
| cijian-agent | Actions：打 tag → 构建单文件产物（linux amd64/arm64）→ GitHub Release；各地点 `install.sh` 安装 + systemd 扸管 | 无（各服务器手动跑一次 install.sh） |

### Phase 5 · 验收上线

- 端到端清单：上传一张照片 → 选地点 → 出纸 → 站点看到结果
- 异常清单：agent 掉线、文件过期、打印失败重试、重复提交去重
- 监控：API 侧任务状态大盘（一个简单页面即可）；agent 心跳超时告警

## 5. API 契约骨架（详见日后 04-api-contract.md）

```
站点侧（JWT）
  POST /api/auth/login                     → { token }
  POST /api/files            (multipart)   → { file_id, expires_at }
  GET  /api/printers                       → [{ id, location, name, online }]
  POST /api/print-jobs       { file_id, printer_id, copies, options }
                                           → { job_id, status: "queued" }
  GET  /api/print-jobs?status=…            → 任务列表（查看结果用）

Agent 侧（每地点独立 Agent Key）
  POST /api/agents/heartbeat { handlers:[…], status }
  GET  /api/agents/tasks                  → 认领任务（带租约）{ job_id, file_url, options }
  POST /api/agents/tasks/:id/status       { state, message, result? }
  GET  /files/:token                      短时签名下载，仅任务所属 agent 可取

任务状态机：queued → claimed → printing → done | failed(可重试)
```

## 6. 风险与注意

1. **打印重复**：租约过期重派前必须检查本地打印队列，避免同一任务打两份（M5 重点验收）
2. **磁盘**：临时文件必须有 TTL + 水位双保险，否则腾讯云盘会被照片吃满
3. **域名/备案**：Vercel 在境外，whereami.cn 解析到 Vercel 无需备案；但腾讯云 API 若用域名需已备案域名，过渡期可直接 `https://<IP>` + 自签/ACME 证书
4. **密钥轮换**：Agent Key 支持在 API 侧吊销重发，防地点服务器失窃
5. **上传限制**：类型白名单（pdf/jpg/png）+ 大小上限，接口层限流

## 7. 决策记录（2026-10-21 已全部确认）

| # | 决策点 | 结论 |
|---|---|---|
| 0 | Vercel 现状 | 未连任何 GitHub 仓 → **新建** cijian-site |
| 1 | 仓库归属 | **个人账号**（xuxun22） |
| 2 | 后端栈 | **Node**（22 + Hono + SQLite，ADR-002） |
| 3 | Agent 栈 | **Python**（3.10+，ADR-003） |
| 4 | 登录方式 | **单口令** + JWT（ADR-004） |
| 5 | 打印结果口径 | **仅状态与原因**，不回传影像（ADR-005） |
| 6 | scaffold 边界 | 本仓**允许**存放最小骨架（README + CI + 配置占位，无业务逻辑，ADR-006） |
| 7 | api 公网暴露 | 部署时在 06-security §传输 三案（备案直连 / 境外区 / Cloudflare Tunnel）中选一 |

## 8. 立即行动项

1. 你：`gh auth login`（当前 token 已失效）
2. 我：`./scripts/bootstrap-repos.sh`（Phase 2 建仓：site 并入暂存代码 + api/agent 骨架）
3. 你：按 07-deploy-cicd.md 接线（Vercel 导入 site 仓；api 仓配 3 secrets + DEPLOY_ENABLED）
4. 我：M1 起在各代码仓实现（登录 → 上传+任务 → 打印闭环 → 状态页 → 运维）
