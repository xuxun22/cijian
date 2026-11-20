# gotcha：openDb 里 `migrate()` 先跑，种子用它后面才补的列 → 生产 crash loop

> 2026-11-20 · 仓库：cijian-api · 类别：gotcha · 状态：现行

## 症状

上线「打卡分孩子」后 `app-api-1` 一直 `Restarting`，日志：

```
Error: no such column: child
    at migrate (file:///app/dist/db.js:469:8)
    at openDb (file:///app/dist/db.js:13:5)
    at createApp (file:///app/dist/app.js:40:5)
```

本地全绿（134 测试 + typecheck + build），因为测试每次建**全新库**：`CREATE TABLE IF NOT EXISTS checkin_projects` 里已带 `child`，根本走不到老库路径。

## 根因

`src/db.ts` 的结构是：

```ts
export function openDb(dataDir: string): DB {
  const db = new DatabaseSync(...);
  migrate(db);                       // ← 建表 + 幂等种子都在这里
  try { db.exec("ALTER TABLE printers ..."); } catch {}   // ← 列迁移在 migrate 之后
  ...
}

function migrate(db: DB): void { ... CREATE TABLE ... INSERT OR IGNORE 种子 ... }
```

新列的 `ALTER TABLE` 按现有习惯写在 `openDb()` 里、`migrate()` **之后**；而依赖该列的种子/回填写在 `migrate()` 里 → 老库启动时种子先跑，列还不存在，`no such column` 直接崩，容器无限重启。

## 解法

依赖新列的种子，其 `ALTER` 必须是 `migrate()` 的**第一条语句**（在 `CREATE TABLE` / 种子之前）：

```ts
function migrate(db: DB): void {
  // 新库此时表还不存在，ALTER 失败无妨；CREATE TABLE 自带该列
  try { db.exec("ALTER TABLE checkin_projects ADD COLUMN child TEXT NOT NULL DEFAULT ''"); } catch {}
  ...
}
```

`openDb()` 里那份重复的 ALTER 删掉，避免两个位置各说各话。

## 验证（必须用「老库」）

```bash
# 手工建一张没有新列的老表 → 用 dist/db.js 的 openDb 打开 → 种子应自动补列并回填
node -e "...CREATE TABLE checkin_projects (旧结构)..."
node --input-type=module -e "import {openDb} from './dist/db.js'; console.log(openDb('/tmp/olddb').prepare('select id,name,child from checkin_projects').all())"
```

只跑单测不够——测试库永远是全新的。

## 热修上线

服务器 timer 每 5 分钟才拉；crash loop 时别等，手动 `sudo systemctl start cijian-deploy.service`，然后
`docker ps` 看 `(healthy)`，`docker exec app-api-1 node ...` 查库确认回填。
