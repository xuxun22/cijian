# 系统总览

> 更新：2026-10-22 · 类别：overview · 状态：现行

## 仓库

| 仓库 | 职责 | 部署 |
|---|---|---|
| `cijian`（~/work/cijian） | 文档 + llmwiki + 建仓自动化 | 不部署 |
| `cijian-site`（~/work/cijian-site） | Astro 站点 + 打印工作台（前端待做） | Vercel → whereami.cn |
| `cijian-api`（~/work/cijian-api） | Hono + node:sqlite 后端 | 腾讯云 vm-0-4-ubuntu，Docker Compose |
| `cijian-agent`（~/work/cijian-agent） | Python 纯标准库任务守护进程 | 各打印地点；首台 = 本机 Mac mini |

## 机器与网络

- **服务器**：腾讯云 `vm-0-4-ubuntu`，硅谷区（na-siliconvalley，无需备案），公网 43.159.141.66，Tailscale 100.127.52.69
- **公网端口**：80/443 开（宿主共享 Caddy），22 关闭 → SSH/CI 均走 Tailscale
- **宿主 Caddy**：ACLI 共享管理，扩展点 `/etc/caddy/acli.d/sites/*.caddy`（cijian-api 已接入），**admin API 已关**，改配置用 `systemctl restart caddy`
- **Mac mini**（本机）：launchd 服务 `com.cijian.agent`，CUPS 打印机 `Mi_All_in_One_Inkjet_Printer`

## 域名

| 域名 | 状态 |
|---|---|
| `whereami.cn` | Vercel 站点（已接入） |
| `https://43-159-141-66.sslip.io` | api 临时域名，sslip.io 通配解析 → 43.159.141.66，**即刻可用** |
| `api.whereami.cn` | **待办**：DNSPod 加 A 记录 → 43.159.141.66，Caddy 站点块已就绪，加完即生效 |

## 打印数据流

浏览器/Vercel(https) → cijian-api(SQLite+文件) ← 轮询 ← cijian-agent(Mac mini) → CUPS → 打印机。
浏览器→api 走公网 TLS；agent→api 走公网 TLS（也可换 Tailscale 内网 http，WireGuard 已加密）。
