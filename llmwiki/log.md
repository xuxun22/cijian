# 时间线（最新在前 · 追加式，勿改写历史条目）

## [2026-11-20] feat | 每日看见 v1.6 P1 实现：shine.daily + 20:45 推送 + 反馈/跟催 + 网页档案

api：`shine.daily` 任务、`shine_dailies`/`shine_daily_feedback`、scheduler 20:45、21:30 跟催、
`GET /api/shine/daily`、agent 备料端点、微信确定性反馈。agent：`_daily`/`shine-daily-v4`、
模型失败退观察任务、wiki best-effort 落档。site：每日看见档案 + 手动记录选孩子。mp：去掉闪光 tab。
测试：api 146 / agent 122 绿，site build / mp typecheck 绿。见 [shine-ai-plane](pages/shine-ai-plane.md)。

## [2026-11-20] decision | 闪光 v2「每日看见」：微信推送、小程序去 tab、指定说话人

爸爸从未主动用小程序记闪光 → 入口从「家长输入」改为「AI 从打卡/试卷/记录生成每日卡，20:45 企微推给爸妈」。
已确认：小程序去掉闪光 tab；每天指定一位家长说；允许 praise/notice/listen/invite 四种；14 天试运行。
产品/任务/schema 草案见主仓 `docs/12-shine-plan.md §0`；本条只记决策，实现时按 §0.9 同步 04/05。

## [2026-11-20] fix | 微信对话又见「这次没想好」= z.ai 周/月额度打满，已加自动兜底模型

`zai-coding-plan/glm-5.3-flash` 报 `Weekly/Monthly Limit Exhausted`（22:50 重置），chat.reply 两次重试后仍 failed，
api 按 failed 回兜底文案。worker 现在捕获额度类错误后自动换 `ai_review_model`（deepseek/deepseek-flash）重试，
实测 1.7s 正常回复。见 [gotcha-opencode-free-quota](pages/gotcha-opencode-free-quota.md)。

## [2026-11-20] gotcha | 打卡分孩子上线即 crash loop：列迁移在 migrate() 之后

M-C7 五仓上线（cijian/api/site/mp/agent），生产 api 秒崩：`no such column: child`。
根因：`openDb()` 先 `migrate()`（建表+种子），新列 `ALTER` 却按旧习惯写在 migrate 之后 → 老库种子先跑。
解法：依赖新列的 ALTER 必须放 `migrate()` 第一条。单测全新建库，永远测不出来；必须造「老表」验证。
手动 `systemctl start cijian-deploy.service` 热修（不等 5 分钟后 timer），E2E 全过。
见 [gotcha-migrate-order](pages/gotcha-migrate-order.md)。

## [2026-11-18] deploy | 生产机 reimage 完成（干净系统，Hermes 清除）

备份 5.8MB（数据+env+配置+密钥，integrity ok）→ 爸爸重装 Ubuntu 24.04 并接入 Tailscale
（新 IP 100.78.101.104，公网 IP 43.173.111.191 保留）→ 重建 docker/Caddy/deploy timer/authorized_keys
→ 恢复数据与 env → `DEPLOY_HOST` secret 更新。验证：HTTPS health 200、证书签发、CI 部署 28s、
agent 心跳恢复、数据计数一致（20 提醒/2 成员/200 消息/123 任务）。Hermes 不再恢复。详见
[cijian-api-deploy](pages/cijian-api-deploy.md) §reimage 实录。

## [2026-11-18] deploy | 生产机 Hermes gateway 已停（无运行时依赖）

生产机（VM-4-9-ubuntu）的用户级 `hermes-gateway.service` 从 11-11 起常驻（连同 weixinpay/lightclaw
插件），但 `hermes cron list` 为空、无定时任务。已 `systemctl --user disable --now` 停用并取消开机自启
（Linger=yes 下会随登录自启，必须先 disable）。数据 `~/.hermes` 4.4GB 保留，待后续 reimage 再清。
验证：api 健康、cijian-deploy.timer 正常、微信对话 7.7s 完成。现行架构（api/agent/site/mp）不调用 Hermes。

