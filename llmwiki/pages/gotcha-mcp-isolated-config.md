# MCP 工具全丢：XDG_CONFIG_HOME 隔离后模型说「我做不到」

> 2026-11-14 · 仓库：cijian-agent · 类别：gotcha · 状态：已修

## 症状

微信里让助手「在 docs 下建个文件 / 改个功能」，它回：

- 「现在交不出去，等下再试一次。」
- 「我做不到，我建不了文件。」

但同一台机器上直接 `opencode run --agent assistant-chat` 完全正常，工具也能调。
`~/Library/Logs/cijian-mcp.log` 里**没有任何工具调用记录**——说明请求根本没到 MCP。

## 根因

对话子进程为了隔离本机 24 个开发技能与开发 MCP，把 `XDG_CONFIG_HOME` 指到工作区内的空目录（`runner.isolate_config`）：

```python
env["XDG_CONFIG_HOME"] = str(workdir / ".xdg-config")
```

而 `install_mcp` 只把能力 MCP 配置写到**工作区根**的 `opencode.json`。
隔离生效后，opencode 读的是 `$XDG_CONFIG_HOME/opencode/opencode.json`（不存在），26 个能力工具一个都没注册。
模型手里只剩 `skill` 工具，于是把 `dev_task` 当技能调：

```
Unable to load skill dev_task
```

报错后它没有重试，直接照提示词说了「交不出去」——看起来像模型不行，其实是工具没挂上。

## 解法

`runner.install_mcp` 同时写两份配置：

```python
text = json.dumps(config, ensure_ascii=False, indent=2)
(workdir / "opencode.json").write_text(text, encoding="utf-8")          # 项目根
isolated = workdir / ".xdg-config" / "opencode"
isolated.mkdir(parents=True, exist_ok=True)
(isolated / "opencode.json").write_text(text, encoding="utf-8")         # 隔离后的 XDG 配置
```

验证方式（必须看到 `mcp connected` + 工具真的回话）：

```bash
env -i PATH=... HOME="$HOME" XDG_CONFIG_HOME="$PWD/.xdg-config" ... \
  opencode run --standalone --print-logs --agent assistant-chat \
  --model opencode/mimo-v2.6-flash-free --auto "调用 cijian_dev_board"
# 日志里应有：message="mcp connected" server=cijian tools=26
```

## 预防

1. **「小模型不稳」先排除工具没挂上**：查 `cijian-mcp.log` 有没有那次调用；没有就是配置/权限问题，不是模型问题。
2. 隔离任何 `XDG_*` 目录时，检查配置是否也需要跟着搬一份。
3. 模型会把工具名当技能名调，提示词里写全名（`cijian_dev_task`）并注明「不是技能」；「做不到」类回复在 worker 里重试一次。
