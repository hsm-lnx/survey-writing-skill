# 每日调度：拉信 → 解析 → 补全 → 让 Claude 生成简报 → 归档
# 由 Windows 任务计划程序每天调用；也可手动：
#   powershell -ExecutionPolicy Bypass -File .\run_daily.ps1
#
# 本文件必须存成 UTF-8 带 BOM + CRLF：Windows PowerShell 5.1 读无 BOM 的 UTF-8
# 会按 ANSI 解码，中文注释会导致解析失败。

param(
    [string]$WorkDir = ""
)

$ErrorActionPreference = "Stop"
if ([string]::IsNullOrWhiteSpace($WorkDir)) { $WorkDir = $PSScriptRoot }
$root = (Resolve-Path -LiteralPath $WorkDir).Path
Set-Location $root
try { [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false) } catch {}

$today = Get-Date -Format "yyyy-MM-dd"
$logDir = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$log = Join-Path $logDir "$today.log"

function Log($msg) {
    $line = "[$(Get-Date -Format 'HH:mm:ss')] $msg"
    Write-Host $line
    Add-Content -Path $log -Value $line -Encoding utf8
}

# 计划任务的环境 PATH 与交互终端不同，固定解析到一个可用的解释器。
# 优先级：SURVEY_DAILY_PYTHON 环境变量 → python → py -3 → 常见安装路径。
function Resolve-Python {
    if ($env:SURVEY_DAILY_PYTHON -and (Test-Path $env:SURVEY_DAILY_PYTHON)) {
        return @($env:SURVEY_DAILY_PYTHON)
    }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return @($cmd.Source) }
    $cmd = Get-Command py -ErrorAction SilentlyContinue
    if ($cmd) { return @($cmd.Source, "-3") }
    foreach ($c in @(
        "D:\Miniconda_Destination\python.exe",
        "C:\Program Files\Python310\python.exe",
        "C:\Python314\python.exe"
    )) {
        if (Test-Path $c) { return @($c) }
    }
    return @("python")
}

function Invoke-Py {
    param([string]$Script, [string[]]$Extra = @())
    $py = Resolve-Python
    $exe = $py[0]
    $pyArgs = @()
    if ($py.Count -gt 1) { $pyArgs = $py[1..($py.Count - 1)] }
    $pyArgs += @((Join-Path $root $Script)) + $Extra
    $ErrorActionPreference = "Continue"
    $out = & $exe @pyArgs 2>&1
    $code = $LASTEXITCODE
    $ErrorActionPreference = "Stop"
    foreach ($lineOut in $out) { Log ([string]$lineOut) }
    return $code
}

Log "===== 每日文献简报任务开始 ====="
Log "工作目录：$root"

# 1. 拉信
Log "步骤 1：拉取 Alert 邮件"
$code = Invoke-Py "pull_mail.py"
if ($code -ne 0) {
    Log "拉信失败（退出码 $code），退出，邮件保留在邮箱。"
    exit 1
}

# 1.5 解析邮件（quoted-printable HTML -> 结构化 _parsed.md）
Log "步骤 1.5：解析 Alert 邮件为 _parsed.md"
$code = Invoke-Py "parse_alerts.py"
if ($code -eq 4) {
    # 零新增时数据库仍会发一封空提醒；归档后安静退出，不调 Claude、不生成简报
    $zeroDir = Join-Path $root "processed\$today"
    New-Item -ItemType Directory -Force -Path $zeroDir | Out-Null
    $zeroEmails = Get-ChildItem -Path (Join-Path $root "inbox") -Filter "*.eml" -ErrorAction SilentlyContinue
    if ($zeroEmails) { $zeroEmails | Move-Item -Destination $zeroDir -Force }
    Log "步骤 2：本轮 0 条新记录（空提醒），邮件已归档，安静退出。"
    exit 0
}
if ($code -ne 0) {
    Log "解析失败（退出码 $code），退出，邮件保留在 inbox\。"
    exit 1
}

