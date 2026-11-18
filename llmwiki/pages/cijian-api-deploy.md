# cijian-api 部署与迁移（腾讯云 + Caddy + Tailscale）

- 日期：2026-11-11 · 仓库：cijian-api · 类别：ops · 状态：有效

## 当前生产

| 项 | 值 |
|---|---|
| 主机 | `43.173.111.191`（VM-4-9-ubuntu，Ubuntu 24.04，2C/2G） |
| tailnet | `100.78.101.104`（reimage 后节点名 `vm-4-9-ubuntu`；迁移时为 `cijian-api`/100.94.198.50） |
| 路径 | `/opt/cijian-api/app`（deploy key 只读，id 169463064） |
| 反代 | 独立 Caddy 2.11：`api.whereami.cn` + `43-173-111-191.sslip.io` → `127.0.0.1:8787` |
| 证书 | Let's Encrypt 生产（Caddyfile 全局 `acme_ca` 显式指定） |
| 自愈 | `cijian-deploy.timer` 5 分钟 `git pull --ff-only` + `docker compose up -d --build` |
| CI/CD | Actions secrets `DEPLOY_HOST/USER/SSH_KEY` 已指向新机；`workflow_dispatch` 22s 通过（2026-11-18 复测 29s） |
| 残留清理 | 2026-11-18 已停生产机用户级 `hermes-gateway.service`（`disable --now`，无 cron 任务，4.4GB 数据保留待 reimage）；现行架构无 Hermes 运行时依赖 |

旧机 `43.159.141.66`（vm-0-4-ubuntu / 100.127.52.69）**已于 2026-11-18 销毁**（当时保留作回滚退路，确认迁移稳定后清理）。

## 迁移必做

1. 数据必须**干净停机后**复制 `cijian.db` + `-wal` + `-shm`（宿主机常无 sqlite3 CLI）。
2. `data/` 归 root（容器内 root 写），`cijian.env` 归 ubuntu 600，argon2 的 `$` 写 `$$`。
3. `CIJIAN_JWT_SECRET` / `FILE_URL_SECRET` / `PASSPHRASE_HASH` 必须沿用旧值，否则老 token 全失效、老签名链接全 404。
4. DNS 切完后**再做一次数据同步**，否则切换窗口内的打卡/媒体会丢。
5. 安全组必须放行 80/443，否则 ACME 直接失败。

## reimage 实录（2026-11-18，清掉 Hermes 残留）

背景：生产机迁移后仍带着旧 Hermes gateway（4.4GB，无 cron 任务）。停用后决定 reimage 成干净系统。

**备份（reimage 前）**：干净停机拷 `data/`（db+wal+shm）、`cijian.env`、`docker-compose.yml`、
`deploy.sh`、systemd unit/timer、`Caddyfile`、`~/.ssh/{cijian_deploy,authorized_keys}`、Hermes 小状态；
本机 `.local/share/cijian-backups/2026-11-18-reimage/`（含 RESTORE.md，SHA256 双向校验，`PRAGMA integrity_check=ok`）。

**重装后交付物**：干净 Ubuntu 24.04 + Tailscale 已接入（`tailscale up --ssh --accept-dns=false`），
给新 Tailscale IP 即可接管；公网 IP 保留（DNS 不用改）。

**重建顺序**：docker/compose → deploy key + clone → 恢复 data（root:root）与 cijian.env（600）
→ `docker compose up -d --build` → Caddy（官方 apt 源 + 原 Caddyfile，证书自动签发）
→ `cijian-deploy.timer` → `authorized_keys` → `gh secret set DEPLOY_HOST <新 Tailscale IP>`。

**坑**：
- `cat 大文件 | tailscale ssh host "cat > /tmp/x"` 在本地命令超时被 SIGTERM 时会把远端文件**截断**
  （实测 5.7MB → 2.5MB，且解包出半套 data）。大文件传输要单独一条命令 + 远端 `sha256sum` 校验后再解包。
- 新 Tailscale 节点 IP 会变（100.94.198.50 → 100.78.101.104），必须更新 `DEPLOY_HOST` secret；
  CI 部署实测 28s 通过。
- 恢复后核对数据计数（reminders/wecom_users/wecom_messages/ai_tasks）比看 health 更能确认没丢数据；
  agent 的 `last_seen_at` 会在一分钟内自动刷新。

## 坑

- Caddy 失败后退避可达 600s；放行防火墙后 `systemctl restart caddy` 立即重试。
- `tailscale ssh` 的 ACL 是按**用户名**授权的：本机 `ssh xuxun22@...` 被拒，`tailscale ssh ubuntu@...` 正常。
- CI 用的 Tailscale authkey 会提示 deprecated（建议换 OAuth client），但当前可用。
- 部署脚本用 `flock` 防重入；两台机器各自跑 timer 互不干扰。
