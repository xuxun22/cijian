# checkin 打卡管线（v1.4 每日打卡）

- 日期：2026-11-05 · 仓库：cijian-api / cijian-agent（M-C2 起）/ 文档 cijian · 类别：overview · 状态：有效

## 是什么

工具箱第二件工具：**投递即打卡**——手机录视频/录音 AirDrop 到 Mac mini，agent 扫描
→ ffprobe → whisper.cpp 分类 → 上报 api → 自动指派项目（AI > 唯一未完成 > 待指派）→
记录自动生成 → 归档两段式命名 → 预览片上云（480p/250kbps，**云端只留 7 天**）→
签名 URL 播放（HMAC 12h、免 auth 头、支持 Range）。

真相源：`docs/10-checkin-plan.md`（设计+决策记录）、`docs/04` §v1.4、`docs/05` §打卡。

## 关键事实（实现时容易忘的）

- 表：`checkin_projects / checkin_records / checkin_media`，幂等迁移在 `src/db.ts migrate()`
- 记录**只能由媒体管线/assign 生成**（无用户 POST records）；`UNIQUE(project_id, date)`，多段练习 Σ 媒体
- 记录日期 = agent 上报的当地日期；api 侧「当日」统一 `shanghaiToday()`（Asia/Shanghai）
- 预览片上传：agent 已转码的成品直传，`data/media/<yyyy-mm>/<cm_id>.mp4`，无 24h TTL，sweeper 按 7 天清
- 播放免 Authorization 头（`<video>`/`wx.video` 发不了 header）→ `/media/:token` HMAC，密钥复用 `FILE_URL_SECRET`
- min_duration 字段保留但**不参与任何判定**（2026-11-05 决策）
- CORS 已放行 PATCH（`app.ts`，records 补字段需要）
- agent 侧端点：`GET checkin/projects`（分类用项目清单）、`GET checkin/sync`（matched+待指派的
  期望归档名/当前名/预览状态，agent 差量收敛）、`POST media`、`POST media/:id/content`、`POST renames/:id/done`
- 归档名按 `_` 分段渲染：未填字段的段整体剔除（ingest = `date_project_orig`，补字段后自动出现
  `piecexcount` 段并由 sync 触发改名）——不会出现字面 `{piece}`

## agent 侧（v0.3.1，M-C2）

- 能力线程（非 claim）：`CIJIAN_HANDLERS=print,checkin`；registry 里 `BACKGROUND={"checkin"}`
- 依赖：ffmpeg/ffprobe（brew）、whisper-cli（brew whisper-cpp）、模型
  `~/.local/share/cijian-agent/models/ggml-small.bin`（487,601,967 字节，**hf-mirror.com** 下载，
  HuggingFace 直连会超时）
- 幂等：处理即移出 inbox；holding 名 `<media_id>__原名`；归档名以 api sync 为准 → 重启自愈
- 稳定判定：连续两轮大小一致 + 静置 5s；**首见且静置 >60s 直接处理**（重启积压/`--once`）
- `--once` 会补一次扫描（settle），daemon 模式不需要
- 分类：抽 3×12s → whisper-cli `-oj` → 三段合计中文字符数为主判据（≥40 人声 / ≤15 无人声 /
  中间带参考 no_speech_prob）→ 按项目 `classifier_hint` 关键词唯一匹配（`无人声|器乐|音乐|演奏` vs
  `人声|朗读|说话|背诵|跟读`），置信度 0.9；匹配不唯一/转写失败 → 放弃分类交服务端规则
- 预览片：视频 480p/250kbps（长视频按 8MB 目标自动降码率，最低 100k）、音频 AAC 64k，指派人/待指派都上传
- **预览上传是后台线程**（`_preview_queue`），慢网不阻塞扫描/改名；失败指数退避（10 分钟起，最长 6 小时），
  上传超时 30 分钟。2026-11-06 实测：API 在腾讯云**美国圣克拉拉**，家宽到它 RTT ~350ms、丢包 0~20%，
  单流上传只有 3~30KB/s —— 11MB 的 450k 预览传不上去，故降到 250k/8MB 目标；根治要迁国内或媒体走国内 CDN
- **launchd 环境没有 Homebrew PATH**：plist 的 `EnvironmentVariables` 已加 PATH，代码里
  `_tool()` 也会按 `/opt/homebrew/bin`、`/usr/local/bin` 兜底解析；启动日志直接打 ffmpeg/whisper 路径
- **水位线** `~/.local/share/cijian-agent/checkin/state.json`（last_seen）：首次启用不吞 Downloads 里
  的历史文件（早于启用水位线的首见文件原地跳过），停机期间的新投递重启后仍能补处理
