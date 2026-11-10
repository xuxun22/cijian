# M-B0 Spike 结论（2026-11-11 · 看见闪光 / Agent AI 任务平面）

> 验收项：opencode JSON 契约、专用 agent profile、analyze 延迟基线、图片视觉、私有仓+deploy key。
> 结论：**全部通过，拓扑定稿，可以进入 M-B1（API 任务平面）**。

## 1. opencode JSON 契约 ✅

- `opencode run --standalone --format json --auto "<msg>"` 输出**单行 JSON**，模型文本在 `part.text`，
  其余字段（sessionID/timestamp/time.start|end）可用于审计与耗时统计。
- `--standalone` 私有服务器启动开销 ≈ **1.2s**（每次任务独立，不依赖/不干扰常驻后台服务）。

## 2. 专用 agent profile ✅

- 位置：工作区 `.opencode/agents/<name>.md`（注意是 **agents** 目录）；
  frontmatter：`description / mode: primary / model / permissions / steps`，正文 = system prompt。
- `shine-analyze` 实测配置：

```yaml
permissions:
  - { action: "*", resource: "*", effect: deny }     # 先全禁
  - { action: read,  resource: "*", effect: allow }  # 再放行只读
  - { action: glob,  resource: "*", effect: allow }
  - { action: grep,  resource: "*", effect: allow }
steps: 2
```

- `--agent shine-analyze` 正确加载；禁 shell/edit/webfetch 后模型行为正常（纯文本进出）。
- `--model` 显式指定覆盖 frontmatter，两者保持一致即可。

## 3. analyze 延迟基线 ✅（好于预估）

| 场景 | wall time（含启动 1.2s） | 模型耗时 |
|---|---|---|
| 文字 · 完整 prompt + 5 few-shot | **6.4 ~ 8.5s**（2 次） | 5.7 ~ 7.7s |
| 图片（`--file` 附图） | **10.6s** | 9.8s |

预估 p50 8~15s 偏保守；实际 p50 ≈ 7s（免费档模型）。维持「异步 202 + 前端轮询」设计，
timeout 180s 余量充足。**direct 快通道（Phase 3 备选）暂无必要**。

## 4. 输出质量（真实 prompt v1）✅

- JSON 严格符合契约：`kind/highlight/strength/growth_note/say_this/lighter/avoid/tags/need_more` 全字段。
- 禁用词 0；用「孩子」不猜性别；不虚构细节。
- 图片规则生效：附 logo 图测试，模型**真的看到了画面**（描述出「一大一小两个身影背对着光」），
  且因无学习/生活行为线索正确走 `need_more` 请家长补一句——没有臆造。

## 5. 私有仓 + deploy key ✅

- `github.com:xuxun22/cijian-family-wiki`（**PRIVATE**）已建。
- deploy key `cijian-agent`（写权限）已挂；私钥在 `~/.config/cijian/wiki_deploy_key`（600）。
- clone → commit → push 全链路验证通过（`GIT_SSH_COMMAND=ssh -i … -o IdentitiesOnly=yes`）。
- wiki 骨架已种子：`AGENTS.md`（schema 全文）/ `index.md` / `log.md`。

## 6. 定稿拓扑（与 13 号文档一致）

- Mac mini：`CIJIAN_HANDLERS=print,checkin,ai`，唯一 wiki 写者（deploy key 在此机）。
- 后续加机器：只报 `shine.analyze` 能力，不配 wiki key。
- agent 任务子进程 env 白名单（剔除 agent key/deploy key），`HOME` 指向任务工作区。

## 7. 遗留/注意事项

- `opencode run` 每次冷启 ~1.2s——若未来量大可评估常驻 server 模式，MVP 不做。
- 免费档模型偶发波动，`max_attempts=2` + 退避足够。
- 图片经 `--file` 附加即走视觉通道，无需手工 base64（agent 侧只需下载到工作区）。
