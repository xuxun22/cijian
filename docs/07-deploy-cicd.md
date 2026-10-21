# 07 · 部署与 CI/CD

> 各代码仓的构建、部署、密钥配置手册。bootstrap 建仓后按本文逐仓接线。

## 总览

| 仓 | CI | 部署 | 需配置 |
|---|---|---|---|
| cijian-site | Actions：构建检查 | Vercel 关联仓库，push 即部署，PR 自动预览 | 无 secrets（Vercel 网页授权一次） |
| cijian-api | Actions：测试 | Actions SSH 到腾讯云 `docker compose up` | 3 个 secrets + 1 个 variable |
| cijian-agent | Actions：静态检查 | 打 tag → Release 源码包；各地点 `install.sh` 安装/升级 | 无 |

## cijian-site（Vercel）

1. <https://vercel.com/new> → Import `xuxun22/cijian-site`
2. Framework 自动识别 Astro，直接 Deploy
3. 环境变量：`PUBLIC_API_BASE = https://api.whereami.cn`（Production + Preview）
4. 域名：Vercel 项目 → Domains → 添加 `whereami.cn`（DNS 按提示配置）
5. 以后 push `main` 自动上线，PR 出预览 URL

CI（仓库自带 `.github/workflows/ci.yml`）：`npm ci && npm run build`，仅做构建守门，部署由 Vercel 自己完成。

## cijian-api（腾讯云）

### 服务器初始化（一次性）

```bash
sudo mkdir -p /opt/cijian-api && sudo chown -R $USER /opt/cijian-api
cd /opt/cijian-api && git clone https://github.com/xuxun22/cijian-api.git app
# compose 文件、TLS（Caddy 或 Cloudflare Tunnel）见 06-security §传输
```

### GitHub 配置

仓库 Settings → Secrets and variables → Actions：

| 类型 | 名称 | 值 |
|---|---|---|
| Secret | `DEPLOY_HOST` | 服务器 IP |
| Secret | `DEPLOY_USER` | SSH 用户 |
| Secret | `DEPLOY_SSH_KEY` | 私钥（该用户对 /opt/cijian-api 有写权限） |
| Variable | `DEPLOY_ENABLED` | `true`（配齐上面三个后再设，workflow 以此为开关） |

`.github/workflows/deploy.yml`（仓库自带）：push `main` → SSH → `git pull && docker compose up -d --build`。

### api 环境变量（服务器 `.env`，不入库）

见 06-security §密钥清单：`CIJIAN_PASSPHRASE_HASH` / `CIJIAN_JWT_SECRET` / `CIJIAN_FILE_URL_SECRET` / `CIJIAN_DATA_DIR` / `PORT`。

生成示例：

```bash
npm run admin -- hash-passphrase --pass '家人口令'   # → CIJIAN_PASSPHRASE_HASH（服务器 env 里 $ 要写成 $$）
openssl rand -hex 32                                 # ×2 → CIJIAN_JWT_SECRET / CIJIAN_FILE_URL_SECRET
```

## cijian-agent（各地点服务器）

### 安装（M3 交付 `install.sh`，此处为目标形态）

```bash
curl -fsSL https://github.com/xuxun22/cijian-agent/releases/latest/download/install.sh | \
  sudo bash -s -- --api https://api.whereami.cn --key <agent_key> --handlers print
```

install.sh 做的事：

1. 建 `/opt/cijian-agent`，下载对应 Release 源码包，创建 venv
2. 写 `/etc/cijian/agent.env`（API 地址、agent key、启用的 handlers、本地 CUPS 打印机名）
3. 装 systemd 单元 `cijian-agent.service` 并启动（`Restart=always`）

### 升级

```bash
sudo /opt/cijian-agent/install.sh --tag v0.2.0   # 下载新 Release 并 systemctl restart
```

### CI/CD

- `ci.yml`：PR / push 时 `compileall` 静态检查（M1 起升级为 ruff + pytest）
- `release.yml`：打 `v*` tag → 打包含源码与 install.sh 的 tarball → GitHub Release

## 运维手册

| 事项 | 操作 |
|---|---|
| 新增打印机地点 | api：`npm run admin -- add-printer --name … --location …`（生成 key，显示一次）→ 地点服务器跑 install.sh |
| 吊销 agent key | api：`npm run admin -- revoke-printer p_xxx` → 该地点立即 401 |
| 换登录口令 | 更新 `CIJIAN_PASSPHRASE_HASH` → 重启 api |
| 备份 | 服务器 cron：每日 `sqlite3 cijian.db ".backup …"`，保留 7 份 |
| 磁盘告警 | sweeper 水位 >90% 时 api 拒收上传并记日志（05）；人工关注 |
| 查看心跳 | site 打印工作台的在线状态，或 `curl -s api/api/printers` |

## 里程碑回执

每个里程碑（M1–M5，见 00-execution-plan §4）完成时：

1. 对应代码仓 push/PR 合入
2. 本仓 `docs/` 同步更新（契约变更先改 04/05）
3. 在 00-execution-plan §4 表格标注 ✔

## 初始部署实录（2026-10-21，vm-0-4-ubuntu）

- Docker 29.1.3 + Compose 2.40.3（apt: docker.io + docker-compose-v2）；ubuntu 已入 docker 组
- 私有仓拉取：服务器 deploy key（`~/.ssh/cijian_deploy`，只读，gh api 注册）；仓库内 `core.sshCommand` 指向它
- **宿主机 80/443 被 ACLI 共享 Caddy 占用** → api 容器仅发布 `127.0.0.1:8787`，
  经 `/etc/caddy/acli.d/sites/cijian-api.caddy` 反代；改动后 `caddy validate` + `systemctl restart caddy`
- env 文件为 `cijian.env`（**不是** `.env`，避免 compose 默认插值源混淆）；argon2 hash 的 `$` 写 `$$`
- 公网入口：`https://43-159-141-66.sslip.io`（即刻可用）；`api.whereami.cn` 待 DNSPod A 记录（值 43.159.141.66）
- 公网 22 关闭：CI/CD 部署需 Tailscale（deploy.yml 已支持 TS_AUTHKEY）；初始部署由 Mac mini 经 Tailscale SSH 手工完成
- 已注册打印机：`p_macmini`（Mac mini，launchd 常驻 `com.cijian.agent`，CUPS：Mi_All_in_One_Inkjet_Printer）
- 端到端验证：登录 → 上传 PNG → 建任务 → agent 领取 → CUPS 出纸（17s）→ done，事件序列完整