- 每轮各阶段（projects/scan/sync）独立 try，网络抖动或单文件异常不会阻断整轮；
  `iterdir` 在 macOS 上偶发 `EINTR`，`_list_inbox()` 重试 3 次

## 排障入口

- 指派全进待指派 → 先查 `checkin_projects.active` 是否为 1（曾因 INSERT 占位符错位全变 0，已修）
- 预览播放 410 → 正常到期（7 天）；403 → 签名过期（12h），前端重新取 `/api/checkin/media/:id/url`
- sync 拉取为空但文件没改名 → 查 `checkin_media.archive_name` 是否已等于期望名（done 会确认）
- **全判成器乐**：whisper.cpp 1.9 的 `-oj` **没有 no_speech_prob**（只有 transcription[].text），
  曾默认 1.0 导致全判无人声——已改 cjk 计数主判据；另注意模型不完整会 SIGABRT，已按「失败→放弃分类」处理
- **全判成人声**：真实朗读片段 cjk 通常 60~150；若器乐被幻觉出长句，往 `HALLUCINATION_PATTERNS` 加词
- 分类/上传不动作 → `CIJIAN_HANDLERS` 是否含 checkin；模型路径是否存在；`launchctl` 重启后看
  `~/Library/Logs/cijian-agent.*.log`
- 文件滞留在 inbox → 是否 <60s 静置或正在拷贝（两轮稳定）；解析失败/过短的媒体
  **原地保留**并按签名记忆跳过（不搬动家人的其他文件），只有明确属于打卡的才 move
- web 端视图切换依赖 `[hidden]`：global.css 已加 `[hidden]{display:none!important}`
  （此前 `.print-login{display:grid}` 会盖掉 hidden，属打印页潜在 bug）
- 日志里 `checkin 一轮异常：[Errno 4] Interrupted system call: '…/Downloads'` → 旧版扫描阶段被信号打断
  会中断整轮（连 sync 都跳过）；v0.3.1 已改为各阶段容错 + EINTR 重试
- launchd 读 `~/Downloads` 的 TCC 权限已验证（用临时 LaunchAgent 跑同款 python：listdir/read 均 ok，
  ffmpeg/whisper-cli rc=0），排障时可复用这一招，不必投真媒体

## 小程序侧（M-C4，2026-11-06）

- `pages/checkin/checkin`：今日项目卡（已打卡/待打卡/休息日 + 14 天圆点 + 连续天数）、待认领
  （指派/忽略）、媒体行点播、字段编辑保存、改派；30s 自动刷新（播放中/字段 dirty 时跳过）、下拉刷新
- `pages/checkin/projects`：项目 CRUD（名称/内容类型/AI 提示/归档模板/练习日/启用/字段）
- `app.json` 加 tabBar：**打卡 / 打印**，`pages[0]` 变为 checkin（启动页变了）
- **微信 wx.request 不支持 PATCH**（method 枚举只有 GET/POST/PUT/DELETE/…；社区一致结论）。
  api 的两个更新端点用 `app.on(['PATCH','POST'], …)` 同时挂两种方法：网页用 PATCH，小程序用 POST。
  （此前试过 `as unknown as RequestOption['method']` 透传，真机会失败，已回退）
- 播放：视频用 `<video>` 浮层；音频用 `wx.createInnerAudioContext()`；`preview_status != ready`
  时点播放给「转码中」提示（api 返回 409）。签名 URL 走 `<video>`/音频组件，不需要配域名白名单
  （只有 request/uploadFile/downloadFile/connectSocket 需要）
- 登录与打印页共用 `wxLogin` 静默登录（首次绑邀请码）
- 发布：CI 的 upload job 已配置 `MP_UPLOAD_PRIVATE_KEY`，push main 自动上传开发版
  （日志「上传完成：v0.1.0-<sha>」）；「设为体验版」只能在 mp 后台手动点
- 若真机视频/音频播不了：先确认 mp 后台「downloadFile 合法域名」是否含 `https://api.whereami.cn`
  （组件本身不强制白名单，但加上无害；request/uploadFile 已有）

## 里程碑状态

M-C1 ✅（2026-11-05，13 项集成测试，已上线）→ M-C2 ✅（2026-11-05，真机 E2E：朗读音频/视频→阅读、
器乐→二胡；改派重命名、补字段两段式命名、预览上传、Range 播放、幂等复跑全过）→ M-C3 ✅（2026-11-05，`/tools/checkin`：今日完成/待认领/预览播放/补字段/改派/项目管理，已随站点发布）→
M-C4 ✅（2026-11-06，mp 打卡页+项目管理页+tabBar，`npm run typecheck` 绿；播放需开发者工具/真机人工点一次）→
M-C5 试运行一周（生产 agent 已于 2026-11-06 开 checkin：`CIJIAN_HANDLERS=print,checkin`，
项目「每日阅读」「二胡练习」已建好）
