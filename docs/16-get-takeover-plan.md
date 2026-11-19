# 16 · get 产品线接管一期方案（issue → 企微方案 → 批准 → 实现 → GitLab draft MR）

> 状态：设计稿（待批准） · 日期：2026-11-19
> 前置调研结论见 llmwiki `pages/get-takeover.md`。
> 一期范围：走通单 issue 全链路 + 提交开出 draft MR；MR 评论响应 / CI 自动修复 / post-merge followup 留二期。

## 1. 背景与目标

get 产品线 = 自建 GitLab（`http://git.getneuton.com:8090`，group `get-aico`）上 9 个仓。
原开发者 agent（get-dev，位于 `~/get/get-dev`）已停摆：launchd 未装载、heartbeat 租约过期、
最后活动 2026-10-09。cijian-agent 的编码通道（docs/14 §17、dev-plan-approval）刚落地
plan 先行 + 微信/小程序审批，具备承载能力。

**一期目标**：在 get-ui 开一个打了 `agent-take` 标签的测试 issue，一小时内企微收到方案；
回「批准」后 agent 在隔离 worktree 实现、跑该仓验证环；回「提交」后 push 分支并在
GitLab 开出 draft MR（描述含 `Closes #iid`、影响分析、验证结果）。cijian 项目行为完全不变。

**明确不做（一期）**：MR 评论自动响应、CI 红 pipeline 自动修复、post-merge followup、
直接提交仓（get-dev 自身仍走 MR）、多 host 租约、按项目付费模型档（只留配置口）。

## 2. 改造后链路

```
GitLab issue(标签 agent-take)
   │ ①launchd 每小时（Mac mini）
   ▼
get-dev gate（纯 shell+python3，零 LLM）── idle → 退出，零 token
   │ 有新 issue：② 在 issue 评论「已接手」+ ③ POST /api/agents/dev/intake
   ▼
cijian-api：dedupe(source_key) → 建 dev_tasks(planning) → 入队 dev.task(plan)
   ▼
cijian-agent worker：领任务 → 装配 get 工作区(wiki知识+get版prompt)
   → dev-plan-get（只读出方案）→ 微信发方案（爸爸批）
   │ 「批准」
   ▼
dev-get（execute）：worktree 实现 → worker 跑 per-repo 验证环 → 微信报改动+检查
   │ 「提交」
   ▼
worker：commit → push assistant/<dev_task_id> → GitLab REST 开 draft MR
   → 微信回 MR 链接；MR 描述 Closes #iid + 影响分析 + 验证记录
```

关键边界不变：**commit/push/开 MR 都由 worker 做，模型子进程无凭证无 push 权**；
`SAFE_ENV_KEYS` 白名单天然阻止 `GITLAB_TOKEN` 下传 opencode。

## 3. 部件设计

### P1 · repos.json 扩展（cijian-agent `devwork.py`）

现有 schema 只有 `root`+`repos`。新增 project 级可选字段（旧格式照读不误）：

```json
{
  "default": "cijian",
  "projects": {
    "cijian": {
      "root": "~/work",
      "repos": ["cijian", "cijian-api", "cijian-agent", "cijian-site", "cijian-mp"]
    },
    "get": {
      "root": "~/get",
      "repos": ["benchmark", "forwardneural", "get-dev", "get-models",
                "get-quick-model", "get-ui", "model-explainer", "model-store", "qlib-alpha"],
      "plan_agent": "dev-plan-get",
      "dev_agent": "dev-get",
      "model": "",
      "verify_timeout": 600,
      "setup":  { "get-ui": "npm-ci-gitlab-registry" },
      "verify": {
        "get-models":       "cd py && flake8 src/ --count --select=E9,F63,F7,F82 && make all",
        "get-ui":           "npm run build",
        "model-explainer":  "python3 -m ruff check backend/ && make all && cd backend && python3 -m unittest discover tests/",
        "get-quick-model":  "mvn -q compile -s maven-settings.xml",
        "model-store":      "make all",
        "benchmark":        "python3 -m compileall -q src run_with_monitor.py",
        "forwardneural":    "node --check assets/app.js && node --check mock/fred.js && node --check mock/forecasts.js",
        "qlib-alpha":       "python3 -m compileall -q .",
        "get-dev":          "python3 -m compileall -q agent"
      },
      "release_branches": { "get-models": "fast-ray", "*": "main" },
      "push": "gitlab-draft-mr"
    }
  }
}
```

