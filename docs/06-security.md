# 06 · 安全

> 威胁模型按家庭规模设定：防陌生人、防爆破、防滥用；不追求对抗定向攻击。

## 资产

1. 家庭照片等上传文件（隐私）
2. 打印能力本身（防滥用：被陌生人拿来打东西）
3. 地点服务器的 agent key（失窃风险）

## 认证

### 站点用户：单口令（ADR-004）

- 口令的 **hash** 存于 api 环境变量 `CIJIAN_PASSPHRASE_HASH`（argon2id；代码不接触明文口令）
- 登录接口限速：同 IP 每分钟 5 次，超发 429；连续失败叠加指数退避
- 成功后签发 JWT（HS256，`CIJIAN_JWT_SECRET`，7 天）；无刷新令牌，过期重输
- 私有接口一律校验 `Authorization: Bearer`；401 不区分「token 过期」与「没带」，不泄露信息

### 地点 Agent：每地点独立 key

- `printers.key_hash` 存 SHA-256，**明文 key 只在发放时显示一次**（admin CLI：`npm run admin -- add-printer`）
- 所有 agent 接口要求 `X-Agent-Key`，查表定位 printer 身份
- **吊销即失效**：admin CLI 删/换 key 后，心跳立刻 401——服务器失窃时一键止血
- key 生成：`openssl rand -hex 32`

## 授权

- 签名文件 URL：`HMAC(file_id.job_id.printer_id.exp)`，15 分钟有效，**绑定任务与地点**——A 地的 agent 拿不到 B 地任务、也拿不到已过租约任务的文件（403）
- 文件不可枚举：随机文件名 + Web 根外存储 + 无目录列表
- CORS：仅放行 `https://whereami.cn`（开发时另放行 Vercel 预览域），私有接口拒绝其他 Origin

## 上传安全

- 白名单 `pdf|jpg|png`，**magic bytes 校验**（不信任扩展名与 Content-Type）
- 大小上限 20MB（multipart 解析前先检查 Content-Length）
- 登录态 + 限速：每用户每分钟 10 次
- 文件不执行、不内联渲染——`Content-Disposition: attachment` + `X-Content-Type-Options: nosniff`（签名下载响应头）

## 传输（api 的公网暴露方案）

⚠️ 约束：站点在 Vercel（https），浏览器 fetch 到自签证书或纯 HTTP 的 api 都会被浏览器拦截。因此 **自签 / 裸 HTTP 不可用**，必须真证书 + 真域名。

| 方案 | 适用 | 做法 |
|---|---|---|
| **A** | whereami.cn 已备案 | DNS：`api.whereami.cn` → 腾讯云 IP；服务器上 Caddy 自动 ACME |
| **B** | 服务器在境外区域（香港/新加坡等，无需备案） | 同 A，直接 ACME |
| **C** | 大陆服务器 + 未备案 | Cloudflare Tunnel：服务器跑 `cloudflared` 出站建隧道，`api.whereami.cn` 走 Cloudflare 代理——无需开入站端口、无需备案 |

- Agent → api 同样走该 HTTPS 域名（python requests 校验公共 CA，不 `verify=False`）
- 服务器防火墙：方案 A/B 只开 443（22 限源 IP）；方案 C 可不开任何入站端口

> **初始部署现状（2026-10-21）**：服务器实测在**硅谷区**（无需备案）。正式域名 DNS 未配，
> 暂以 `https://43-159-141-66.sslip.io`（sslip.io 通配解析 → 43.159.141.66，Caddy ACME 真证书）对外，
> Caddy 站点块已同时包含 `api.whereami.cn`（DNSPod 加 A 记录后自动生效）。
> agent→api 亦可走 Tailscale 内网 `http://100.127.52.69:8787`（WireGuard 端到端加密，明文 HTTP 可接受）。

## 日志与审计

- 不落明文口令 / agent key / JWT；日志中文件只出现 file_id
- 登录失败记 IP 与次数（限速依据）
- `job_events` 即操作审计：谁（user/api/agent:xxx）何时把任务改成了什么

## 密钥清单（api 环境变量）

| 变量 | 用途 |
|---|---|
| `CIJIAN_PASSPHRASE_HASH` | 登录口令 hash（argon2id） |
| `CIJIAN_JWT_SECRET` | JWT 签名（≥32 字节随机） |
| `CIJIAN_FILE_URL_SECRET` | 签名下载 URL（独立于 JWT，≥32 字节随机） |
| `CIJIAN_DATA_DIR` | SQLite + files 根目录 |

轮换：三个 secret 均可热换（重启 api 生效）；换 `JWT_SECRET` 会使所有登录态失效——家人重新输一次口令即可。