## [2026-11-18] deploy | 旧服务器销毁，文档纠正为生产机 VM-4-9-ubuntu（43.173.111.191）

爸爸在腾讯云销毁旧机 vm-0-4-ubuntu（43.159.141.66 / Tailscale 100.127.52.69）。生产一直是
VM-4-9-ubuntu（43.173.111.191 / 100.94.198.50，`api.whereami.cn`），旧机残留的 Hermes gateway
（AI 日报 08:07、产业专刊周一 08:37，和现行定时任务撞车）与 cijian-api 副本随销毁一并消失。
已更新 docs/00、06、07、CADDY.md、deploy.yml 注释，以及 llmwiki overview / deployment-tencent-vm /
cijian-api-deploy / gotcha-sslip-tls / gotcha-mp-domain-check 中的旧机引用。

## [2026-11-11] gotcha | whereami.com 是第三方网站；WW_verify 验证文件挂 cijian-site/public/

需求里的 `whereami.com` 系笔误（第三方 Cloudflare 站点，仓库 grep 零命中）；我们的域名为
whereami.cn 家族。企业微信验证文件放 `cijian-site/public/` push main，Vercel ~1 分钟上线，
裸域/www 双 200。见 pages/gotcha-whereami-com.md。

## [2026-11-05] experienced | M-C3：练习打卡网页端上线（/tools/checkin）

今日完成情况 / 待认领投递（预览→挂项目）/ 补字段 / 改派 / 项目管理（新建/编辑/启停）全在
一个纯客户端页；口令与打印工作台共用 localStorage JWT；签名 URL 直接喂 `<video>/<audio>`。
站点由 Vercel 自动发布（GitHub Actions 只做 build 校验）。另修 `[hidden]` 优先级问题。
见 pages/checkin-pipeline.md。

## [2026-11-05] experienced | M-C2：checkin 投递即打卡 agent 管线落地（v0.3.0）

能力线程扫描 AirDrop 投递 → ffprobe → whisper.cpp 分类 → 上报 → 归档/暂存 → 预览转码上云 →
sync 差量收敛。真机 E2E 全过（朗读音频/视频→阅读、器乐→二胡、改派/补字段两段式改名、Range 播放）。
两个关键坑：① whisper.cpp 1.9 的 `-oj` 没有 no_speech_prob（曾默认 1.0 → 全判器乐），
改 cjk 计数主判据；② 模型不完整时 SIGABRT 必须当「分类失败」而非「无人声」。
模型走 hf-mirror.com（HF 直连超时）。见 pages/checkin-pipeline.md。

## [2026-11-04] gotcha | 纸已打出但 CUPS 永不出队：完成事件丢失卡「打印中」

IPP 打印机打完即休眠，完成事件不回 CUPS，任务永卡 Waiting for job to complete，
agent 等 30 分钟后还会误报失败。v0.2.2 ConfirmClock：持续 300s 即 cancel 并按完成
上报（数据已全部送达）。见 pages/print-pipeline.md。

## [2026-11-04] deploy | v1.3：小程序去口令——wx.login 静默登录 + 邀请码首绑 openid

网页仍口令登录（双通道同构 JWT）；邀请码复用站点口令仅首绑校验一次；任务列表
归属标注 user_name；admin 增 users 管理。需服务器 cijian.env 配
CIJIAN_WX_APPID/SECRET（未配 wx-login 优雅 503）。契约见 docs/04、05、06。

## [2026-11-04] gotcha | wx.uploadFile 无法自定义文件名：orig_name 变 tmp_xxx

小程序上传相册/聊天文件后任务显示 tmp_xxx——UploadFileOption 没有 fileName，
multipart 文件名只能取临时路径尾段。解法：formData 传 name + 服务端清洗后优先
采用（api 343e5ae / mp c29b5ce），契约同步 docs/04。见 pages/gotcha-mp-upload-filename.md。

## [2026-11-04] gotcha | 打印机掉线三连：闪断致取消不触发、删队列误报完成、mDNS 失效按 IP 重建