- `verify` 命令全部提炼自 get-dev `agent/verify.d/*.sh`（VERIFIED 2026-10-02）。**落地时逐仓
  复跑一遍核对**；已知偏差：get-quick-model 本地 mvn 编译是坏的（Lombok 预处理，pre-existing，
  真正的 gate 是 MR 的 CI pipeline）→ 该仓验证结果只记 informational，不阻塞提交；
  qlib-alpha 深度 smoke 需要沙盒数据，一期只做语法环。
- `devwork.verify()` 查找顺序：project.verify[repo] → 现有 package.json 逻辑（cijian 仓不变）
  → 无（记「没跑」）。命令用 `child_env`，cwd=该仓 worktree，超时用 `verify_timeout`（默认 420）。
- `setup`（worker 侧、execute 前一次性）：`npm-ci-gitlab-registry` 是内置动作名——
  照 verify.d/get-ui.sh 的做法：临时 npmrc（repo 自带 .npmrc + 追加
  `//git.getneuton.com:8090/:_authToken=$GITLAB_TOKEN`）→ `NPM_CONFIG_USERCONFIG=… npm ci`，
  失败回退 `npm install --no-audit`。**必须 worker 做**：模型子进程 env 里没有 token，
  而且也不该有。装好后模型跑 `npm run build` 无需 registry。
- `push`：`gitlab-draft-mr`（get）| 默认空 = 现状 local-only（cijian 不动）。
- `release_branches`：MR 目标分支表。

### P2 · cijian-api：intake 端点 + source_key 去重

迁移（照现有 migration pattern）：

```sql
ALTER TABLE dev_tasks ADD COLUMN source_key TEXT;
CREATE UNIQUE INDEX idx_dev_tasks_source ON dev_tasks(source_key) WHERE source_key IS NOT NULL;
```

新路由（`routes/agents.ts` 面，`requireAgent`，与 heartbeat/claims 同级）：

```
POST /api/agents/dev/intake
Headers: X-Agent-Key: <printer key>
Body:
{
  "project": "get",
  "issues": [
    {"repo": "get-ui", "iid": 12, "title": "GN3.1 面板移动端折叠",
     "description": "……", "url": "http://git.getneuton.com:8090/get-aico/get-ui/-/issues/12"}
  ]
}

200 →
{"created": [{"dev_task_id": "dt_…", "source_key": "get-aico/get-ui#12"}],
 "skipped":  ["get-aico/get-ui#13"]}
```

行为：
- `source_key = "<group>/<repo>#<iid>"`；命中即 skipped（幂等，gate 每小时重发也安全）。
- requester 默认取 `wecom_users` 里 `role='dad'` 的 user_id（body 可覆盖）；project 透传。
- prompt 模板：`【get-ui #12】<title>\n\n<description 截断>\n\n<link>`（plan agent 靠它定位仓库）。
- 建单后走现链路：`createDevTask(planning)` → `startDevPlan` → enqueue `dev.task(phase=plan)`，
  payload 加 `source_key`/`source_url`，plan 完照常 deliverChat 微信。
- 校验：issues ≤5 条/次、description ≤4000、repo 必须字母数字（防注入），非法条目整批 400。
- dev_tasks 读面（看板/详情）加返回 `source_key`，MR 开出后 `result` 里存 MR url。

### P3 · cijian-agent：GitLab 客户端 `cijian_agent/gitlab.py`

从 `~/get/get-dev/agent/gitlab.py` 移植（纯 stdlib urllib，已实战验证），精简为 worker 所需：

- `api(method, path, data, params)` —— 带超时与错误包装（`_http_error` 模式保留）
- `create_draft_mr(project_id, source_branch, target_branch, title, description)`
- `issue_note(project_id, iid, body)`（二期评论响应用，一期仅保留接口）
- `project_id_by_name(name)`（启动时缓存 group projects 映射）

配置（agent.env，`config.py` 新键）：

```
CIJIAN_GITLAB_URL=http://git.getneuton.com:8090
CIJIAN_GITLAB_GROUP=get-aico
CIJIAN_GITLAB_TOKEN=<group access token, Developer+api scope>
```

