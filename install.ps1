#Requires -Version 5.1
<#
    survey-writing / survey-ops 双卷 skill 一键部署
    用法:
      powershell -ExecutionPolicy Bypass -File install.ps1
      powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey
      powershell -ExecutionPolicy Bypass -File install.ps1 -SkipSkeleton
#>
param(
    [string]$ProjectRoot = "",
    [switch]$SkipSkeleton
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if (-not $here) { $here = (Get-Location).Path }

Write-Host ""
Write-Host "== survey-writing / survey-ops 部署 ==" -ForegroundColor Cyan
Write-Host ""

# ---------- 1. skill 安装位置 ----------
if ($ProjectRoot) {
    $base = Join-Path $ProjectRoot ".claude\skills"
    $scope = "项目级 ($ProjectRoot)"
} else {
    $base = Join-Path $env:USERPROFILE ".claude\skills"
    $scope = "用户级 ($env:USERPROFILE)"
}
$src = Join-Path $here "skills"

if (-not (Test-Path $src)) {
    throw "找不到 skills\ —— 请在仓库根目录运行本脚本"
}

if (-not (Test-Path $base)) {
    New-Item -ItemType Directory -Force -Path $base | Out-Null
}

# 双卷 + 共享交接面，逐目录覆盖
$units = @("survey-writing", "survey-ops", "_shared")
foreach ($u in $units) {
    $s = Join-Path $src $u
    $d = Join-Path $base $u
    if (-not (Test-Path $s)) {
        Write-Host "[跳过] skills\$u 不存在" -ForegroundColor Yellow
        continue
    }
    if (Test-Path $d) {
        Write-Host "[更新] $u （覆盖同名文件，不影响其他 skill）"
    }
    Copy-Item -Path $s -Destination $base -Recurse -Force
    Write-Host "  [ok] $d" -ForegroundColor Green
}
Write-Host "     作用域：$scope"
Write-Host ""

# ---------- 2. 项目骨架 ----------
if (-not $SkipSkeleton) {
    if ($ProjectRoot) { $root = $ProjectRoot } else { $root = (Get-Location).Path }
    Write-Host "项目骨架 -> $root"

    $dirs = @("manuscript", "pdfs", "bib", "docs", "reports", "reports\_raw")
    foreach ($d in $dirs) {
        $p = Join-Path $root $d
        if (-not (Test-Path $p)) {
            New-Item -ItemType Directory -Force -Path $p | Out-Null
            Write-Host "  [新建] $d"
        } else {
            Write-Host "  [存在] $d"
        }
    }

    $ledger = Join-Path $root "bib\verified.md"
    if (-not (Test-Path $ledger)) {
        $head = @"
# 文献台账

只增不改、编号顺延。新增条目先走 survey-ops §7 验证，再入账。

| 编号 | 著录 | 依据等级 | 备注 |
|------|------|----------|------|
"@
        Set-Content -Path $ledger -Value $head -Encoding utf8
        Write-Host "  [新建] bib\verified.md"
    } else {
        Write-Host "  [存在] bib\verified.md"
    }

    $progress = Join-Path $root "docs\progress.md"
    if (-not (Test-Path $progress)) {
        Set-Content -Path $progress -Value "# 进度板`n`n| 日期 | 范围 | 产物 | 遗留 |`n|---|---|---|---|`n" -Encoding utf8
        Write-Host "  [新建] docs\progress.md"
    }
    Write-Host ""
}

# ---------- 3. 依赖检查 ----------
Write-Host "依赖检查"
$missing = @()

$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) {
    $ver = (& python --version 2>&1) -join " "
    Write-Host "  [ok] $ver"
} else {
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) {
        $ver = (& py --version 2>&1) -join " "
        Write-Host "  [ok] $ver (py launcher)"
    } else {
        Write-Host "  [缺] python —— 核验脚本无法运行" -ForegroundColor Yellow
        $missing += "python"
    }
}

$pandoc = Get-Command pandoc -ErrorAction SilentlyContinue
if ($pandoc) {
    $ver = (& pandoc --version 2>&1 | Select-Object -First 1)
    Write-Host "  [ok] $ver"
} else {
    Write-Host "  [缺] pandoc —— tools\convert.cmd (docx→md) 不可用，非必需" -ForegroundColor Yellow
    $missing += "pandoc"
}

$curl = Get-Command curl -ErrorAction SilentlyContinue
if ($curl) {
    Write-Host "  [ok] curl"
} else {
    Write-Host "  [缺] curl —— arxiv_curl.py 兜底不可用，非必需" -ForegroundColor Yellow
    $missing += "curl"
}
Write-Host ""

# ---------- 4. 环境变量检查（不打印值） ----------
Write-Host "环境变量（只报有无，不显示值）"
$vars = @("AMINER_API_KEY", "ZOTERO_USER_ID", "ZOTERO_API_KEY")
$unset = @()
foreach ($v in $vars) {
    $val = [Environment]::GetEnvironmentVariable($v, "Process")
    if ([string]::IsNullOrWhiteSpace($val)) {
        $val = [Environment]::GetEnvironmentVariable($v, "User")
    }
    if ([string]::IsNullOrWhiteSpace($val)) {
        Write-Host "  [未设] $v" -ForegroundColor Yellow
        $unset += $v
    } else {
        Write-Host "  [已设] $v"
    }
}
Write-Host ""

# ---------- 5. 收尾 ----------
Write-Host "== 完成 ==" -ForegroundColor Cyan
if ($unset.Count -gt 0) {
    Write-Host "未设置的环境变量：$($unset -join ', ')"
    Write-Host "对应的脚本会报错退出，其余功能不受影响。填法见 KEY_SETUP.md。"
}
Write-Host "用法与依赖说明见 README.md"
Write-Host "  写作卷条文：$base\survey-writing\SKILL.md"
Write-Host "  体系卷条文：$base\survey-ops\SKILL.md"
Write-Host "  交接契约：  $base\_shared\handoff.md"
Write-Host ""
