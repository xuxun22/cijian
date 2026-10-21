# 时间线（追加式，勿改写历史条目）

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
