# cijian-api · 此间后端

Node 22 + Hono + SQLite：登录鉴权（单口令 + JWT）、文件收发（TTL 临时存储）、打印任务调度、agent 心跳。

接口契约（`docs/04-api-contract.md`）与数据模型（`docs/05-data-model.md`）以文档仓 [`cijian`](https://github.com/xuxun22/cijian) 为准。

## 开发

```bash
npm install
npm run dev
```

## 部署

GitHub Actions SSH 到腾讯云执行 `docker compose up -d --build`。
需在仓库配置：Secrets `DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_SSH_KEY`，Variable `DEPLOY_ENABLED=true`。
详见文档仓 `docs/07-deploy-cicd.md`。

## 环境变量

复制 `.env.example` 为 `.env` 并填值（生成方法见 `docs/06-security.md`）。

## 里程碑

- [ ] M1 鉴权（登录 / JWT / 私有接口守卫）
- [ ] M2 文件上传 + 打印任务
- [ ] M3 agent 接口（心跳 / 领取 / 上报）
- [ ] M5 sweeper（TTL / 租约 / 水位）
