# opencode 延迟基准脚本（2026-11-22）

配合 [opencode-latency-bench](../../pages/opencode-latency-bench.md) 使用。三个脚本都依赖本机
`cijian-agent` 的代码与 `~/.config/cijian/agent.env`（模型/凭证），并在 `/tmp` 下建临时 home。

| 脚本 | 用途 |
|---|---|
| `latency_bench.py` | 最初归因：纯启动 / 真实 agent 环境 / 无 MCP / 带图，逐个变量拆 |
| `threeway.py` | 决定性对照：现状 `--standalone` vs 预启服务 + CLI `--server` vs HTTP API 直连 |
| `phases.py` | 单次会话的事件阶段拆解（execution/step/tool 各段耗时） |

运行：

```bash
python3 threeway.py
python3 phases.py
```

注意：

- 脚本会 `install_mcp` 写 `/tmp/ocbench/home/opencode.json`，令牌是假的（`bench-fake-token`），
  只测耗时，工具调用会失败——这是预期的。
- 预启服务鉴权：`Basic base64("opencode:<server password>")`；密码在 `opencode serve` 启动日志里。
- 完成信号听 `session.execution.succeeded/failed/interrupted`，没有 `session.idle`。
- 图片附件必须是 `files:[{uri:"file:///abs/path"}]`。
- 改配置后要显式 `POST /api/location/reload`；靠文件 watch 会拖到 ~4s。
