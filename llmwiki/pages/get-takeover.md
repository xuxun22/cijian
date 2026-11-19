# get 产品线接管调研（get-dev → cijian-agent）

> 日期：2026-11-18 · 仓库：cijian（本文）/ get-dev · 类别：overview · 状态：现行（一期设计已出）

## 是什么

评估「get 产品系列 repo 能否由 cijian agent 接管开发」的调研结论 + 一期设计指针。
正式方案：`docs/16-get-takeover-plan.md`（API 契约、repos.json 扩展、prompt 草稿、实施步骤）。

## 关键事实

- **get 产品线**：自建 GitLab `http://git.getneuton.com:8090`（API 明文 HTTP、git 走 SSH，
  本机 key 已验证可达），group `get-aico`，9 个仓。release 分支：get-models=`fast-ray`，其余 main。
  有 CI 的：get-models / get-quick-model / get-ui / model-explainer。
- **`~/get` 下不是所有目录都属 get-aico**：qlib（微软 GitHub clone）、patent-xai / pocs /
  qlib_data / quant-connect 是本地杂物，白名单别收。
- **get-dev（原 agent）已停摆**：本机 launchd 未装载（`launchctl list | grep getdev` 空）、
  `.log/gate.log` 与 `state.json` 不存在、heartbeat master 是另一台机 RacheldeiMac.local
  且租约 2026-11-18 06:30Z 已过期、wiki 最后活动 2026-10-09。
- **get-dev 资产可复用**：wiki（9/9 仓页面 + system-architecture 跨仓影响表 +
  verification-loops + local-e2e + dev-principles）、`agent/verify.d/*.sh` 12 个实测验证脚本、
  `agent/gitlab.py` 纯 stdlib GitLab 客户端。
- **get-dev 有自己的项目级 llmwiki skill**（`~/get/get-dev/.opencode/skill/llmwiki/SKILL.md`，
  2026-11-19 建）：交互会话在 get-dev 目录里维护 wiki 用（查/记/lint/桩整备，英文条目、
  log 带 HH:MM）。它只进交互会话——自动 dev 通道的一次性 workspace 不装 skill（P9 隔离
  不变）。
- **两边架构同构**：worktree 隔离、验证环、llm-wiki、人审门、commit 由 worker。接管 =
  把 get-dev 的触发/知识/验证/MR 四部件搬进 cijian dev 通道。

## cijian-agent 侧的三个硬缺口（方案 P1-P4 对应）

1. `devwork.verify()` 只认 package.json（npm typecheck/test）——Python/Java 仓被静默跳过。
2. dev 任务从不 push、无 MR——commit 只落本地 `assistant/<dev_id>` 分支。
3. 无 GitLab 客户端；触发源只有企微文本（需要 gate→intake 桥）。

## 实施时容易踩的

- **get-ui 的 `npm ci` 需要 GITLAB_TOKEN 做 npm registry 认证**
  （`//git.getneuton.com:8090/:_authToken`，见 verify.d/get-ui.sh）——装依赖必须 worker
  侧带 token 做（临时 NPM_CONFIG_USERCONFIG），模型子进程 env 白名单（SAFE_ENV_KEYS）
  天然没有 token，装好依赖后 `npm run build` 无需 registry。
- get-quick-model 本地 `mvn compile` 是坏的（Lombok 预处理，pre-existing）；真 gate 是 MR CI。
- get-models pytest 套件 known-stale（API 漂移），verify 只做 flake8+make。
- 信任边界：get 是公司资产；`collect_commits` 定时上报要按项目过滤，别把公司提交标题
  发进家庭日报（方案 P4.6）。
- **opencode 的 `external_directory deny` 只管原生 read/edit/glob/grep，管不到 shell**：
  dev.md 白名单里的 `cat *`/`rg *`/`find *` 是软边界，模型可读机器上用户可读的任何文件
  （含 agent.env 密钥）。get 版 profile 已删通配读命令——看文件走原生工具；硬边界需
  opencode bash sandbox（Seatbelt，落地核对）。
- 双 agent 打架：接管后必须卸载所有机器上的 com.getdev.agentpoll（含 RacheldeiMac）。