纪律沿用 get-dev：token 永不进日志、不进子进程 env、不 commit。git push 走 SSH
（本机 key 已验证可达 `git@git.getneuton.com`），**token 只用于 REST**。

### P4 · worker 改造（`worker.py`）

1. **按项目选 prompt/model**：`_dev_plan`/`_dev_execute` 读 project 的
   `plan_agent/dev_agent/model`（默认 `dev-plan`/`dev`/`ai_dev_model`），
   `runner.install_agent(workspace, agent_name, …)` 相应换名。
2. **知识装配**（见 P6）。
3. **execute 前 setup**：对 `setup` 表里的仓在 worktree 上跑安装动作（worker env 含 token）。
4. **验证**：`devwork.verify()` 按 P1 顺序；get-quick-model 这类 informational 结果原样进
   报告文本，不拦截。
5. **`_dev_commit` 扩展**（project.push == gitlab-draft-mr 时）：
   ```
   commit（现状） → 逐仓 push origin assistant/<dev_id>:assistant/<dev_id>
   → create_draft_mr(project_id, assistant/<dev_id>, release_branch(repo),
        title="Draft: <subject> (#<iid>)",
        description=MR 模板)
   → cleanup(keep_branch=False)（远端已有，本地分支不再保留）
   → 返回 text 带 MR url
   ```
   MR 描述模板：
   ```
   Closes #<iid>

   由 cijian 家庭助手编码通道生成（get-dev agent 已由其接管）。分支 assistant/<dev_task_id>。

   **Impact analysis:** <从已批准的 plan 摘录涉及仓库/文件>
   **Local verification:** <verify 输出（含 informational 项）>
   **Assumptions:** <plan 里的假设，无则省>
   ```
6. **隐私开关**：`collect_commits`（dev_commits 定时上报）加项目过滤——
   config 新键 `ai_dev_report_projects`（默认 `cijian`），get 的提交标题不进家庭日报。
7. **wiki 沉淀（无 skill、零额外 token）**：push+MR 成功后，worker 用手头已有素材
   （issue 原文、已批准 plan、最终 summary、verify 输出、MR url）落一篇
   `~/get/get-dev/wiki/issues/<repo>/!<iid>.md` 桩条目 + `wiki/log.md` 追加一行，
   然后 commit+push get-dev 仓（pull --rebase，冲突跳过下次再试）。get agent 因此
   **不需要任何 skill**：读靠 KNOWLEDGE/ 复制，写靠 worker。深度提炼/lint/自维护
   仍是二期。
8. 失败路径：push/MR 开失败时任务标 failed 并微信说明（本地分支保留人工处置），
   不自动重试开 MR。

### P5 · prompt 草稿（`cijian_agent/ai/prompts/`）

frontmatter 与现有 `dev-plan.md`/`dev.md` 的权限框架一致，三处差异：

1. shell 白名单**收紧 + 追加**（原因见 P9）：
   - **删掉**通配读命令 `cat *`、`head *`、`tail *`、`sed -n *`、`rg *`、`find *`——看文件
     一律走 opencode 原生 read/glob/grep 工具（受 `external_directory deny` 硬约束，shell 不受其约束）；
   - **追加**构建类：`python3 -m *`、`make *`、`mvn *`、`node --check *`、`flake8 *`、
     `ruff *`；`python3 -c *` 明确 deny（防内联脚本任意读文件）；
   - 禁区 deny 列表原样保留，含 `*curl*`/`*ssh*`/`git commit`/`git push`。
2. `dev-get.md` 的 `steps` 放宽到 60。
3. 两个 profile 的正文不提及 cijian 家庭系统的任何路径与概念。

**`dev-plan-get.md` 正文**（替换现有正文）：

