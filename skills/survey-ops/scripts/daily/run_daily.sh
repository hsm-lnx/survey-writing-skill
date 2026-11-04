#!/usr/bin/env bash
# 每日调度：拉信 → 解析 → 补全 → 让 Claude 生成简报 → 归档
# macOS / Linux 用法：
#   ./run_daily.sh
#   cron: 0 9 * * * "/path/to/project/daily/run_daily.sh"
#
# 注意：本脚本不做 set -e；各步骤的退出码要按约定分辨处理。

set -u

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT" || exit 1

TODAY="$(date +%Y-%m-%d)"
LOG_DIR="$ROOT/logs"
mkdir -p "$LOG_DIR"
LOG="$LOG_DIR/$TODAY.log"

log() {
    printf '[%s] %s\n' "$(date +%H:%M:%S)" "$1" | tee -a "$LOG"
}

PY="${SURVEY_DAILY_PYTHON:-python3}"
if ! command -v "$PY" >/dev/null 2>&1; then
    PY="python"
fi
if ! command -v "$PY" >/dev/null 2>&1; then
    log "找不到 Python。设 SURVEY_DAILY_PYTHON 指向解释器，或把 python 加进 PATH。"
    exit 1
fi

run_py() {
    local script="$1"
    shift
    local out code line
    out="$("$PY" "$ROOT/$script" "$@" 2>&1)"
    code=$?
    if [ -n "$out" ]; then
        while IFS= read -r line; do log "$line"; done <<< "$out"
    fi
    return "$code"
}

log "===== 每日文献简报任务开始 ====="
log "工作目录：$ROOT"

# 1. 拉信
log "步骤 1：拉取 Alert 邮件"
run_py pull_mail.py
code=$?
if [ "$code" -ne 0 ]; then
    log "拉信失败（退出码 $code），退出，邮件保留在邮箱。"
    exit 1
fi

# 1.5 解析
log "步骤 1.5：解析 Alert 邮件为 _parsed.md"
run_py parse_alerts.py
code=$?
if [ "$code" -eq 4 ]; then
    mkdir -p "$ROOT/processed/$TODAY"
    find "$ROOT/inbox" -maxdepth 1 -name '*.eml' -exec mv {} "$ROOT/processed/$TODAY/" \;
    log "步骤 2：本轮 0 条新记录（空提醒），邮件已归档，安静退出。"
    exit 0
fi
if [ "$code" -ne 0 ]; then
    log "解析失败（退出码 $code），退出，邮件保留在 inbox/。"
    exit 1
fi

# 1.6 补全
log "步骤 1.6：Crossref / OpenAlex 补全著录与摘要"
run_py enrich_crossref.py
code=$?
if [ "$code" -eq 2 ]; then
    log "补全全部失败（网络不可用？），退回 _parsed.md 继续生成简报。"
elif [ "$code" -ne 0 ]; then
    log "补全异常（退出码 $code），退回 _parsed.md 继续生成简报。"
fi

# 2. 是否有新邮件或手工补充
shopt -s nullglob
emls=("$ROOT/inbox"/*.eml)
shopt -u nullglob
manual_file="$ROOT/manual/extra_titles.txt"
manual_lines=0
if [ -f "$manual_file" ]; then
    manual_lines="$(awk 'NF && $0 !~ /^[[:space:]]*#/' "$manual_file" | wc -l | tr -d ' ')"
fi

if [ "${#emls[@]}" -eq 0 ] && [ "$manual_lines" -eq 0 ]; then
    log "inbox/ 无新邮件、manual/ 无补充题名，按规则保持安静，不生成简报。"
    exit 0
fi
if [ "$manual_lines" -gt 0 ]; then
    log "manual/ 有 $manual_lines 条补充题名，一并处理"
fi
log "步骤 2：inbox/ 有 ${#emls[@]} 封新邮件，调 Claude 生成简报"

# 3. 调 Claude（自动读当前目录 CLAUDE.md）
if ! command -v claude >/dev/null 2>&1; then
    log "找不到 claude 命令。请确认 Claude Code 已安装并在 PATH 里。"
    exit 1
fi
prompt="按当前目录 CLAUDE.md 里的规则，优先读取 inbox/_enriched.md（缺失时依次退回 _parsed.md、.eml），逐条分诊，生成今天的中文简报到 brief/ 目录。
如果所有记录都没有新论文（已在 processed/ 历史里或已在台账中），就不要生成 brief 文件，直接结束。
生成完简报后，不要做任何其他事。"
claude_out="$(printf '%s' "$prompt" | claude -p --allowedTools "Read" "Write" "Glob" "Grep" 2>&1)"
claude_code=$?
if [ -n "$claude_out" ]; then
    while IFS= read -r line; do log "$line"; done <<< "$claude_out"
fi
log "Claude 退出码：$claude_code"

# 4. 只有 Claude 正常结束才归档
if [ "$claude_code" -ne 0 ]; then
    log "Claude 步骤失败，邮件保留在 inbox/，本次不归档。"
    exit 1
fi
arch="$ROOT/processed/$TODAY"
mkdir -p "$arch"
if [ "${#emls[@]}" -gt 0 ]; then
    mv -f "${emls[@]}" "$arch/"
fi
for pf in _parsed.md _parsed.json _enriched.md _enriched.json; do
    if [ -f "$ROOT/inbox/$pf" ]; then
        mv -f "$ROOT/inbox/$pf" "$arch/"
    fi
done
if [ -f "$manual_file" ]; then
    mv -f "$manual_file" "$arch/manual_extra_titles.txt"
fi
log "步骤 4：${#emls[@]} 封邮件、解析件及手工补充题名已归档到 $arch"

# 5. 简报是否生成
if [ -f "$ROOT/brief/$TODAY.md" ]; then
    log "简报已生成：$ROOT/brief/$TODAY.md"
else
    log "今天无新论文，未生成简报（符合规则）。"
fi

log "===== 任务结束 ====="
