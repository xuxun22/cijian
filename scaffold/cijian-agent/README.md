# cijian-agent · 此间任务守护进程

运行在每个打印机地点的服务器上：**纯出站**连接 cijian-api——心跳上报能力、领取任务、执行（打印，经 CUPS `lp`）、上报状态。

架构与防重打设计见文档仓 [`cijian`](https://github.com/xuxun22/cijian)：`docs/03-architecture.md`。

## 安装（M3 交付 install.sh 后）

```bash
curl -fsSL https://github.com/xuxun22/cijian-agent/releases/latest/download/install.sh | \
  sudo bash -s -- --api https://api.whereami.cn --key <agent_key> --handlers print
```

agent_key 由 cijian-api 的 admin 命令发放（见 `docs/07-deploy-cicd.md §运维手册`）。

## 里程碑

- [ ] M3 打印闭环（心跳 / 领取 / 下载 / lp / 上报 / 幂等防重打）
- [ ] M5 重试退避与掉线恢复
