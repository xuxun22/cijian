# 索引

> LLM 回答问题前先读本文件定位相关页面。新增页面必须登记于此。

## 总览

- [overview](pages/overview.md) — 此间系统全景：四个仓、服务器、域名、agent、数据流
- [engineering-standards](pages/engineering-standards.md) — **Harness 规则：每仓必跑测试、lint/类型规则、产品层判定（用户友好/风格统一/产品语义）**，SKILL.md 内置强制清单
- [deployment-tencent-vm](pages/deployment-tencent-vm.md) — 腾讯云 vm-0-4-ubuntu 初始部署实录与拓扑
- [print-pipeline](pages/print-pipeline.md) — 打印闭环的状态机、租约、重试、防重打
- [env-and-secrets](pages/env-and-secrets.md) — 密钥与口令的存放位置、轮换方法

## 踩坑（gotcha）

- [gotcha-compose-dollar](pages/gotcha-compose-dollar.md) — compose 对 env 文件做 `$` 插值，argon2 hash 需 `$$` 转义
- [gotcha-bash-fullwidth](pages/gotcha-bash-fullwidth.md) — bash `$VAR` 紧邻全角字符导致 unbound variable
- [gotcha-node-sqlite](pages/gotcha-node-sqlite.md) — better-sqlite3 在新 Node 上编译失败 → 迁移 node:sqlite 三连坑
- [gotcha-sslip-tls](pages/gotcha-sslip-tls.md) — DNS 未配时用 sslip.io 拿即时 TLS；正式域名的接线清单
- [gotcha-tailscale-ssh-check-mode](pages/gotcha-tailscale-ssh-check-mode.md) — Tailscale 默认 SSH 策略 check 模式，CI runner 无人值守 SSH 永久挂起

## howto 补充

- CD 双通道：cijian-api 推 main 即部署（Tailscale + SSH），另有服务器 5 分钟自拉取 timer 兜底
