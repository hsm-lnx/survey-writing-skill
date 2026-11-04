#Requires -Version 5.1
<#
    survey-writing / survey-ops 双卷 skill 一键部署（Windows）

    用法:
      powershell -ExecutionPolicy Bypass -File install.ps1
      powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey
      powershell -ExecutionPolicy Bypass -File install.ps1 -ProjectRoot D:\my_survey -AutoInstall
      powershell -ExecutionPolicy Bypass -File install.ps1 -SkipSkeleton

    参数:
      -ProjectRoot   项目目录；不给则装到 ~/.claude/skills（所有项目可用）
      -SkipSkeleton  不建 manuscript/pdfs 等项目目录
      -AutoInstall   缺 Python / pandoc / curl 时，尝试用 winget / choco / scoop 自动安装
      -NoDoctor      装完不自动跑环境体检
#>
param(
    [string]$ProjectRoot = "",
    [switch]$SkipSkeleton,
    [switch]$AutoInstall,
    [switch]$NoDoctor
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
if (-not $here) { $here = (Get-Location).Path }

function Write-Step($text) {
    Write-Host ""
    Write-Host "== $text ==" -ForegroundColor Cyan
}
function Write-Ok($text) { Write-Host "  [ok] $text" -ForegroundColor Green }
function Write-Warn($text) { Write-Host "  [!] $text" -ForegroundColor Yellow }
function Write-Fail($text) { Write-Host "  [X] $text" -ForegroundColor Red }

function Test-RealPython([string]$cmd) {
    if (-not $cmd) { return $false }
    $c = Get-Command $cmd -ErrorAction SilentlyContinue
    if (-not $c) { return $false }
    # 跳过 Microsoft Store 的 python.exe 占位符（运行它会弹应用商店）
    if ($c.Source -and $c.Source -like "*\WindowsApps\python*.exe") { return $false }
    try {
        $out = & $cmd -c "import sys; print('%d.%d' % sys.version_info[:2])"
        if ($LASTEXITCODE -ne 0) { return $false }
        $parts = "$out".Trim().Split(".")
        $major = [int]$parts[0]
        $minor = [int]$parts[1]
        return ($major -gt 3 -or ($major -eq 3 -and $minor -ge 8))
    } catch {
        return $false
    }
}

function Find-Python {
    foreach ($cmd in @("python", "py")) {
        if (Test-RealPython $cmd) { return $cmd }
    }
    return $null
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Install-Python {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        foreach ($id in @("Python.Python.3.13", "Python.Python.3.12", "Python.Python.3.11")) {
            Write-Host "  尝试：winget install --id $id ..."
            & winget install --id $id -e --accept-source-agreements --accept-package-agreements --silent
            if ($LASTEXITCODE -eq 0) { break }
        }
        Refresh-Path
        return (Find-Python)
    }
    $choco = Get-Command choco -ErrorAction SilentlyContinue
    if ($choco) {
        Write-Host "  尝试：choco install python -y ..."
        & choco install python -y
        Refresh-Path
        return (Find-Python)
    }
    $scoop = Get-Command scoop -ErrorAction SilentlyContinue
    if ($scoop) {
        Write-Host "  尝试：scoop install python ..."
        & scoop install python
        return (Find-Python)
    }
    return $null
}

function Install-Tool([string]$display, [string]$wingetId, [string]$chocoName) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        Write-Host "  尝试：winget install --id $wingetId ..."
        & winget install --id $wingetId -e --accept-source-agreements --accept-package-agreements --silent
        if ($LASTEXITCODE -eq 0) { Write-Ok "$display 安装命令完成" }
        else { Write-Warn "$display 安装命令退出码 $LASTEXITCODE" }
        Refresh-Path
        return
    }
    $choco = Get-Command choco -ErrorAction SilentlyContinue
    if ($choco) {
        Write-Host "  尝试：choco install $chocoName -y ..."
        & choco install $chocoName -y
        Refresh-Path
        return
    }
    $scoop = Get-Command scoop -ErrorAction SilentlyContinue
    if ($scoop) {
        Write-Host "  尝试：scoop install $chocoName ..."
        & scoop install $chocoName
        Refresh-Path
        return
    }
    Write-Warn "没找到 winget / choco / scoop；请手动安装 $display"
}

Write-Step "survey-writing / survey-ops 部署"

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
        Write-Warn "skills\$u 不存在，跳过"
        continue
    }
    if (Test-Path $d) {
        Write-Host "  [更新] $u （覆盖同名文件，不影响其他 skill）"
    }
    Copy-Item -Path $s -Destination $base -Recurse -Force
    Write-Ok $d
}
Write-Host "  作用域：$scope"

# 把体检脚本和密钥说明也放一份到 .claude\，方便装完以后随时用
$setupDir = Split-Path $base -Parent
$doctorSrc = Join-Path $here "tools\doctor.py"
$doctorDst = Join-Path $setupDir "doctor.py"
if (Test-Path $doctorSrc) {
    Copy-Item $doctorSrc $doctorDst -Force
    Write-Ok "环境体检脚本 -> $doctorDst"
}
$keySrc = Join-Path $here "KEY_SETUP.md"
if (Test-Path $keySrc) {
    Copy-Item $keySrc (Join-Path $setupDir "KEY_SETUP.md") -Force
}

