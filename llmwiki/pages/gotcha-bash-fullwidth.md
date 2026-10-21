# gotcha：bash `$VAR` 紧邻全角字符 → unbound variable

> 2026-10-21 · 仓库：cijian（bootstrap 脚本）/ cijian-agent（install.sh）· 类别：gotcha · 状态：现行
> 本项目已中招两次，均发生在中文 echo 文案里。

## 症状

```bash
say "$FULL（$VIS）"
# ./script.sh: line N: FULL�: unbound variable
```

`set -u` 下报一个带乱码的未绑定变量名。

## 根因

bash 在非 UTF-8 locale 解析时，把 `$FULL` 后面的全角括号 `（`（UTF-8 首字节 0xEF）
当作变量名的合法字节一起展开 → 变量名变成 `FULL\xef` → unbound。
`$VIS）`、`$LABEL）。` 同理。

## 解法

```bash
say "${FULL}（${VIS}）"      # 花括号显式定界
# 批量修复（找出所有 $VAR 紧邻全角字符的行）：
perl -ne 'print "$.: $_" if /\$[A-Za-z_]\w*[^\x00-\x7f\s"}\')=,.:;\/\]\[]/' script.sh
```

## 预防

- 写含中文文案的 bash：变量一律 `${VAR}` 花括号包裹
- 提交前跑一次 `bash -n`（只查语法，查不出这个！）——所以本条要靠 code review / grep 自查
- llmwiki：本条目就是防再犯的机制
