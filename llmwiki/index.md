# 索引

> LLM 回答问题前先读本文件定位相关页面。新增页面必须登记于此。

## 总览

- [overview](pages/overview.md) — 此间系统全景：四个仓、服务器、域名、agent、数据流
- [engineering-standards](pages/engineering-standards.md) — **Harness 规则：每仓必跑测试、lint/类型规则、产品层判定（用户友好/风格统一/产品语义）**，SKILL.md 内置强制清单
- [deployment-tencent-vm](pages/deployment-tencent-vm.md) — 旧机 vm-0-4-ubuntu 部署实录（2026-11-18 已销毁，仅供历史参考）
- [print-pipeline](pages/print-pipeline.md) — 打印闭环的状态机、租约、重试、防重打
- [checkin-pipeline](pages/checkin-pipeline.md) — 每日打卡 v1.4：投递即打卡、AI 指派、预览片 7 天/签名URL播放
- [assistant-architecture](pages/assistant-architecture.md) — 家庭助手架构：微信回调→ai_tasks 任务平面→agent(opencode+MCP)→API 代发；三种身份与两个队列
- [privacy-iron-law](pages/privacy-iron-law.md) — **铁律：腾讯云服务器不存任何家庭私密信息（≤7 天缓存通道可，判据=随时删服务器不丢数据）；真相源=Mac mini；checkin 预览为缓存、合规**
- [papers-pipeline](pages/papers-pipeline.md) — 错题本（docs/17）：第 1 步已上线——本地 papers.db、AirDrop 图片扫描、180s 多页分组、年级自动成长
- [weekend-outing](pages/weekend-outing.md) — 周六出门建议：每周六 08:30 推 3 个上海亲子选项（天气/档期/多样性/距离），回 1/2/3 与「反馈：…」；偏好即时固化家庭 wiki
- [get-takeover](pages/get-takeover.md) — get 产品线（GitLab get-aico 9 仓）由 cijian agent 接管开发的调研结论与一期设计指针；get-dev 已停摆
- [dev-plan-approval](pages/dev-plan-approval.md) — 编码通道计划先行 + 小程序开发看板；JWT/企微身份绑定、同毫秒排序坑
- [env-and-secrets](pages/env-and-secrets.md) — 密钥与口令的存放位置、轮换方法

## 踩坑（gotcha）

- [wechat-reply-latency](pages/wechat-reply-latency.md) — **微信图片 ~1 分钟才有回复**：图片不进对话只走错题本（45s 防抖+vision），chat 模型从未接入看图；文字 15~30s=模型首轮 10~13s+重试翻倍；含 P0~P2 改进计划

- [devflow-push-main](pages/devflow-push-main.md) — **dev 通道 committed ≠ 上线**：旧终态只是本地分支；「提交」已升级为合并 main+push+各仓部署（push-main）

- [gotcha-compose-dollar](pages/gotcha-compose-dollar.md) — compose 对 env 文件做 `$` 插值，argon2 hash 需 `$$` 转义
- [gotcha-bash-fullwidth](pages/gotcha-bash-fullwidth.md) — bash `$VAR` 紧邻全角字符导致 unbound variable
- [gotcha-node-sqlite](pages/gotcha-node-sqlite.md) — better-sqlite3 在新 Node 上编译失败 → 迁移 node:sqlite 三连坑
- [gotcha-migrate-order](pages/gotcha-migrate-order.md) — **列迁移写在 openDb()、种子在 migrate() → 老库启动崩（no such column），生产 crash loop；测试新库永远复现不了**
- [gotcha-sslip-tls](pages/gotcha-sslip-tls.md) — DNS 未配时用 sslip.io 拿即时 TLS；正式域名的接线清单
- [gotcha-tailscale-ssh-check-mode](pages/gotcha-tailscale-ssh-check-mode.md) — Tailscale 默认 SSH 策略 check 模式，CI runner 无人值守 SSH 永久挂起
- [gotcha-cors-www-origin](pages/gotcha-cors-www-origin.md) — Vercel 主域是 www，CORS 白名单只写裸域导致前端全被拦
- [gotcha-mp-domain-check](pages/gotcha-mp-domain-check.md) — 小程序真机「连不上服务器」= 域名未备案被微信拦截；urlCheck:false 本地永远复现不了
- [gotcha-mp-upload-filename](pages/gotcha-mp-upload-filename.md) — wx.uploadFile 无法自定义 multipart 文件名，orig_name 变 tmp_xxx → formData 传 name + 服务端优先采用
- [gotcha-mcp-isolated-config](pages/gotcha-mcp-isolated-config.md) — 隔离 XDG_CONFIG_HOME 后 MCP 配置没跟着搬，26 个能力工具全丢，模型表现为「我做不到」
- [gotcha-whereami-com](pages/gotcha-whereami-com.md) — whereami.com 是第三方网站非本项目域名；根路径静态文件（WW_verify 等）放 cijian-site/public/ 推 main 即生效
- [gotcha-skill-archive-recursive](pages/gotcha-skill-archive-recursive.md) — opencode 递归扫描 skills 目录，归档技能放 `.archive/` 里照样被加载；归档要放同级 skills-archive
- [gotcha-opencode-free-quota](pages/gotcha-opencode-free-quota.md) — 免费模型共享额度，压测后连对话一起 429；错误只在 stdout 事件流，stderr 可能是空的
- [gotcha-airdrop-mtime-watermark](pages/gotcha-airdrop-mtime-watermark.md) — **AirDrop 保留拍摄 mtime/ birthtime，水位线按 mtime 判把当天投递当旧文件永久跳过**；到达时间必须 `max(mtime, birthtime, ctime)`

## howto 补充

- CD 双通道：cijian-api 推 main 即部署（Tailscale + SSH），另有服务器 5 分钟自拉取 timer 兜底
- [cijian-api-deploy](pages/cijian-api-deploy.md) — 生产部署拓扑（腾讯云 + Caddy + Tailscale + 5 分钟自拉取）与迁移步骤/坑
- [shine-ai-plane](pages/shine-ai-plane.md) — 看见闪光 AI 平面 + v1.6 每日看见：API 任务队列（不调模型）+ agent opencode 执行 + 私有 wiki 记忆/视图发布 + 20:45 微信卡/反馈，含嵌套事务、wx 无 PATCH、wiki 组串行等坑
- [opencode-runner](pages/opencode-runner.md) — agent 用 `opencode run` 做 AI 执行器的实测契约：JSON 输出在 `part.text`、`.opencode/agents/`（复数）profile、`--file` 附图、延迟基线、wiki deploy key 流程
