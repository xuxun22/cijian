# gotcha：better-sqlite3 在新 Node 上编译失败 → 迁移 node:sqlite 三连坑

> 2026-10-21 · 仓库：cijian-api · 类别：gotcha · 状态：现行

## 症状与演进

1. `npm install`：better-sqlite3 在 Node 26 无预编译产物 → node-gyp 源码编译失败
2. 换 `node:sqlite` 后 vitest 报 `Failed to load url sqlite`（Vite 5 内置模块清单无 sqlite）
3. tsc 报 `unknown 不能赋给 SQLInputValue`（node:sqlite 类型比 better-sqlite3 严）

## 解法（三步全做才能绿）

1. **换 driver**：`import { DatabaseSync } from 'node:sqlite'`（Node 22.13+/24+ 免 flag）。
   没有 `db.transaction()` 糖 → 写 `tx(db, fn)` 助手（BEGIN/COMMIT/ROLLBACK）。
   Docker 基础镜像升 `node:24-bookworm-slim`（零原生依赖后甚至不需要 build tools）。
2. **vitest 配置**：`test.server.deps.external: [/^node:/]` + `ssr.external: ['node:sqlite']`，
   并升 vitest ^3（其 Vite 6 用 `isBuiltin` 识别新内置模块；vitest 2 的 Vite 5 配置不生效）。
3. **类型**：`StatementSync.run/get/all` 参数是 `SQLInputValue`（null|number|bigint|string|Uint8Array），
   查询结果的字段是 `unknown` → 传参前 `String(row.id)` 显式转换。

## 预防

- 新项目优先用 `node:sqlite`：零原生依赖 = 本地/CI/Docker 三处零编译问题
- `npm run build`（tsc --noEmit）必须过才准提交；仅凭 `dist/` 有产物判断通过是不可靠的
  （tsc 默认有错也 emit）
