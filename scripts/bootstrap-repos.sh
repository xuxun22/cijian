#!/usr/bin/env bash
# cijian · 代码仓引导脚本
#
# 依据 repos.yaml 在 GitHub 个人账号下创建代码仓，推送 scaffold/ 骨架，
# 并把暂存的业务代码（repos.yaml 的 source 字段）并入对应仓库。
# 已存在且非空的远端仓库会被跳过（防覆盖），可重复执行。
#
# 用法：
#   ./scripts/bootstrap-repos.sh            # 处理 repos.yaml 中全部仓库
#   ./scripts/bootstrap-repos.sh cijian-api # 只处理指定仓库
set -euo pipefail
cd "$(dirname "$0")/.."

say()  { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
skip() { printf '\033[1;33m  - 跳过\033[0m %s\n' "$*"; }

# ---------- 前置检查 ----------
command -v gh    >/dev/null || { echo "错误：需要 GitHub CLI（gh）"; exit 1; }
command -v rsync >/dev/null || { echo "错误：需要 rsync"; exit 1; }
gh auth status >/dev/null 2>&1 || { echo "错误：gh 未登录，请先执行：gh auth login"; exit 1; }

OWNER=$(awk '/^owner:/ {print $2}' repos.yaml)
ALL_REPOS=$(awk '/^  - name: / {print $3}' repos.yaml)
[ -n "$ALL_REPOS" ] || { echo "错误：repos.yaml 未解析到任何仓库"; exit 1; }

# field <repo> <field>：从 repos.yaml 取字段值（固定四格缩进格式）
field() {
  awk -v repo="$1" -v key="$2" '
    /^  - name: / { cur = $3 }
    cur == repo && $0 ~ "^    " key ":" {
      sub("^    " key ": *", ""); gsub(/^"|"$/, ""); print; exit
    }' repos.yaml
}

TARGETS=${*:-$ALL_REPOS}
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

for NAME in $TARGETS; do
  echo "$ALL_REPOS" | grep -qx "$NAME" \
    || { echo "错误：repos.yaml 中没有仓库 $NAME"; exit 1; }

  VIS=$(field "$NAME" visibility); VIS=${VIS:-private}
  DESC=$(field "$NAME" description)
  SRC=$(field "$NAME" source)
  FULL="$OWNER/$NAME"
  say "$FULL（$VIS）"

  # 1. 建仓（已存在则跳过）
  if gh repo view "$FULL" >/dev/null 2>&1; then
    skip "远端已存在，不重复创建"
  else
    ARGS=(--"$VIS")
    [ -n "$DESC" ] && ARGS+=(--description "$DESC")
    gh repo create "$FULL" "${ARGS[@]}"
    say "已创建"
  fi

  # 2. 克隆；非空仓库拒绝覆盖
  CLONE="$WORK/$NAME"
  rm -rf "$CLONE"
  gh repo clone "$FULL" "$CLONE" -- --quiet 2>/dev/null \
    || git clone --quiet "https://github.com/$FULL.git" "$CLONE"

  if [ -n "$(ls -A "$CLONE" | grep -v '^\.git$' || true)" ]; then
    skip "远端已有内容，拒绝覆盖（如需重建请手动处理）"
    continue
  fi

  # 3. 先铺 scaffold 骨架，再并入暂存业务代码（source 覆盖同名骨架文件）
  [ -d "scaffold/$NAME" ] && rsync -a "scaffold/$NAME/" "$CLONE/"
  if [ -n "$SRC" ] && [ -d "$SRC" ]; then
    rsync -a "$SRC/" "$CLONE/"
    say "已并入业务代码：$SRC"
  fi

  # 4. 提交并推送
  git -C "$CLONE" add -A
  git -C "$CLONE" \
      -c user.name="$(git config user.name || echo cijian)" \
      -c user.email="$(git config user.email || echo cijian@whereami.cn)" \
    commit --quiet -m "chore: bootstrap from cijian 文档仓（scaffold + 初始内容）"
  git -C "$CLONE" branch -M main
  git -C "$CLONE" push --quiet -u origin main
  say "已推送：https://github.com/$FULL"
done

cat <<'EOF'

✅ bootstrap 完成。下一步（详见 docs/07-deploy-cicd.md）：
  1. cijian-site  → https://vercel.com/new 导入该仓；
                    环境变量 PUBLIC_API_BASE = https://api.whereami.cn
  2. cijian-api   → 仓库 Secrets：DEPLOY_HOST / DEPLOY_USER / DEPLOY_SSH_KEY；
                    Variables：DEPLOY_ENABLED = true
  3. cijian-agent → 无需配置；M3 交付 install.sh 后各地点服务器安装
EOF