任务卡「打印中」30 分钟 → CUPS 以 ~100s 周期闪断 ~10s 清零不可达计时，防补打取消
永远不触发（v0.2.1 UnreachableClock 改累计制）；排障中删队列致挂起任务消失、agent 误报
done；Bonjour 扫不到但 IP 可达，按 IP 重建队列绕过。见 pages/print-pipeline.md。

## [2026-11-04] gotcha | 小程序真机「连不上服务器」：域名未备案被微信域名校验拦截

真机输口令报连不上服务器，本地工具正常 → urlCheck:false 掩盖问题，whereami.cn
未 ICP 备案加不进白名单，请求根本没到服务器。见 pages/gotcha-mp-domain-check.md。
（同日更正：实际白名单配好即解决，直接根因是白名单未配；request/uploadFile 是两个独立列表。）

## [2026-10-24] gotcha | CORS 来源不匹配：Vercel 主域是 www

打印工作台登录全被 CORS 拦截 → 根因是 Vercel 把 www 设为主域，前端 Origin 为
`https://www.whereami.cn` 而白名单只有裸域。修复：CORS 改为正则放行 `*.whereami.cn` 家族。
同日清理了一次 compose 并发竞态留下的孤儿容器（18e7b3be9f95_app-api-1）。

## [2026-10-24] fix | 打印机「假在线」盲区：心跳携带 CUPS 硬件状态

**症状**：打印机断电后，工作台仍显示「在线」（agent 心跳正常），任务默默排队。
**根因**：心跳只报了 agent 存活，没报 CUPS 打印机硬件状态——`lpstat -p` 的
"Looking for printer." 状态消息没人采集。
**修复**：心跳携带 `printer_state`（unreachable=设备不可达），API 存 `printers.device_state`，
前端三态展示（在线 / 打印机未响应 / 离线）；打印等待期间不可达超 3 分钟 → 取消 CUPS
任务并报失败（防止来电后突然补打积压任务）。
见 [print-pipeline](pages/print-pipeline.md) §两种离线。

## [2026-10-22] mp | 微信小程序打印工作台（M-mp-1~3）

原生 TS；口令登录、相册/拍摄/聊天文件三入口上传（wx.uploadFile 原生进度）、
打印机三态、任务列表轮询 + 事件时间线、转发家庭群卡片。仓库 `cijian-mp`。
上线前置：小程序备案 + whereami.cn 域名 ICP（见 docs/09）。

## [2026-10-22] fix | CI/CD 打通：Tailscale SSH check 模式挂起 runner

deploy 挂起 12 分钟零输出 → 根因是 Tailscale 默认 SSH 策略 check 模式（新设备需浏览器确认，
runner 无法完成）。用户改 accept + 换 ephemeral auth key 后，push 即部署全链路打通
（Tailscale 接入 → SSH → git pull → compose 重建 → healthy，全程 <1 分钟）。
见 [gotcha-tailscale-ssh-check-mode](pages/gotcha-tailscale-ssh-check-mode.md)。

## [2026-10-22] howto | Harness 规则成文：每仓测试/lint/产品判定 + enforce 接线

新增 [engineering-standards](pages/engineering-standards.md)：每仓校验命令、类型与 lint 规则、
产品层判定（等待必有反馈/错误文案人话/纸墨朱砂令牌/契约先行/noindex/防重打优先）。
enforce 接线：api CI 增加 typecheck 关卡、agent CI 升级 ruff+compileall、
SKILL.md 内置「提交前检查清单」。推动因：用户要求规则可校验、可强制执行。

## [2026-10-22] fix | 任务卡「已接受」：agent 漏报 printing 致租约超时

见 [print-pipeline](pages/print-pipeline.md) §实战记录。修复：lp 提交成功即上报 printing（租约 600s），
轮询期间每 4 分钟续租；顺带照片 fit-to-page 单页打印、超时默认放宽到 30 分钟。agent v0.1.2。

## [2026-10-22] seed | llmwiki 初始化

