# ADR-003 · Agent：Python 3.10+

日期：2026-10-21 · 状态：已接受（用户选定 Python）

## 背景

地点服务器上的常驻任务执行器：轮询领任务、下载文件、调本地打印机、上报。用户有多地点异构任务系统的设想（「每台服务器注册了不一样的任务处理系统」）。

## 决策

- **Python 3.10+** 单进程守护（systemd 托管，`Restart=always`）
- HTTP：requests；打印：subprocess 调 CUPS 命令行（`lp` / `lpstat`）
- 处理器注册表：handler 以模块形式注册（首版仅 `print`），配置文件声明启用项；心跳上报能力，api 按能力派发
- 安装：venv + systemd unit，`install.sh` 一键装/升

## 备选与否决

- **Go 单二进制**：部署最省，但用户偏好 Python
- **Node**：与 api 同栈好维护，但打印生态（CUPS 调用）两者都是 subprocess，无差异

## 后果

- ✅ Python 胶水特性适合「多种任务处理器」的演进方向
- ✅ 各地点可按配置启用不同 handler，同一套 agent 代码
- ⚠️ 依赖服务器自带 python3（主流发行版默认满足）
- ⚠️ 需约束依赖面（仅 requests 级别），避免 venv 膨胀
