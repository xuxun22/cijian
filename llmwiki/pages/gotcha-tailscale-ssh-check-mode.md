# gotcha：Tailscale 默认 SSH 策略 check 模式，无人值守 SSH 会永久挂起

> 2026-10-22 · 仓库：cijian-api（CI/CD）· 类别：gotcha · 状态：现行

## 症状

GitHub Actions 的部署步骤（appleboy/ssh-action → Tailscale IP:22）**零日志挂起 12 分钟**：
没有 banner、没有认证失败、没有任何输出。Tailscale 接入步骤本身是成功的
（runner 设备已注册：`tailscale status` 可见 `github-runnervmxehtw`，active; direct）。

## 根因

服务器 `tailscale up --ssh` 开了 **Tailscale SSH**：尾网内目标为 22 端口的连接被 tailscaled
截获，**不走 sshd / authorized_keys**，而是按尾网策略的 `ssh` 小节判定。

Tailscale **默认策略**的 ssh 规则第一条是 `action: "check"`——要求来源设备**先去浏览器
完成一次确认**才放行。交互式终端（人的电脑）能看到确认提示所以能过；
CI runner 全自动无人值守，永远无法完成确认 → 连接被无限期挂起。

另外注意：这条路径上 **DEPLOY_SSH_KEY 私钥根本不参与认证**（被 tailscaled 截获），
所以"密钥对不对"的排查方向从一开始就是错的。

## 解法

Tailscale 管理台 → Access controls → ssh 小节把 `action: "check"` 改为 `"accept"`
（家庭尾网全是自己设备，可接受失去浏览器复核）：

```json
"ssh": [
  {
    "action": "accept",
    "src":    ["autogroup:member"],
    "dst":    ["autogroup:self"],
    "users":  ["autogroup:nonroot", "root"]
  }
]
```

改完无需重启任何东西，下一次连接即生效。

## 预防

- 无人值守的 SSH（CI/脚本）遇到"零输出挂起"，先想到 **check 模式 / ACL 静默丢弃**，
  再想密钥——判断依据：有 banner 的认证失败会很快报错，静默挂起是策略层丢包。
- CI 用的 auth key 建议勾选 **Ephemeral**（runner 设备用完自动从尾网消失，不堆积设备）。
- runner 上的 tailscale 版本由 github-action 安装，版本旧会触发尾网的
  "known security vulnerability" 告警——一次性 CI 机器风险低，可在 action 里固定新版消除告警。
- 同类场景备选方案：服务器 systemd timer 自拉取（5 分钟），完全不依赖 runner 网络（本仓曾用它过渡）。
