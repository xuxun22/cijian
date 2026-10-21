# 时间线（追加式，勿改写历史条目）

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