# ---------- 2. 项目骨架 ----------
# 若目标目录就是本仓库自身（用户照 README 在 clone 里直接跑），不建骨架，免得弄脏干净的 clone
if (-not $SkipSkeleton) {
    if ($ProjectRoot) { $root = $ProjectRoot } else { $root = (Get-Location).Path }
    if ([IO.Path]::GetFullPath($root).TrimEnd("\") -eq [IO.Path]::GetFullPath($here).TrimEnd("\")) {
        Write-Warn "当前目录是本仓库自身，不在这里建 manuscript/pdfs 等目录。"
        Write-Host "           到你的项目目录里跑：install.ps1 -ProjectRoot <项目目录>" -ForegroundColor Yellow
        $SkipSkeleton = $true
    }
}

if (-not $SkipSkeleton) {
    Write-Step "项目骨架 -> $root"

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
}

# ---------- 3. 依赖检查与自动安装 ----------
Write-Step "依赖检查"

$pythonCmd = Find-Python
if ($pythonCmd) {
    $ver = (& $pythonCmd -c "import sys; print('Python %d.%d.%d' % sys.version_info[:3])")
    Write-Ok "$ver（命令：$pythonCmd）"
} else {
    Write-Fail "python 未安装 —— 核验脚本无法运行"
    if ($AutoInstall) {
        Write-Host "  正在尝试自动安装 Python（可能弹出权限确认，请允许）..."
        $pythonCmd = Install-Python
        if ($pythonCmd) {
            $ver = (& $pythonCmd -c "import sys; print('Python %d.%d.%d' % sys.version_info[:3])")
            Write-Ok "已安装：$ver（命令：$pythonCmd）"
        } else {
            Write-Warn "自动安装没成功。请手动安装：https://www.python.org/downloads/"
        }
    } else {
        Write-Host "  可加 -AutoInstall 让脚本尝试自动安装，或手动安装：https://www.python.org/downloads/"
    }
}

$pandoc = Get-Command pandoc -ErrorAction SilentlyContinue
if ($pandoc) {
    $ver = (& pandoc --version | Select-Object -First 1)
    Write-Ok "$ver"
} else {
    Write-Warn "pandoc 未安装 —— tools\convert.cmd (docx→md) 不可用，非必需"
    if ($AutoInstall) { Install-Tool "pandoc" "JohnMacFarlane.Pandoc" "pandoc" }
}

$curl = Get-Command curl -ErrorAction SilentlyContinue
if ($curl) {
    Write-Ok "curl 已安装"
} else {
    Write-Warn "curl 未安装 —— arxiv_curl.py 兜底不可用，非必需"
    if ($AutoInstall) { Install-Tool "curl" "cURL.cURL" "curl" }
}

# 没跑体检时，给一个简单的密钥有无提示
if ($NoDoctor -or -not $pythonCmd) {
    Write-Step "密钥（只报有无，不显示值）"
    $vars = @("AMINER_API_KEY", "ZOTERO_USER_ID", "ZOTERO_API_KEY")
    $unset = @()
    foreach ($v in $vars) {
        $val = [Environment]::GetEnvironmentVariable($v, "Process")
        if ([string]::IsNullOrWhiteSpace($val)) {
            $val = [Environment]::GetEnvironmentVariable($v, "User")
        }
        if ([string]::IsNullOrWhiteSpace($val)) {
            Write-Warn "$v 未设置"
            $unset += $v
        } else {
            Write-Ok "$v 已设置"
        }
    }
    if ($unset.Count -gt 0) {
        Write-Host "  这些是可选项；对应的脚本会报错退出，其余功能不受影响。"
        if ($pythonCmd) {
            Write-Host "  配置方法见 KEY_SETUP.md，或装好后运行：$pythonCmd `"$doctorDst`" --configure"
        } else {
            Write-Host "  配置方法见 KEY_SETUP.md（装好 Python 后可用 doctor.py --configure）。"
        }
    }
}

# ---------- 4. 环境体检 ----------
$doctorRun = $doctorDst
if (-not (Test-Path $doctorRun)) { $doctorRun = $doctorSrc }
if (-not $NoDoctor -and $pythonCmd -and (Test-Path $doctorRun)) {
    Write-Step "环境体检"
    $doctorArgs = @($doctorRun)
    if ($ProjectRoot) { $doctorArgs += @("--project-root", $ProjectRoot) }
    & $pythonCmd @doctorArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Warn "体检发现必需项未满足；按上面的 [X] 处理。已安装的 skill 文件不受影响。"
    }
}

# ---------- 5. 收尾 ----------
Write-Step "完成"
Write-Host "  写作卷条文：$base\survey-writing\SKILL.md"
Write-Host "  体系卷条文：$base\survey-ops\SKILL.md"
Write-Host "  交接契约：  $base\_shared\handoff.md"
Write-Host "  使用说明：  仓库根目录 README.md"
if ($pythonCmd) {
    Write-Host ""
    if ($ProjectRoot) {
        Write-Host "  随时体检：  $pythonCmd `"$doctorDst`" --project-root `"$ProjectRoot`""
    } else {
        Write-Host "  随时体检：  $pythonCmd `"$doctorDst`""
    }
    Write-Host "  配置密钥：  $pythonCmd `"$doctorDst`" --configure"
    if ($ProjectRoot) {
        Write-Host "  每日监控：  $pythonCmd `"$base\survey-ops\scripts\daily\init_daily.py`" --workdir `"$ProjectRoot\daily`""
    } else {
        Write-Host "  每日监控：  $pythonCmd `"$base\survey-ops\scripts\daily\init_daily.py`" --workdir .\daily"
    }
    Write-Host "              （可选；初始化后填 daily\config.json，详见 README §4.8）"
}
Write-Host ""