```markdown
你是 get 产品线（GitLab group get-aico）的编码通道，现在只做方案设计：GitLab 上
来了一个 issue，先读懂现状，给出一份能让对方点头的计划。

【工作区】
- 当前目录下每个子目录是一个 git 仓库的独立 worktree（分支已建好）。
- KNOWLEDGE/ 是这个产品线的工程知识库：先读 KNOWLEDGE/index.md，再读本次涉及的
  仓库页（KNOWLEDGE/repos/<repo>.md）和 KNOWLEDGE/concepts/system-architecture.md。
- 只读这些目录，绝不读工作区之外的路径。这一阶段绝对不改文件、不装依赖、不提交。

【必须做的分析】
1. 定位需求涉及的仓库；读相关代码与 KNOWLEDGE，确认现状实现方式。
2. 跨仓影响分析（MANDATORY）：按 system-architecture.md 的影响表，判断本改动
   会波及哪些仓（例：改 model-explainer API ⇒ 查 get-ui 消费方），逐仓说明
   「要改 / 查过不用改」。
3. 找最小改动落点；两种做法差别大时选贴近现有结构、改动小的，另一种写进「要确认」。
4. 验证口径：说明这个仓改完怎么验（KNOWLEDGE/repos/<repo>.md 里有已验证命令）。
5. 不要顺手重构、升级依赖、改无关文件。

【最后一条消息的格式】
中文，20 行内，不要大段代码：
- 【目标】一句话。
- 【涉及】按仓库列：仓库名 — 关键文件/模块；每仓标注「要改」或「查过不用改」。
- 【步骤】3~6 条，按顺序。
- 【验证】打算跑的检查（按仓列）。
- 【风险/要确认】没有写「无」。
只输出这份计划，不要问「要我继续吗」，系统会拿给对方批准。
```

**`dev-get.md` 正文**：

```markdown
你是 get 产品线（GitLab group get-aico）的编码通道，负责把一份已批准的计划落成代码。

【工作区】
- 每个子目录是一个 git 仓库的独立 worktree（分支 assistant/<任务号> 已建好），
  只动这些子目录，绝不碰工作区之外的路径。
- KNOWLEDGE/ 是产品线工程知识库：动手前读 KNOWLEDGE/repos/<涉及仓>.md 与
  concepts/ 下相关页（dev-principles、release-branches）；改跨仓接口前必读
  concepts/system-architecture.md 的影响表。
- 依赖已由系统装好（get-ui 的 node_modules 已就位），不要自己 npm ci。

【硬规则】
- 永不 merge、永不 push、永不改 git 远端——提交和开 MR 由系统做。
- 遵守 KNOWLEDGE/concepts/dev-principles.md 的工程规范。
- 发现需要跨仓联动改动而计划没提：本仓先做完，把缺口写进最终回复，不要自行
  扩大战线。
- 卡在需要人选的决定上：在工作区根目录写 .cijian-ask.json
  {"question": "…", "options": ["…","…"]} 然后结束本轮，等对方点选项。

【做完后】
- 能跑的检查尽量跑（ruff / flake8 / make / npm run build / unittest 等，按仓库页
  的已验证命令）；系统还会再跑一遍正式验证环。
- 最后一条消息用中文说明：每个仓改了什么、跑过什么检查及结果、留给 MR 描述的
  影响分析一句话、假设（如有）。20 行内。
```

### P6 · 知识注入（装配进一次性 workspace）

`create_workspace` 之后、`install_agent` 之前，worker 复制：

```
~/get/get-dev/wiki/{index.md, concepts/, repos/, log.md 最近 50 行} → <workspace>/KNOWLEDGE/
```

- 全量 concepts/repos 两个目录（实测体积在 MB 级，一次性目录用完即删，成本可忽略；
  落地时 `du -sh` 复核，超 10MB 则砍 reviews/raw——本来也不复制 raw）。
- 复制而非 symlink：workspace 是临时目录，且要避免 external_directory 语义歧义。
- freshness：每次 execute 都重新复制，wiki 更新自然生效；wiki 的更新仍在 get-dev 仓
  由人（或二期 agent）维护，一期 cijian 侧只读。
- 另在 workspace 根写一个 3 行的 `AGENTS.md`：「工作区说明 + 指路 KNOWLEDGE/index.md」。

### P7 · gate 改造（`~/get/get-dev`，get-dev 仓内的唯一改动）

`agent.sh poll-gate` 的 `--wake` 分支替换：不再本地起 `opencode run`，改为