# 1.6 按题名找 DOI，再按 DOI 补全作者/年份/卷期页/摘要，并与台账、正文、历史简报对重
Log "步骤 1.6：Crossref / OpenAlex 补全著录与摘要"
$code = Invoke-Py "enrich_crossref.py"
if ($code -eq 2) {
    Log "补全全部失败（网络不可用？），退回 _parsed.md 继续生成简报。"
} elseif ($code -ne 0) {
    Log "补全异常（退出码 $code），退回 _parsed.md 继续生成简报。"
}

# 2. 检查 inbox 是否有新邮件或手工补充题名
$inboxDir = Join-Path $root "inbox"
$emls = Get-ChildItem -Path $inboxDir -Filter "*.eml" -ErrorAction SilentlyContinue
$manualFile = Join-Path $root "manual\extra_titles.txt"
$manualLines = @()
if (Test-Path $manualFile) {
    $manualLines = @(Get-Content $manualFile -Encoding UTF8 -ErrorAction SilentlyContinue |
        Where-Object { $_.Trim() -and -not $_.Trim().StartsWith("#") })
}
if ((-not $emls -or $emls.Count -eq 0) -and $manualLines.Count -eq 0) {
    Log "inbox\ 无新邮件、manual\ 无补充题名，按规则保持安静，不生成简报。"
    exit 0
}
if ($manualLines.Count -gt 0) {
    Log "manual\ 有 $($manualLines.Count) 条补充题名，一并处理"
}
$emailCount = 0
if ($emls) { $emailCount = $emls.Count }
Log "步骤 2：inbox\ 有 $emailCount 封新邮件，调 Claude 生成简报"

# 3. 调 Claude（自动读当前目录 CLAUDE.md）
$claudeCmd = Get-Command claude -ErrorAction SilentlyContinue
if (-not $claudeCmd) {
    Log "找不到 claude 命令。请确认 Claude Code 已安装并在 PATH 里。"
    exit 1
}
$prompt = @"
按当前目录 CLAUDE.md 里的规则，优先读取 inbox/_enriched.md（缺失时依次退回 _parsed.md、.eml），逐条分诊，生成今天的中文简报到 brief/ 目录。
如果所有记录都没有新论文（已在 processed/ 历史里或已在台账中），就不要生成 brief 文件，直接结束。
生成完简报后，不要做任何其他事。
"@
$ErrorActionPreference = "Continue"
$claudeOut = $prompt | & $claudeCmd.Source -p --allowedTools "Read" "Write" "Glob" "Grep" 2>&1
$claudeCode = $LASTEXITCODE
$ErrorActionPreference = "Stop"
foreach ($lineOut in $claudeOut) { Log ([string]$lineOut) }
Log "Claude 退出码：$claudeCode"

# 4. 只有 Claude 正常结束才归档；失败则邮件留在 inbox 下次重试
if ($claudeCode -ne 0) {
    Log "Claude 步骤失败，邮件保留在 inbox\，本次不归档。"
    exit 1
}
$archDir = Join-Path $root "processed\$today"
New-Item -ItemType Directory -Force -Path $archDir | Out-Null
if ($emls) { $emls | Move-Item -Destination $archDir -Force }
foreach ($pf in @("_parsed.md", "_parsed.json", "_enriched.md", "_enriched.json")) {
    $p = Join-Path $inboxDir $pf
    if (Test-Path $p) { Move-Item $p -Destination $archDir -Force }
}
if (Test-Path $manualFile) {
    Move-Item $manualFile -Destination (Join-Path $archDir "manual_extra_titles.txt") -Force
}
Log "步骤 4：$emailCount 封邮件、解析件及手工补充题名已归档到 $archDir"

# 5. 简报是否生成
$brief = Join-Path $root "brief\$today.md"
if (Test-Path $brief) {
    Log "简报已生成：$brief"
} else {
    Log "今天无新论文，未生成简报（符合规则）。"
}

Log "===== 任务结束 ====="
