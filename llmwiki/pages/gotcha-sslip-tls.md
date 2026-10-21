# howto：DNS 未配时的即时 TLS（sslip.io）与正式域名接线清单

> 2026-10-21 · 仓库：cijian-api · 类别：howto · 状态：现行

## 背景

浏览器（https 页面）fetch 后端必须也是 https（混合内容会被浏览器拦截），
且证书必须可信——自签证书、纯 HTTP、IP 直连都不可行。
但 `api.whereami.cn` 的 A 记录还没配（DNS 在 DNSPod）。

## 解法：sslip.io 通配 DNS

`43-159-141-66.sslip.io` 由 sslip.io 解析到 43.159.141.66——零配置获得一个
指向服务器的真域名，Caddy 对它走 ACME 拿真证书。**即刻可用**：

```bash
curl https://43-159-141-66.sslip.io/api/health   # {"ok":true}
```

## 正式域名接线清单（api.whereami.cn）

1. DNSPod 控制台 → whereami.cn → 添加记录：主机 `api`，类型 `A`，值 `43.159.141.66`
2. Caddy 站点块已同时包含 `api.whereami.cn`（/etc/caddy/acli.d/sites/cijian-api.caddy），
   DNS 生效后 Caddy 自动签证书，无需重启
3. 验证：`curl https://api.whereami.cn/api/health`
4. Vercel 项目环境变量 `PUBLIC_API_BASE=https://api.whereami.cn`（站点前端引用）
5. 服务器公网 22 仍关闭：CI 部署走 Tailscale Action（见 deploy.yml 注释与 deployment-tencent-vm）

## 陷阱

- 服务器公网 80/443 由 ACLI 共享 Caddy 占用——**不要**再起容器级 Caddy（端口冲突）
- Caddyfile 的 admin API 是关的，改配置用 `caddy validate` + `systemctl restart caddy`