```bash
# 1) 接单评论（零 LLM，直接 REST）
gl note <pid> <iid> "🤖 **cijian assistant** — 已接手此 issue，方案稍后由家庭助手通道贴出。"
# 2) 送进 cijian
payload=$(gl poll | jq '.new_labeled_issues')   # 已有的 poll JSON 输出
curl -sS -X POST "$CIJIAN_API_URL/api/agents/dev/intake" \
  -H "X-Agent-Key: $CIJIAN_AGENT_KEY" -H 'Content-Type: application/json' \
  -d "{\"project\":\"get\",\"issues\":$payload}"
```

- `.env` 追加 `CIJIAN_API_URL=https://api.whereami.cn`、`CIJIAN_AGENT_KEY=<printer key>`。
- gate 侧幂等双保险：intake 的 source_key 去重为主，gate 的 state.json 记录照旧。
- heartbeat/launchd plist 沿用（`com.getdev.agentpoll` 每小时）；mastership 逻辑保留
  （单机无害，将来多机可用）。wake 失败进 gate.log，不重试（下小时自然重试）。
- AGENTS.md/README 加一段「本 agent 的 LLM 部分已由 cijian assistant 接管」防止误用。

### P8 · 退役与隔离

- 确认其它机器（RacheldeiMac）卸载 `com.getdev.agentpoll`（那里曾是 master）。
- get-dev 仓保留三职能：wiki 载体、verify.d 参考、gate 宿主。`agent.sh` 其余子命令
  （claim/worktree/finish…）保留不删（无害，二期评论响应可能复用 gitlab.py 逻辑）。
- **交互式 wiki 维护**走项目级 skill：`~/get/get-dev/.opencode/skill/llmwiki/`（查/记/lint/
  P4.7 桩条目整备；随 get-dev 仓提交）。只在交互会话生效，不进自动通道的一次性 workspace
  （P9 隔离不变）。

### P9 · 隔离边界（公司 ↔ 家庭，双向）

**被动注入面 = 零**（get agent 被动看到的 cijian 内容）：

| 来源 | 实际情况 |
|---|---|
| 技能（含 llmwiki skill） | workspace 无 `.opencode/skill/`；`isolate_config` 把全局 `~/.config/opencode` 指到 workspace 内空目录 → 不可见 |
| 家庭能力（31 个 MCP 工具） | `run_dev` 不挂能力 MCP、不带任何家庭令牌 |
| 家庭记忆（preferences/facts/notes） | 只注入 assistant-chat 的持久 home，编码通道不注入 |
| llmwiki / family wiki / cijian docs | 不挂进 workspace；P6 只复制 get-dev 的 wiki |
| 环境变量 | `SAFE_ENV_KEYS` 白名单剥掉一切 `CIJIAN_*` |
| 会话延续 | `--standalone` 冷启新会话 |

反向同理：get 的代码/wiki 只活在一次性 workspace（用完即删）与任务文本里；
`collect_commits` 按项目过滤（P4.6）。

**「不给看」≠「主动偷看也看不到」**：`external_directory deny` 只约束原生 read/edit/glob/grep
工具，**管不到 shell**——白名单里若保留 `cat *` 这类通配读命令，模型可以读这台机器上用户可读
的任何文件（含 `~/work/cijian`、family wiki checkout、agent.env 密钥文件）。这不是 get 特有
（现有 cijian dev 通道同样存在），但接管把它升级为公司/家庭双向边界，加硬措施：

1. **白名单收紧**（P5 第 1 条）：看文件只走原生工具；shell 只留收窄后的构建命令。
2. **bash 沙箱（落地核对项）**：核实 opencode 的 bash sandbox（macOS Seatbelt / Linux
   bubblewrap）能否在 workspace 级 opencode.json 配 workspace-only 读写——可用则
   `make`/`mvn` 这类本身能读任意文件的构建命令也出不去，内核级硬边界。
3. **密钥最小化**：agent.env 权限 600；`CIJIAN_GITLAB_TOKEN` 只进 worker 进程内存
   （config 启动时读入），不落 workspace、不进子进程 env。

## 4. 配置与变更汇总