以 Karpathy llmwiki 模式初始化本维基；回填 2026-10-18 ~ 10-22 初始部署期间的 7 条经验。

## [2026-10-21] deploy | cijian-api 首次部署到腾讯云 vm-0-4-ubuntu

Docker 29 + Compose 2.40；API 走 127.0.0.1:8787，公网入口挂 ACLI 共享 Caddy。
`https://43-159-141-66.sslip.io/api/health` 全绿。打印机 p_macmini 注册成功。

## [2026-10-21] e2e | 打印闭环端到端验证通过

登录 → 上传 autumn-walk.svg.png → 建任务 j_ae77f097634bd2d8 → agent 领取 → CUPS 出纸 → done。
事件序列 queued→claimed→claimed→done（含一次租约重派，符合设计）。

## [2026-10-21] gotcha | bash $VAR 紧邻全角括号（bootstrap 与 install.sh 各中一次）

见 [gotcha-bash-fullwidth](pages/gotcha-bash-fullwidth.md)。

## [2026-10-21] gotcha | compose env_file 的 $ 插值吃掉 argon2 hash

见 [gotcha-compose-dollar](pages/gotcha-compose-dollar.md)。

## [2026-10-21] decision | better-sqlite3 → node:sqlite

见 [gotcha-node-sqlite](pages/gotcha-node-sqlite.md) 与 ADR-002 修订。

## [2026-11-05] overview | v1.4 每日打卡 M-C1 上线：投递即打卡引擎（api 侧全量端点+13 测试）

## [2026-11-06] feat | 打卡上生产 + 小程序 M-C4

生产 agent 开启 checkin 能力（env 加 `CIJIAN_HANDLERS=print,checkin` + checkin 配置，launchd 重启）。
过程中修了 4 个真机问题：launchd 无 Homebrew PATH（plist + 代码双兜底）、`iterdir` EINTR 打断整轮
（各阶段独立容错 + 重试）、首次启用会吞历史 Downloads（加水位线 `checkin/state.json`）、
**微信 wx.request 不支持 PATCH**（api 更新端点改为同时接受 POST，小程序字段保存/项目编辑才真机可用）。
小程序新增打卡页 + 项目管理页 + tabBar 双工具入口，api 客户端支持 PATCH。
细节见 [checkin-pipeline](pages/checkin-pipeline.md)。

## [2026-11-06] e2e | 首条真实打卡视频：分类/归档正确，预览上传踩到 3 个坑

175s 二胡视频 → whisper 认出二胡练习 → 建档 → 归档 184MB 原件；预览 6.7MB 上传先后失败两次，
根因：①预览同步上传阻塞扫描 ②Node 默认 requestTimeout=300s 切断慢上传 ③agent claim 遇 SSL 超时崩进程。
均已修（后台线程+指数退避 / requestTimeout 1h / 网络异常只告警），最终 preview=ready。
API 在腾讯云美国圣克拉拉，家宽 RTT ~350ms，单流上传 3~30KB/s —— 在线播放体验的长期瓶颈。

## [2026-11-11] howto | opencode runner 集成实测（M-B0 spike：JSON 契约/agents 目录/延迟/deploy key）

## [2026-11-11] architecture | 看见闪光 AI 平面落地（M-B1~B3：API 任务队列 + agent opencode + wiki 视图 + web/mp UI）

## [2026-11-11] ops | api 迁移到 43.173.111.191（独立 Caddy + Tailscale + 数据/密钥迁移，Actions 与自拉取均切新机）

## [2026-11-15] architecture | 家庭助手架构成文（docs/15）：三层链路、26 个能力工具、六条主流程

同时沉淀 gotcha：隔离 XDG_CONFIG_HOME 后 MCP 配置没搬，能力工具全丢，模型表现为「做不到」。

## [2026-11-15] architecture | 技能自改进 + 记忆分层（遥测/台账/回滚/归档 + 回合后自动回顾）

能力工具 26→30（skill_stats/history/restore/pin），回顾任务 assistant.skill.review（纠正即时 + 每日兜底）。
同时沉淀两条 gotcha：skills 目录递归扫描、免费模型共享额度。

