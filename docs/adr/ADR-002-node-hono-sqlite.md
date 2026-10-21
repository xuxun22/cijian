# ADR-002 · 后端：Node 22 + Hono + SQLite

日期：2026-10-21 · 状态：已接受（用户选定 Node）

## 背景

api 是单机有状态服务：鉴权、文件收发、任务调度、TTL 清理。规模为家庭级（个位数用户、每日任务量极小）。

## 决策

- 运行时 **Node 22**（用户指定 Node）
- 框架 **Hono**：轻量、TypeScript 友好、中间件生态够用
- 存储 **SQLite**（better-sqlite3，WAL 模式）+ 本地磁盘文件，不引入独立数据库服务
- 部署：docker compose（volume 持久化 DATA_DIR），Actions SSH 触发

## 备选与否决

- **Go**：部署更省（单二进制），但用户偏好 Node 生态
- **Postgres/MySQL**：为家庭规模引入 DB 服务属过度设计
- **Serverless（Vercel Functions）**：api 有状态（SQLite+文件盘），不适用

## 后果

- ✅ 单机单文件库，备份 = `.backup` 一条命令
- ✅ better-sqlite3 同步 API，事务简单可靠
- ⚠️ better-sqlite3 含原生编译——用 docker 镜像规避服务器环境问题
- ⚠️ 单实例运行（SQLite 写锁），不可水平扩展——规模到了再换
