# gotcha：compose 对 env 文件做 `$` 插值，argon2 hash 被吃掉

> 2026-10-21 · 仓库：cijian-api · 类别：gotcha · 状态：现行

## 症状

部署后登录始终 401。容器内 `env` 显示 hash 变成了
`=19=19456,t=2,p=1/bxpPTgg$80w859s…`——`$argon2id`、`$v`、`$m`、`$WXfP3IOavNzRPW` 全部消失。
同时 `docker compose` 每次 warn：`The "argon2id" variable is not set. Defaulting to a blank string.`

## 根因

Docker Compose v2 会**对 env 文件值做变量插值**：`$argon2id`、`$v=19`、`$m=19456`、`$WXfP…`
都被当作 compose 变量替换成了空串。变量名不能以数字开头，所以 `$80w859s…` 幸存——
正是这种"部分幸存"让 hash 静默损坏而不报错。

## 解法

env 文件里每个 `$` 写成 `$$`（插值后还原为单 `$`）：

```bash
sed 's/\$/\$\$/g' .env > cijian.env
```

## 预防

- 凡是 compose `env_file` 引用的文件，含 `$` 的值一律 `$$`；本仓示例文件 cijian.env.example 已注明
- 部署后自检：`docker compose exec api env | grep CIJIAN_PASSPHRASE_HASH | grep -c '\$argon2id'` 应为 1
- 相关：arghash 里 `$` 分隔字段（`$argon2id$v=19$m=…$salt$hash`），是这类事故的高发载体
