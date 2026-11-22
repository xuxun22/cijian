# AI 一次性工作区自动清理

- 日期：2026-11-22 · 仓库：cijian-agent · 类别：howto · 状态：有效

## 背景

`prepare_workspace` 每个一次性任务建一个 `<agent>-<ms>-<pid>` 目录（memory-review、
skill-review、shine-*、digest、outing…），跑完不删；agent 常驻几周不重启就会一直堆。
chat 的持久 home（`<state>/ai/work/home`）必须永远保留。

## 实现（agent `runner.cleanup_workspaces` + `worker._cleanup_workspaces`）

- 命名白名单正则 `^[a-z0-9][a-z0-9-]*-\d{13}-\d+$`：**只删长得像一次性工作区的目录**，
  `home`、不认识的文件/目录、symlink 一律不碰（symlink 跳过，避免误伤链接目标）。
- 年龄按**目录本身 mtime**：opencode 只在目录内部新增文件，不会刷新目录 mtime，
  所以 mtime ≈ 创建时间。
- 配置 `CIJIAN_AI_WORKDIR_KEEP_DAYS`（默认 7 天，`<=0` 关闭清理）。
- 触发点：worker 启动时一次 + 每个 AI 任务结束后（`handle` 的 finally），内部节流
  1 小时一次；清理失败只 log.warning，绝不影响任务。
- 日志示例：`清理旧工作区 7 个（0.0 MB）：assistant-digest-…、skill-review-…`。

## 实测（2026-11-22 上线）

首跑删了 7 个 11-12~11-15 的目录（共 ~0 MB——一次性工作区里只有 agent md，
占盘可忽略，清理主要为了目录整洁可读）；home 完好，7 天内的目录全保留。

## 顺带确认的机制（排查时留下的疑问）

- 12:37 生产 home 的 `opencode.json` 缺 `skills` 键，不是 bug：那是调试时手动调
  `prepare_home`+`install_mcp`（没传 skills_dir）留下的；真实对话 `_chat` 一定传
  `skills_dir=str(self.skills_dir)`，13:31 的真实 chat 已把配置重写为带 `skills` +
  `CIJIAN_DEV_PROJECTS` 字面量（1034 字节）。
- 验证命令：
  `python3 -c "import json;print(json.load(open('…/work/home/opencode.json')).get('skills'))"`