| 位置 | 变更 |
|---|---|
| cijian-api DB | `dev_tasks.source_key` 列 + 唯一部分索引（P2） |
| cijian-api 路由 | `POST /api/agents/dev/intake`（requireAgent） |
| cijian-agent `config.py` | `gitlab_url/group/token`、`ai_dev_report_projects`、`ai_dev_verify_timeout` |
| cijian-agent `agent.env` | `CIJIAN_GITLAB_TOKEN` 等三键 |
| cijian-agent `devwork.py` | project 扩展字段解析、verify 查找顺序、setup 动作 |
| cijian-agent `worker.py` | 按项目选 prompt/model、知识装配、commit→push→MR、commits 上报过滤 |
| cijian-agent `gitlab.py` | 新文件（移植） |
| cijian-agent `prompts/` | `dev-plan-get.md`、`dev-get.md` 新增 |
| `~/.config/cijian/repos.json` | 加 `get` project（P1 全文） |
| `~/get/get-dev` | gate wake 分支、.env 两键、AGENTS/README 注记 |

## 5. 实施步骤（每步独立可验证）

1. **api**：迁移 + intake 端点 + 单测（dedupe/默认 requester/校验）→ `npm run typecheck && npm test`。
2. **agent-verify**：repos.json 扩展解析 + verify/setup → 单测（临时 fixture 仓）→ `python3 -m unittest discover -s tests` + `ruff check`。
3. **agent-gitlab**：gitlab.py 移植 + push/MR 单测（mock HTTP）。
4. **agent-worker/prompts/知识装配**：两份 prompt、worker 改造、`collect_commits` 过滤 → 全量单测。
5. **gate**：get-dev 仓 wake 分支改造 + 本机 `launchctl bootstrap` 装载。
6. **E2E 演练**：get-ui 开测试 issue（打 agent-take）→ 手动 `agent.sh poll-gate --wake`
   → 走完 链路图 全程 → CI 绿 → 关 issue 归档；llmwiki 沉淀。

## 6. 一期验收（DoD）

- [ ] 测试 issue → 1 小时内（或手动 wake）企微收到方案，含跨仓影响分析
- [ ] 回「批准」→ 实现 + 验证环输出现在微信汇报里
- [ ] 回「提交」→ GitLab 出现 draft MR：目标分支正确（get-ui=main）、描述含 Closes #iid/影响/验证
- [ ] get-ui MR 的 CI pipeline 绿
- [ ] 同一 issue 重发 intake → skipped（幂等）
- [ ] cijian 项目回归：随便提一个 cijian 需求全链路不变（prompt/verify/local-only 提交语义）
- [ ] get 提交标题不出现在 dev_commits 日报
- [ ] `grep -r GITLAB_TOKEN` 在 agent 日志/子进程 env 里零命中
- [ ] 隔离验证：测试 issue 里诱导读 `~/work/cijian` 与 agent.env——read 工具被
      `external_directory` 挡、shell 无通配读命令可用（P9）
- [ ] 提交后 `~/get/get-dev/wiki/issues/get-ui/!<iid>.md` 出现桩条目且已推送（P4.7）

## 7. 风险与回退

| 风险 | 缓解 |
|---|---|
| GitLab API 走 HTTP 明文，token 暴露面 | 内网既定现状；日志/子进程双禁；泄露只需吊销 group token |
| 免费 flash 模型啃不动 Ray/Java 仓 | DoD 用 get-ui（React，最轻）验证；`model` 字段留口，随时切付费档 |
| 验证环超时（make/编译慢） | `verify_timeout` 可配（默认 600s）；get-quick-model 明确 informational |
| gate 机器睡眠错过小时点 | 现状 get-dev 同样问题；必要时二期换服务器侧 cron |
| 双 agent 误并存 | P8 退役清单 + get-dev AGENTS/README 注记 |
| shell 白名单是软边界（通配读命令可读用户可读文件） | P9：白名单收紧 + 核对 opencode bash sandbox（Seatbelt） |
| wiki 复制进 workspace 的信息过时 | 每任务现复制；wiki 维护流程不变（人/二期） |
| 回退 | 卸 launchd 或 intake 404 即静默停摆，get 侧零损害；cijian 侧改动全部 project-gated |

## 8. 二期展望（不在本期）

MR 评论响应闭环（mr-notes + 必答后才能领新活）、CI 红 pipeline 自动修复、post-merge
followup 分支、方案/结果回贴 GitLab issue 评论、按项目付费模型档、多 host、
直接提交仓语义、wiki 深度自维护（桩条目已在一期 P4.7，二期做 distill/review/lint
与 MR 评论 ingest）。
