# 腾讯云 vm-0-4-ubuntu 部署实录

> 2026-10-21 · 类别：howto · 仓库：cijian-api · 状态：现行

## 服务器画像

- Ubuntu 24.04.4，硅谷区（metadata: `na-siliconvalley`），2C/3.6G/59G
- 用户 `ubuntu`，passwordless sudo；SSH 仅 Tailscale 可达（公网 22 关闭）
- Docker 29.1.3 + Compose 2.40.3（apt: docker.io + docker-compose-v2）

## 部署拓扑（重要：与最初设想不同）

- **宿主机 80/443 被 ACLI 共享 Caddy 占用**（arkcli 体系，admin off）——容器内不再跑 Caddy
- api 容器只发布 `127.0.0.1:8787`；公网入口 = 共享 Caddy 的站点块：

```
/etc/caddy/acli.d/sites/cijian-api.caddy
  api.whereami.cn, 43-159-141-66.sslip.io {
      reverse_proxy 127.0.0.1:8787
  }
```

- 改完配置：`sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl restart caddy`
  （admin off 所以 reload 不可用；restart 是亚秒级）

## 私有仓库拉取（deploy key）

```bash
ssh-keygen -t ed25519 -f ~/.ssh/cijian_deploy -N '' -C cijian-api-deploy
# pub key 在 Mac 上：gh api repos/xuxun22/cijian-api/keys -f title=... -f key="$PUB" -F read_only=true
git config core.sshCommand "ssh -i ~/.ssh/cijian_deploy -o StrictHostKeyChecking=accept-new"
```

注意 `gh api -f key="$PUB"` 会把布尔传成字符串——布尔字段必须用 `-F`。

## 环境变量

`/opt/cijian-api/app/cijian.env`（600 权限）。**argon2 hash 的 `$` 必须写成 `$$`**，
见 [gotcha-compose-dollar](gotcha-compose-dollar.md)。

## CI/CD 现状

`deploy.yml` 已写好（Tailscale Action + appleboy SSH），被 `vars.DEPLOY_ENABLED` 开关挡住。
启用前置：Tailscale 管理台生成 auth key → 仓库 Secret `TS_AUTHKEY` + `DEPLOY_HOST=100.127.52.69`。
（GitHub 托管 runner 无法直连公网 22，这是走 Tailscale 的原因。）
