# 索引

> LLM 回答问题前先读本文件定位相关页面。新增页面必须登记于此。

## 总览

- [overview](pages/overview.md) — 此间系统全景：四个仓、服务器、域名、agent、数据流
- [engineering-standards](pages/engineering-standards.md) — **Harness 规则：每仓必跑测试、lint/类型规则、产品层判定（用户友好/风格统一/产品语义）**，SKILL.md 内置强制清单
- [deployment-tencent-vm](pages/deployment-tencent-vm.md) — 腾讯云 vm-0-4-ubuntu 初始部署实录与拓扑
- [print-pipeline](pages/print-pipeline.md) — 打印闭环的状态机、租约、重试、防重打
- [checkin-pipeline](pages/checkin-pipeline.md) — 每日打卡 v1.4：投递即打卡、AI 指派、预览片 7 天/签名URL播放
- [env-and-secrets](pages/env-and-secrets.md) — 密钥与口令的存放位置、轮换方法

## 踩坑（gotcha）

- [gotcha-compose-dollar](pages/gotcha-compose-dollar.md) — compose 对 env 文件做 `$` 插值，argon2 hash 需 `$$` 转义
- [gotcha-bash-fullwidth](pages/gotcha-bash-fullwidth.md) — bash `$VAR` 紧邻全角字符导致 unbound variable
- [gotcha-node-sqlite](pages/gotcha-node-sqlite.md) — better-sqlite3 在新 Node 上编译失败 → 迁移 node:sqlite 三连坑
- [gotcha-sslip-tls](pages/gotcha-sslip-tls.md) — DNS 未配时用 sslip.io 拿即时 TLS；正式域名的接线清单
- [gotcha-tailscale-ssh-check-mode](pages/gotcha-tailscale-ssh-check-mode.md) — Tailscale 默认 SSH 策略 check 模式，CI runner 无人值守 SSH 永久挂起
- [gotcha-cors-www-origin](pages/gotcha-cors-www-origin.md) — Vercel 主域是 www，CORS 白名单只写裸域导致前端全被拦
- [gotcha-mp-domain-check](pages/gotcha-mp-domain-check.md) — 小程序真机「连不上服务器」= 域名未备案被微信拦截；urlCheck:false 本地永远复现不了
- [gotcha-mp-upload-filename](pages/gotcha-mp-upload-filename.md) — wx.uploadFile 无法自定义 multipart 文件名，orig_name 变 tmp_xxx → formData 传 name + 服务端优先采用
- [gotcha-whereami-com](pages/gotcha-whereami-com.md) — whereami.com 是第三方网站非本项目域名；根路径静态文件（WW_verify 等）放 cijian-site/public/ 推 main 即生效

## howto 补充

- CD 双通道：cijian-api 推 main 即部署（Tailscale + SSH），另有服务器 5 分钟自拉取 timer 兜底
- [cijian-api-deploy](pages/cijian-api-deploy.md) — 生产部署拓扑（腾讯云 + Caddy + Tailscale + 5 分钟自拉取）与迁移步骤/坑
- [shine-ai-plane](pages/shine-ai-plane.md) — 看见闪光 AI 平面：API 任务队列（不调模型）+ agent opencode 执行 + 私有 wiki 记忆/视图发布，含嵌套事务、wx 无 PATCH 等坑
- [opencode-runner](pages/opencode-runner.md) — agent 用 `opencode run` 做 AI 执行器的实测契约：JSON 输出在 `part.text`、`.opencode/agents/`（复数）profile、`--file` 附图、延迟基线、wiki deploy key 流程
