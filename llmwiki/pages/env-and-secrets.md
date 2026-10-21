# 密钥与口令

> 2026-10-22 · 类别：howto · 仓库：cijian-api / cijian-agent · 状态：现行

## 存放位置

| 密钥 | 位置 | 用途 |
|---|---|---|
| `CIJIAN_PASSPHRASE_HASH` | 服务器 `/opt/cijian-api/app/cijian.env` | 登录口令的 argon2id hash |
| `CIJIAN_JWT_SECRET` | 同上 | JWT 签名 |
| `CIJIAN_FILE_URL_SECRET` | 同上 | 签名下载 URL |
| agent key | Mac mini `~/.config/cijian/agent.env`（600） | p_macmini 的 agent 凭证 |
| 登录口令（明文） | **只在初始部署时告知过用户，不落任何存储** | 家人登录 |

## 轮换

```bash
# 登录口令（在服务器容器里）：
cd /opt/cijian-api/app
sudo docker compose exec -T api node dist/admin.js hash-passphrase --pass '新口令'
# 输出替换 cijian.env 的 CIJIAN_PASSPHRASE_HASH → sudo docker compose up -d

# JWT / FILE_URL secret：openssl rand -hex 32 → 替换 → 重启（JWT 换了所有登录态失效，无害）
# agent key：admin revoke-printer p_xxx → add-printer 重新发放 → 地点服务器改 agent.env 重启
```

## 红线

- 明文口令、agent key、JWT secret **永不进 git**（含 llmwiki 条目——写"见 cijian.env"即可）
- 服务器 env 文件里的 `$` 必须 `$$` 转义（见 gotcha-compose-dollar）
- 本地 Mac 的 `~/.config/cijian/agent.env` 已 chmod 600，勿移动到共享目录
