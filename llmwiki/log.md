# 时间线（最新在前 · 追加式，勿改写历史条目）

## [2026-10-24] gotcha | CORS 来源不匹配：Vercel 主域是 www

打印工作台登录全被 CORS 拦截 → 根因是 Vercel 把 www 设为主域，前端 Origin 为
`https://www.whereami.cn` 而白名单只有裸域。修复：CORS 改为正则放行 `*.whereami.cn` 家族。
同日清理了一次 compose 并发竞态留下的孤儿容器（18e7b3be9f95_app-api-1）。

## [2026-10-24] fix | 打印机「假在线」盲区：心跳携带 CUPS 硬件状态

**症状**：打印机断电后，工作台仍显示「在线」（agent 心跳正常），任务默默排队。
**根因**：心跳只报了 agent 存活，没报 CUPS 打印机硬件状态——`lpstat -p` 的
"Looking for printer." 状态消息没人采集。
**修复**：心跳携带 `printer_state`（unreachable=设备不可达），API 存 `printers.device_state`，
前端三态展示（在线 / 打印机未响应 / 离线）；打印等待期间不可达超 3 分钟 → 取消 CUPS
任务并报失败（防止来电后突然补打积压任务）。
见 [print-pipeline](pages/print-pipeline.md) §两种离线。

## [2026-10-22] mp | 微信小程序打印工作台（M-mp-1~3）

原生 TS；口令登录、相册/拍摄/聊天文件三入口上传（wx.uploadFile 原生进度）、
打印机三态、任务列表轮询 + 事件时间线、转发家庭群卡片。仓库 `cijian-mp`。
上线前置：小程序备案 + whereami.cn 域名 ICP（见 docs/09）。

## [2026-10-22] fix | CI/CD 打通：Tailscale SSH check 模式挂起 runner

deploy 挂起 12 分钟零输出 → 根因是 Tailscale 默认 SSH 策略 check 模式（新设备需浏览器确认，
runner 无法完成）。用户改 accept + 换 ephemeral auth key 后，push 即部署全链路打通
（Tailscale 接入 → SSH → git pull → compose 重建 → healthy，全程 <1 分钟）。
见 [gotcha-tailscale-ssh-check-mode](pages/gotcha-tailscale-ssh-check-mode.md)。

## [2026-10-22] howto | Harness 规则成文：每仓测试/lint/产品判定 + enforce 接线

新增 [engineering-standards](pages/engineering-standards.md)：每仓校验命令、类型与 lint 规则、
产品层判定（等待必有反馈/错误文案人话/纸墨朱砂令牌/契约先行/noindex/防重打优先）。
enforce 接线：api CI 增加 typecheck 关卡、agent CI 升级 ruff+compileall、
SKILL.md 内置「提交前检查清单」。推动因：用户要求规则可校验、可强制执行。

## [2026-10-22] fix | 任务卡「已接受」：agent 漏报 printing 致租约超时

见 [print-pipeline](pages/print-pipeline.md) §实战记录。修复：lp 提交成功即上报 printing（租约 600s），
轮询期间每 4 分钟续租；顺带照片 fit-to-page 单页打印、超时默认放宽到 30 分钟。agent v0.1.2。

## [2026-10-22] seed | llmwiki 初始化

以 Karpathy llmwiki 模式初始化本维基；回填 2026-10-18 ~ 10-22 初始部署期间的 7 条经验。

## [2026-10-21] deploy | cijian-api 首次部署到腾讯云 vm-0-4-ubuntu

Docker 29 + Compose 2.40；API 走 127.0.0.1:8787，公网入口挂 ACLI 共享 Caddy。
`https://43-159-141-66.sslip.io/api/health` 全绿。打印机 p_macmini 注册成功。

## [2026-10-21] e2e | 打印闭环端到端验证通过

登录 → 上传 autumn-walk.svg.png → 建任务 j_ae77f097634bd2d8 → agent 领取 → CUPS 出纸 → done。
事件序列 queued→claimed→claimed→done（含一次租约重派，符合设计）。

## [2026-10-21] gotcha | bash $VAR 紧邻全角括号（bootstrap 与 install.sh 各中一次）

见 [gotcha-bash-fullwidth](pages/gotcha-bash-fullwidth.md)。

## [2026-10-21] gotcha | compose env_file 的 $ 插值吃掉 argon2 hash

见 [gotcha-compose-dollar](pages/gotcha-compose-dollar.md)。

## [2026-10-21] decision | better-sqlite3 → node:sqlite

见 [gotcha-node-sqlite](pages/gotcha-node-sqlite.md) 与 ADR-002 修订。
