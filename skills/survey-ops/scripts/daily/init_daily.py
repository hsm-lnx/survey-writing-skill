#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""初始化「每日文献 Alert 监控」工作目录。

用法（在综述项目根目录）：
    python <skill>/scripts/daily/init_daily.py --workdir ./daily

它会：
  1. 建 inbox/ brief/ processed/ logs/ state/ manual/ 目录；
  2. 把配置检查、拉信、解析、补全、诊断、调度脚本复制到工作目录；
  3. 从模板生成 config.json（占位，需填邮箱授权码）；
  4. 从模板生成 CLAUDE.md（按原始工作版结构脱敏，需按项目改口径）；
  5. 写 .gitignore，确保 config.json 不会被提交。

重复运行只会刷新脚本；已有的 config.json 与 CLAUDE.md 不会被覆盖。
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parents[1]
TEMPLATES = SKILL_ROOT / "templates"

SCRIPTS = (
    "check_config.py",
    "pull_mail.py",
    "parse_alerts.py",
    "enrich_crossref.py",
    "check_alert_links.py",
    "uid_gaps.py",
    "run_daily.ps1",
    "run_daily.sh",
    "SOURCE.md",
)

DIRS = ("inbox", "brief", "processed", "logs", "state", "manual")

GITIGNORE = """# survey-manager daily
# config.json 含邮箱授权码，禁止提交
config.json
inbox/
processed/
logs/
state/
__pycache__/
*.pyc
"""


def say(msg: str) -> None:
    print(msg)


def copy_scripts(workdir: Path) -> None:
    for name in SCRIPTS:
        src = HERE / name
        if not src.is_file():
            say(f"  [跳过] 源文件不存在：{name}")
            continue
        shutil.copy2(src, workdir / name)
        say(f"  [复制] {name}")


def ensure_gitignore(workdir: Path) -> None:
    p = workdir / ".gitignore"
    if p.exists():
        text = p.read_text(encoding="utf-8", errors="replace")
        if "# survey-manager daily" in text:
            say("  [保留] .gitignore 已含 daily 规则")
            return
        p.write_text(text.rstrip() + "\n\n" + GITIGNORE, encoding="utf-8", newline="\n")
        say("  [追加] .gitignore")
    else:
        p.write_text(GITIGNORE, encoding="utf-8", newline="\n")
        say("  [写入] .gitignore")


def main() -> None:
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="初始化每日文献 Alert 监控工作目录")
    ap.add_argument("--workdir", default=str(Path.cwd() / "daily"),
                    help="工作目录（默认：当前目录下的 daily/）")
    args = ap.parse_args()

    workdir = Path(args.workdir).expanduser().resolve()
    workdir.mkdir(parents=True, exist_ok=True)
    for d in DIRS:
        (workdir / d).mkdir(parents=True, exist_ok=True)
    say(f"[OK] 工作目录：{workdir}")

    copy_scripts(workdir)

    cfg_src = TEMPLATES / "daily_config.example.json"
    if not cfg_src.is_file():
        say(f"[ABORT] 模板缺失：{cfg_src}")
        raise SystemExit(1)
    cfg_dst = workdir / "config.json"
    if cfg_dst.exists():
        say("  [保留] config.json 已存在（不覆盖）")
    else:
        data = json.loads(cfg_src.read_text(encoding="utf-8"))
        cfg_dst.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")
        say("  [写入] config.json（占位，需填邮箱授权码）")

    shutil.copyfile(cfg_src, workdir / "config.example.json")
    say("  [复制] config.example.json")

    rules_src = TEMPLATES / "daily_triage.md"
    rules_dst = workdir / "CLAUDE.md"
    if rules_dst.exists():
        say("  [保留] CLAUDE.md 已存在（不覆盖分诊口径）")
    elif rules_src.is_file():
        shutil.copyfile(rules_src, rules_dst)
        say("  [写入] CLAUDE.md（分诊规则模板，需按项目改口径）")
    else:
        say(f"  [跳过] 分诊模板缺失：{rules_src}")

    manual = workdir / "manual" / "extra_titles.txt"
    if not manual.exists():
        manual.write_text(
            "# 一行一条题名；邮件只展示前 5 条时，把其余题名粘到这里。\n"
            "# 以 # 开头为注释；处理成功后本文件会归档到 processed/<日期>/。\n",
            encoding="utf-8", newline="\n")
        say("  [写入] manual/extra_titles.txt")

    ensure_gitignore(workdir)

    say("")
    say("下一步：")
    say(f"  1. 编辑 {cfg_dst}")
    say("     - email / auth_code：收信邮箱与客户端授权码（不是登录密码）")
    say("     - from_filter / match_domain：Alert 发件人与域名")
    say("     - ledger_path / manuscript_globs：台账与正文位置（留空用默认）")
    say(f"  2. 编辑 {rules_dst}：把【待填】处改成你的综述范围、纳入/排除口径")
    say("  3. 先检查配置（不会显示授权码）：")
    say(f"     cd \"{workdir}\"")
    say("     python check_config.py")
    say("     python check_config.py --test-imap   # 可选：实际登录一次，确认授权码可用")
    say("  4. 手动测一遍：")
    say("     python pull_mail.py && python parse_alerts.py && python enrich_crossref.py")
    runner_ps1 = workdir / "run_daily.ps1"
    runner_sh = workdir / "run_daily.sh"
    say("  5. 建定时任务（Windows，每天 09:00）：")
    say('     schtasks /Create /TN "Survey Daily Brief" /SC DAILY /ST 09:00 '
        f'/TR "powershell -ExecutionPolicy Bypass -File \\"{runner_ps1}\\"" /F')
    say("     macOS/Linux 用 cron 调 run_daily.sh，例如：")
    say(f'     0 9 * * * "{runner_sh}"')
    say("  6. 脚本来源与改动对照见工作目录里的 SOURCE.md")
    say("  7. 详细说明见 skill 的 references/daily-lit.md")


if __name__ == "__main__":
    main()
