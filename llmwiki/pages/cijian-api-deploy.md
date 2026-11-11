# cijian-api 部署与迁移（腾讯云 + Caddy + Tailscale）

- 日期：2026-11-11 · 仓库：cijian-api · 类别：ops · 状态：有效

## 当前生产

| 项 | 值 |
|---|---|
| 主机 | `43.173.111.191`（VM-4-9-ubuntu，Ubuntu 24.04，2C/2G） |
| tailnet | `cijian-api` = `100.94.198.50`（`--ssh`，`--accept-dns=false`） |
| 路径 | `/opt/cijian-api/app`（deploy key 只读，id 169463064） |
| 反代 | 独立 Caddy 2.11：`api.whereami.cn` + `43-173-111-191.sslip.io` → `127.0.0.1:8787` |
| 证书 | Let's Encrypt 生产（Caddyfile 全局 `acme_ca` 显式指定） |
| 自愈 | `cijian-deploy.timer` 5 分钟 `git pull --ff-only` + `docker compose up -d --build` |
| CI/CD | Actions secrets `DEPLOY_HOST/USER/SSH_KEY` 已指向新机；`workflow_dispatch` 22s 通过 |

旧机 `43.159.141.66`（vm-0-4-ubuntu / 100.127.52.69）保留为回滚退路，24h 后可停。

## 迁移必做

1. 数据必须**干净停机后**复制 `cijian.db` + `-wal` + `-shm`（宿主机常无 sqlite3 CLI）。
2. `data/` 归 root（容器内 root 写），`cijian.env` 归 ubuntu 600，argon2 的 `$` 写 `$$`。
3. `CIJIAN_JWT_SECRET` / `FILE_URL_SECRET` / `PASSPHRASE_HASH` 必须沿用旧值，否则老 token 全失效、老签名链接全 404。
4. DNS 切完后**再做一次数据同步**，否则切换窗口内的打卡/媒体会丢。
5. 安全组必须放行 80/443，否则 ACME 直接失败。

## 坑

- Caddy 失败后退避可达 600s；放行防火墙后 `systemctl restart caddy` 立即重试。
- `tailscale ssh` 的 ACL 是按**用户名**授权的：本机 `ssh xuxun22@...` 被拒，`tailscale ssh ubuntu@...` 正常。
- CI 用的 Tailscale authkey 会提示 deprecated（建议换 OAuth client），但当前可用。
- 部署脚本用 `flock` 防重入；两台机器各自跑 timer 互不干扰。
