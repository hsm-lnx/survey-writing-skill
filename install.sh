#!/usr/bin/env bash
# survey-writing / survey-ops 双卷 skill 一键部署（macOS / Linux）
# 用法: bash install.sh [项目目录]
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="${1:-}"

echo
echo "== survey-writing / survey-ops 部署 =="
echo

if [ -n "$ROOT" ]; then
    BASE="$ROOT/.claude/skills"
    SCOPE="项目级 ($ROOT)"
    SKEL="$ROOT"
else
    BASE="$HOME/.claude/skills"
    SCOPE="用户级 ($HOME)"
    SKEL="$PWD"
fi

SRC="$HERE/skills"
if [ ! -d "$SRC" ]; then
    echo "错误：找不到 skills/ —— 请在仓库根目录运行本脚本" >&2
    exit 1
fi

mkdir -p "$BASE"
for u in survey-writing survey-ops _shared; do
    if [ ! -d "$SRC/$u" ]; then
        echo "  [跳过] skills/$u 不存在"
        continue
    fi
    cp -R "$SRC/$u" "$BASE/"
    echo "  [ok] $BASE/$u"
done
echo "     作用域   $SCOPE"
echo

# ---- 项目骨架 ----
for d in manuscript pdfs bib docs reports reports/_raw; do
    if [ -d "$SKEL/$d" ]; then
        echo "  [存在] $d"
    else
        mkdir -p "$SKEL/$d"
        echo "  [新建] $d"
    fi
done

if [ ! -f "$SKEL/bib/verified.md" ]; then
    cat > "$SKEL/bib/verified.md" <<'EOF'
# 文献台账

只增不改、编号顺延。新增条目先走 survey-ops §7 验证，再入账。

| 编号 | 著录 | 依据等级 | 备注 |
|------|------|----------|------|
EOF
    echo "  [新建] bib/verified.md"
fi

if [ ! -f "$SKEL/docs/progress.md" ]; then
    cat > "$SKEL/docs/progress.md" <<'EOF'
# 进度板

| 日期 | 范围 | 产物 | 遗留 |
|---|---|---|---|
EOF
    echo "  [新建] docs/progress.md"
fi
echo

# ---- 依赖 ----
echo "依赖检查"
command -v python3 >/dev/null 2>&1 && echo "  [ok] $(python3 --version 2>&1)" || echo "  [缺] python3"
command -v pandoc  >/dev/null 2>&1 && echo "  [ok] $(pandoc --version 2>&1 | head -1)" || echo "  [缺] pandoc（非必需）"
command -v curl    >/dev/null 2>&1 && echo "  [ok] curl" || echo "  [缺] curl（非必需）"
echo

# ---- 环境变量（只报有无） ----
echo "环境变量（只报有无，不显示值）"
for v in AMINER_API_KEY ZOTERO_USER_ID ZOTERO_API_KEY; do
    if [ -n "${!v:-}" ]; then
        echo "  [已设] $v"
    else
        echo "  [未设] $v"
    fi
done
echo

echo "== 完成 =="
echo "用法见 README.md；密钥填法见 KEY_SETUP.md"
echo "  写作卷条文：$BASE/survey-writing/SKILL.md"
echo "  体系卷条文：$BASE/survey-ops/SKILL.md"
echo "  交接契约：  $BASE/_shared/handoff.md"
