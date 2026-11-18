# 系统总览

> 更新：2026-10-22 · 类别：overview · 状态：现行

## 仓库

| 仓库 | 职责 | 部署 |
|---|---|---|
| `cijian`（~/work/cijian） | 文档 + llmwiki + 建仓自动化 | 不部署 |
| `cijian-site`（~/work/cijian-site） | Astro 站点 + 打印工作台（前端待做） | Vercel → whereami.cn |
| `cijian-api`（~/work/cijian-api） | Hono + node:sqlite 后端 | 腾讯云 VM-4-9-ubuntu，Docker Compose |
| `cijian-agent`（~/work/cijian-agent） | Python 纯标准库任务守护进程 | 各打印地点；首台 = 本机 Mac mini |

## 机器与网络

- **服务器**：腾讯云 `VM-4-9-ubuntu`，公网 43.173.111.191，Tailscale `100.78.101.104`（2026-11-18 reimage 后）（旧机 vm-0-4-ubuntu 已于 2026-11-18 销毁）
- **公网端口**：80/443 开（机器上独立 Caddy），22 关闭 → SSH/CI 均走 Tailscale
- **Caddy**：`/etc/caddy/Caddyfile`：`api.whereami.cn, 43-173-111-191.sslip.io → 127.0.0.1:8787`
- **Mac mini**（本机）：launchd 服务 `com.cijian.agent`，CUPS 打印机 `Mi_All_in_One_Inkjet_Printer`

## 域名

| 域名 | 状态 |
|---|---|
| `whereami.cn` | Vercel 站点（已接入） |
| `api.whereami.cn` | **生产 API**（A → 43.173.111.191，Caddy 自动证书） |
| `43-173-111-191.sslip.io` | 备访问入口（新机 sslip） |

## 打印数据流

浏览器/Vercel(https) → cijian-api(SQLite+文件) ← 轮询 ← cijian-agent(Mac mini) → CUPS → 打印机。
浏览器→api 走公网 TLS；agent→api 走公网 TLS（也可换 Tailscale 内网 http，WireGuard 已加密）。
