#!/usr/bin/env bash
# survey-writing / survey-ops 双卷 skill 一键部署（macOS / Linux）
#
# 用法:
#   bash install.sh                           # 装到 ~/.claude/skills（用户级）
#   bash install.sh ~/my_survey               # 装到项目级，并建项目骨架
#   bash install.sh ~/my_survey --auto-install  # 缺 Python/pandoc/curl 时尝试自动安装
#   bash install.sh ~/my_survey --no-doctor     # 装完不跑环境体检
#
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT=""
AUTO_INSTALL=0
NO_DOCTOR=0
SKIP_SKELETON=0

usage() {
    sed -n '2,9p' "$0" | sed 's/^# \{0,1\}//'
}

for arg in "$@"; do
    case "$arg" in
        --auto-install) AUTO_INSTALL=1 ;;
        --no-doctor)    NO_DOCTOR=1 ;;
        --skip-skeleton) SKIP_SKELETON=1 ;;
        -h|--help)      usage; exit 0 ;;
        -*)             echo "未知选项：$arg" >&2; exit 1 ;;
        *)              ROOT="$arg" ;;
    esac
done

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

# 把体检脚本和密钥说明也放一份到 .claude/，方便装完以后随时用
SETUP_DIR="$(dirname "$BASE")"
if [ -f "$HERE/tools/doctor.py" ]; then
    cp "$HERE/tools/doctor.py" "$SETUP_DIR/doctor.py"
    chmod +x "$SETUP_DIR/doctor.py" 2>/dev/null || true
    echo "  [ok] 环境体检脚本 -> $SETUP_DIR/doctor.py"
fi
if [ -f "$HERE/KEY_SETUP.md" ]; then
    cp "$HERE/KEY_SETUP.md" "$SETUP_DIR/KEY_SETUP.md"
fi
echo

# ---- 项目骨架 ----
# 若目标目录就是本仓库自身（用户照 README 在 clone 里直接跑），不建骨架，免得弄脏干净的 clone
if [ "$SKIP_SKELETON" = "0" ] && [ "$(cd "$SKEL" && pwd -P)" = "$(cd "$HERE" && pwd -P)" ]; then
    echo "  [跳过骨架] 当前目录是本仓库自身，不在这里建 manuscript/pdfs 等目录。"
    echo "             到你的项目目录里跑：bash install.sh <项目目录>"
    echo
    SKIP_SKELETON=1
fi

if [ "$SKIP_SKELETON" = "0" ]; then
    echo "项目骨架 -> $SKEL"
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
fi

# ---- 依赖检测与自动安装 ----
detect_python() {
    if command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
        echo python3
        return 0
    fi
    if command -v python >/dev/null 2>&1 && python -c "" >/dev/null 2>&1; then
        echo python
        return 0
    fi
    return 1
}

install_pkg() {
    local pkg="$1"
    if command -v brew >/dev/null 2>&1; then
        echo "  尝试：brew install $pkg"
        brew install "$pkg"
        return $?
    fi
    if command -v apt-get >/dev/null 2>&1; then
        echo "  尝试：sudo apt-get install -y $pkg"
        sudo -n apt-get install -y "$pkg"
        return $?
    fi
    if command -v dnf >/dev/null 2>&1; then
        echo "  尝试：sudo dnf install -y $pkg"
        sudo -n dnf install -y "$pkg"
        return $?
    fi
    if command -v pacman >/dev/null 2>&1; then
        local p="$pkg"
        [ "$pkg" = "pandoc" ] && p="pandoc-cli"
        echo "  尝试：sudo pacman -S --noconfirm $p"
        sudo -n pacman -S --noconfirm "$p"
        return $?
    fi
    if command -v zypper >/dev/null 2>&1; then
        echo "  尝试：sudo zypper --non-interactive install $pkg"
        sudo -n zypper --non-interactive install "$pkg"
        return $?
    fi
    if command -v apk >/dev/null 2>&1; then
        echo "  尝试：sudo apk add $pkg"
        sudo -n apk add "$pkg"
        return $?
    fi
    echo "  [!] 没找到可用的包管理器，请手动安装 $pkg"
    return 1
}

