# 打印闭环：状态机、租约、防重打

> 2026-10-21 · 类别：howto · 仓库：cijian-api / cijian-agent · 状态：现行

## 状态机

```
queued → claimed → printing → done
   ▲        │(租约超时/失败且attempts<3 → 回 queued，30s 退避租约)
   │        ▼
   └──── failed(attempts≥3)      expired(文件24h过期且未开印)
```

## 关键机制（改动前必读）

1. **租约即退避**：`claim` 只领 `lease IS NULL OR lease <= now` 的任务。失败回 queued 时把
   lease 设为 now+30s —— 退避与"领取占用"复用同一字段。测试里模拟时间流逝 = 直接 UPDATE lease。
2. **attempts 在 claim 时 +1**，上限 3。sweeper 把 `queued AND attempts>=3` 置 failed。
3. **防重打**：agent 本地 `state.json` 记 `{current_job, phase, cups_job}`。重启恢复规则：
   - phase=submitted 且 CUPS 队列里还有 → **只等待，不重新提交**
   - phase≠submitted 且租约仍有效 → 重新走完整流程
   - 租约过期 → 清状态，服务端重派（服务端 attempts<3 才重派）
4. **上报 409 的含义**：租约过期或任务被重派 → agent 必须放弃本地副本。process() 里
   report('printing') 返回 False 时必须中止（不确认租约不打印）。
5. **CUPS 结果判定**：`lp` 非零退出 = 提交失败；任务离开 not-completed 队列 = 视为完成
   （CUPS 失败任务同样移出队列且历史保留因机而异，明细不强校验）。

## 排障速查

- 任务卡 `claimed`：agent 死了。等租约过期被 sweeper 重派，或手动
  `UPDATE print_jobs SET status='queued', lease_expires_at=NULL WHERE id=...`（等效 sweeper）
- 任务卡 `queued` 且 attempts≥3：sweeper 10 分钟内会置 failed
- 打印机显示离线：agent 心跳 30s 一次，60s 无心跳判离线 → 看 `launchctl list | grep cijian`
  与 `~/Library/Logs/cijian-agent.err.log`