## [2026-11-21] feat | 生日提醒：提前 7 天 + 当天，08:00 发给爸妈（幂等）

`shine_children` 补 `birthday`（MM-DD）与出生年（布丁 2015-12-21、奶茶 2017-10-11）；
`birthday_reminders` 幂等表；每天 08:00–22:00 检查，提前 7 天/当天各一条。顺带修
`birthday` 列必须在 migrate 种子之前 ALTER 的顺序坑（补回归测试）。

## [2026-11-21] feat | 每日观察提示升级：十领域加权 70/30 + 每句配「可以聊」

重点（情绪/好奇/责任/品德）70%，财商/数字/表达/社交/生活/审美 30%；62 句池，
每句含「最近留意 + 可以聊」，按天确定性加权抽选、21 天不重复，随 20:45 卡发。

## [2026-11-21] decision | 工具箱移除「看见闪光」卡片，仅留直链

微信每日卡（今日看见）为唯一主入口；/tools/shine/ 保留为档案/补记直链，不再出现在 /tools/ 列表。
docs/12 §0.7 IA 表同步。

## [2026-11-21] feat | 口算「还没做」防谎报：answered_count + 未作答≥80% 不建错题不打卡

vision 输出 answered_count；未作答 ≥80% 视为整页/大部分没做，删临时卷、不建错题、不打卡，
回「还没做/还没做完」。真实视觉实测：空白 12 题与只写 2 题均正确拦截。试卷不受影响。

## [2026-11-21] fix | 自动分流 staging 竞态（扫描器抢先建卷）+ 双向纠错上线

首次真实口算照片暴露 `UNIQUE constraint failed: papers.id`：worker 先建目录后建行，
扫描器 reconcile 认领同一目录。改为先建行再下图，补回归测试。另补「第N题错了」
（wrong_on）与「第N题没错」双向纠错。真实口算卷复测：84 题错 8、布丁归属、
「收」后 ready + 11-21 口算打卡成功。

## [2026-11-21] feat | 错题本自动分流：照片 45s 静默识别（试卷/口算/其他），口算自动打卡

微信照片不再需要「收卷」：photo_batches 到期自动 paper.ingest；vision 分 exam/oral/other，
other 安静；「收/不收」确认/丢弃。口算确认后调 agent checkin manual 自动打「每日口算」卡并
明确回「打卡成功」（当日幂等）。合成口算卷实测：12 题准确找出 3 道错、归属奶茶。
api 152 / agent 130 测试绿。详见 pages/papers-pipeline.md。

## [2026-11-20] feat | 错题本第 3 步：微信「收卷」入口 + 预览/确认回路（api 侧）

微信照片 +「收卷」→ 15 分钟窗口合成一份卷（paper_intake 幂等）→ files 1h 中转 →
paper.ingest → 预览回微信（成功即删中转文件）→「入库/第N题没错/奶茶的」→ paper.confirm。
vision 定为 deepseek/deepseek-flash（多模态实测通过：认出奶茶/3年级/第4单元/6题错2）。
api 140 测试绿、agent 112 测试绿；待部署后走微信 E2E。

## [2026-11-20] feat | 错题本第 2 步本地引擎：vision 识别 + 自动归属 + 预览文案

`papers/ingest.py` + prompt `paper-ingest.md`：多页多图 → 严格 JSON → 归属三级
（姓名→年级唯一→问）→ status=preview + 覆盖写题 + 原图归档 originals；CLI 可单卷联调。
14 项单测，全量 110 项绿。未接微信入口/确认回路（第 3 步）。

## [2026-11-20] feat | 错题本第 1 步上线：本地库 + AirDrop 图片扫描/多页分组

`cijian_agent/papers/{store,watch}.py`，能力名 `papers`（已加入 agent.env handlers 并重启）。
children 种子（布丁 2022/奶茶 2024，9/1 自动进级）、papers.db 迁移、Downloads 图片稳定判定、
180s 多页分组、水位线 + reconcile 幂等；13 项单测，全量 96 项绿。详见 pages/papers-pipeline.md。