echo "依赖检查"
PY="$(detect_python || true)"
if [ -n "$PY" ]; then
    echo "  [ok] $("$PY" --version 2>&1)"
else
    echo "  [X] python 未安装 —— 核验脚本无法运行"
    if [ "$AUTO_INSTALL" = "1" ]; then
        echo "  正在尝试自动安装 Python..."
        install_pkg python3 || install_pkg python || true
        hash -r 2>/dev/null || true
        PY="$(detect_python || true)"
        if [ -n "$PY" ]; then
            echo "  [ok] 已安装：$("$PY" --version 2>&1)"
        else
            echo "  [!] 自动安装没成功。请手动安装：https://www.python.org/downloads/"
        fi
    else
        echo "  可加 --auto-install 让脚本尝试自动安装，或手动安装：https://www.python.org/downloads/"
    fi
fi

if command -v pandoc >/dev/null 2>&1; then
    echo "  [ok] $(pandoc --version 2>&1 | head -1)"
else
    echo "  [!] pandoc 未安装 —— tools/convert.cmd (docx→md) 不可用，非必需"
    if [ "$AUTO_INSTALL" = "1" ]; then
        install_pkg pandoc || true
        hash -r 2>/dev/null || true
    fi
fi

if command -v curl >/dev/null 2>&1; then
    echo "  [ok] curl"
else
    echo "  [!] curl 未安装 —— arxiv_curl.py 兜底不可用，非必需"
    if [ "$AUTO_INSTALL" = "1" ]; then
        install_pkg curl || true
        hash -r 2>/dev/null || true
    fi
fi
echo

# ---- 没跑体检时，给一个简单的密钥有无提示 ----
if [ "$NO_DOCTOR" = "1" ] || [ -z "$PY" ]; then
    echo "密钥（只报有无，不显示值）"
    UNSET=""
    for v in AMINER_API_KEY ZOTERO_USER_ID ZOTERO_API_KEY; do
        if [ -n "${!v:-}" ]; then
            echo "  [已设] $v"
        else
            echo "  [未设] $v"
            UNSET="$UNSET $v"
        fi
    done
    if [ -n "$UNSET" ]; then
        echo "  未设置的是可选项；对应脚本会报错退出，其余功能不受影响。"
        echo "  配置方法见 KEY_SETUP.md，或装好后运行：$PY \"$SETUP_DIR/doctor.py\" --configure"
    fi
    echo
fi

# ---- 环境体检 ----
DOCTOR="$HERE/tools/doctor.py"
if [ -f "$SETUP_DIR/doctor.py" ]; then
    DOCTOR="$SETUP_DIR/doctor.py"
fi
if [ "$NO_DOCTOR" = "0" ] && [ -n "$PY" ] && [ -f "$DOCTOR" ]; then
    echo "== 环境体检 =="
    if [ -n "$ROOT" ]; then
        "$PY" "$DOCTOR" --project-root "$ROOT" || true
    else
        "$PY" "$DOCTOR" || true
    fi
    echo
fi

echo "== 完成 =="
echo "  写作卷条文：$BASE/survey-writing/SKILL.md"
echo "  体系卷条文：$BASE/survey-ops/SKILL.md"
echo "  交接契约：  $BASE/_shared/handoff.md"
echo "  使用说明：  仓库根目录 README.md"
if [ -n "$PY" ]; then
    echo ""
    if [ -n "$ROOT" ]; then
        echo "  随时体检：  $PY \"$SETUP_DIR/doctor.py\" --project-root \"$ROOT\""
    else
        echo "  随时体检：  $PY \"$SETUP_DIR/doctor.py\""
    fi
    echo "  配置密钥：  $PY \"$SETUP_DIR/doctor.py\" --configure"
fi
echo
