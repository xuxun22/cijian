# AirDrop 保留拍摄时间，水位线误吞当天投递（checkin）

- 日期：2026-11-20 · 仓库：cijian-agent · 类别：gotcha · 状态：有效

## 症状

二胡练习视频 18:40 录制、当晚 AirDrop 到 Mac mini，打卡没生成；agent 日志每轮/每次重启都打
`早于启用水位线的旧文件，跳过（原地保留）：IMG_5175.MOV`，文件永远留在 Downloads。
（用户视角就是「投了但没算打卡」。）

## 根因

- macOS AirDrop（照片/视频）会**同时保留 mtime 和 birthtime 为拍摄时间**；
  真正的到达时刻是 **ctime**（接收完成后 rename 进 Downloads 的那一刻）。
- `checkin.py _scan()` 首见文件用 `mtime < baseline` 判「早于水位线的旧文件」→
  录制时间（18:40）早于 baseline（上一进程 last_seen − 600s ≈ 19:31）→ 永久跳过。
- `_remember_skip` 只活在进程内存里，重启重新推导；而 last_seen 每轮推进、baseline 越来越新，
  文件永远救不回——**只改判定逻辑也救不了已滞留的文件**，必须同时回拨 state.json。
- papers 管线此前修过同款（`arrival=max(mtime, birthtime)`，见 papers-pipeline.md），
  但本案证明 **birthtime 也会被保留**，那个启发式同样救不了——ctime 才是必要信号。

## 解法（2026-11-20 已修）

- `checkin.py` 增加 `_arrival(st) = max(mtime, birthtime, ctime)`，首见水位线判定改用它。
- 救已滞留文件：`launchctl unload` 停 agent → 把
  `~/.local/share/cijian-agent/checkin/state.json` 的 `last_seen` 回拨到投递时刻之前
  （当天中午即可）→ `launchctl load`。注意 papers 状态独立（`papers/scan_state.json`），互不影响；
  回拨后老文件仍被跳过（其 ctime 也旧，本案三个旧 MOV ctime=Nov 9）。
- 记录日期 = agent 上报的当地日期，救档要赶在午夜前。

## 预防

- 排障口诀：**投了没打卡 → 先 grep 文件名看有没有「早于启用水位线」**；再看
  `stat -f 'mtime=%Sm ctime=%Sc btime=%SB'` 三个时间，判断「录的时刻」vs「投的时刻」。
- ctime 可被后续 chmod/xattr 等改动推后——极端情况下老文件可能被误当新投递处理，
  代价（生成一条待指派媒体，人工忽略即可）远小于吞掉真实练习，可接受。
- 新管线做 inbox 扫描时，到达时间一律用 `max(mtime, birthtime, ctime)`，别只看 mtime。