## [2026-11-20] decision | 错题本设计定稿（docs/17）：真相源=Mac mini，服务器仅≤7天缓存通道

三决策确认：微信发图可（短途过服务器）、PDF 走企微文件消息直发（即发即删）、外部模型 API 可。
铁律细化：判据=「随时删腾讯云不丢数据」；据此重估 checkin 预览 7 天存量=缓存合规，无需整改。

## [2026-11-20] decision | 隐私铁律确立：腾讯云服务器不存任何家庭私密信息，家庭数据长期归属 Mac mini

起因：错题本方案 v1 把试卷照片永久存服务器，被爸爸否决并立规。已建 pages/privacy-iron-law.md
（含 checkin 预览 7 天存量冲突的整改待办）。

## [2026-11-20] deploy | get 接管 E2E 全链路通过 + steps 熔断调查

get-ui#2：issue→gate handoff→intake→plan(42s)→批准→execute(70s, deepseek-flash 付费档)→verify
(npm run build 绿)→提交→Draft MR !11（Closes #2，pipeline 241 绿）→wiki 桩（护栏正确保住了人工页）。
期间修：execute 漏传 agent 名、免费额度打满（get 项目切 deepseek/deepseek-flash）、
dev/dev-get steps 60→200 + 截断收尾话术（用户微信见「本轮已达最大步数」系模型措辞，非代码）。

## [2026-11-19] howto | get 接管一期实现落地：intake 端点 / ProjectSpec / gitlab 客户端 / handoff gate

cijian-api 126 测试绿（+intake 7 项）、cijian-agent 82 绿（+14 项）、get-dev gate 改交接模式。
剩余阻塞：get-dev .env（token）不在本机、agent.env 缺 CIJIAN_GITLAB_TOKEN、launchd 未装、api 未部署。
新坑：opencode 权限后匹配者胜——窄 allow 必须排在宽 deny 之后（记入 opencode-runner）。

## [2026-11-19] overview | get 产品线接管调研：get-dev 已停摆，cijian dev 通道可接管，一期方案出台

9 仓全在自建 GitLab（SSH 可达）；cijian 侧三缺口：verify 只会 npm、无 push/MR、无 GitLab 客户端。
方案 docs/16-get-takeover-plan.md（gate→intake 桥、repos.json 扩展、双 prompt、wiki 知识装配）。

## [2026-11-16] howto | 编码通道改成「计划先行」+ 小程序开发看板

planning → waiting_plan → execute → waiting_input → done；新增 dev-plan 只读 agent、`.cijian-ask.json` 提问协议、
小程序 pages/dev/{board,detail}（仅 dad）。同时沉淀几条坑：JWT users.id 与企微 UserID 需绑定、同毫秒任务靠 rowid 排序、
AI 任务异常要补 markDevTaskFailed、能力面也要校验 dad 角色。

## [2026-11-20] gotcha+decision | dev「提交」升级为 push-main 直上（committed≠上线排障）

口算/跳绳打卡「没上线」排障：两个 dev 任务都停在本地 assistant 分支（未 push 未部署）。
落地 push-main 模式（合并 main+push+api timer/Vercel/mp CI/agent 自重启）并当天上线 M-C6
手动打卡（每日口算/跳绳 + 微信 checkin_do/undo + completion_rate）。见 pages/devflow-push-main.md。

## [2026-11-20] gotcha | 二胡 airdrop 没算打卡：AirDrop 保留拍摄 mtime/birthtime，checkin 水位线把当天投递当旧文件吞了

18:40 录的视频 20:00 才投（ctime=到达时刻），checkin 按 mtime 判「早于水位线」永久跳过；
papers 的 max(mtime,birthtime) 修法不够（birthtime 也被保留）。已修：arrival=max(三者)，
并回拨 state.json last_seen 救回当天记录（23:30 归档 2026-11-20_二胡练习_IMG_5175.mov）。
见 pages/gotcha-airdrop-mtime-watermark.md。
