# dev 通道「提交」语义：push-main 直上（committed ≠ 上线的坑）

- 日期：2026-11-20 · 仓库：cijian-agent（devwork/worker）· 类别：gotcha|decision · 状态：有效

## 症状

2026-11-19 晚微信提了两个 dev 任务（加口算/跳绳打卡项），都回复「提交好了」；
第二天发现功能没上线——生产 api 没新代码、生产库没新项目。

## 根因

dev 通道旧终态是 `committed` = **本地 `assistant/dt_*` 分支提交**，仅此而已：

- 分支不 push（`git ls-remote` 里没有）、不合 main、不部署；worktree 还会被清掉
- 生产 api 的 5 分钟 timer 只拉 `origin/main` → 永远看不到分支上的提交
- 若方案靠「一次性脚本建数据」（如 seed-checkin-projects.py），脚本也不会有人跑
- 两个任务对同一需求各自实现（手动打卡 vs 媒体打卡），都停在分支上互相冲突

## 解法（2026-11-20 起）

「提交」= **合并 main + push + 走各仓部署链路**（`repos.json` 里项目 `push: "push-main"`）：

- `devwork.ship_to_main()`：每仓 `pull --ff-only` → `merge --no-ff 分支` → `push origin main`；
  单仓失败（主检出不在 main / 合并冲突 / 推送失败）保留分支不影响其他仓
- `deploy` 表配置每仓上线动作：api=服务器 timer 自动拉取、site=Vercel 自动发布、
  mp=CI 传开发版（**体验版仍要 mp 后台手动设**）、cijian-agent=`launchctl-kickstart:com.cijian.agent`
  （延时 8s 独立进程组重启，等回复先发出去）
- get 项目仍是 `gitlab-draft-mr`（推分支开草稿 MR，不直上 main）——语义按项目区分

## 预防

- 提需求后隔天验收「没上线」，先查三件事：`git ls-remote --heads origin 'assistant/*'`
  （分支推没推）、`/dev/latest` 的 status（committed 就是没上）、生产 `git log -1`
- 状态机 `committed` 的含义已从「本地提交」变为「已推送上线」（push-main 项目）；
  回复文案也改为逐仓上线说明，别再出现只有分支名的「提交好了」
- 同一需求别发两条 dev 任务：第二次会基于旧 main 另起分支，方案可能冲突，合流要人工挑
