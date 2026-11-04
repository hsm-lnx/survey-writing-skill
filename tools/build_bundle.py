#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 survey-writing/ 与 survey-ops/ 重新打包成单 skill 的 survey-manager/。

用法（在技能包根目录）：
    python tools/build_bundle.py

只重生成 survey-manager/ 的模块、脚本、模板和交接契约；
survey-manager/SKILL.md（路由入口）是本脚本的输入，不会被覆盖。
"""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# 兼容两种布局：发布包（根目录下 survey-*）与部署仓库（skills/ 下 survey-*）
if (ROOT / "skills" / "survey-writing").is_dir() and (ROOT / "skills" / "survey-ops").is_dir():
    BUNDLE = ROOT / "skills" / "survey-manager"
    WRITING = ROOT / "skills" / "survey-writing"
    OPS = ROOT / "skills" / "survey-ops"
else:
    BUNDLE = ROOT / "survey-manager"
    WRITING = ROOT / "survey-writing"
    OPS = ROOT / "survey-ops"

HANDOFF_OLD_NOTE = (
    "> 本文件在两卷中各存一份（`survey-writing/references/handoff.md` 与 "
    "`survey-ops/references/handoff.md`），内容必须一致；改一份时同步另一份。"
)
HANDOFF_BUNDLE_NOTE = (
    "> 本文件是合并包内的唯一交接契约。独立双卷版本在各自的 `references/handoff.md`，"
    "内容必须与本文一致。"
)

DOCTOR_OLD_WRITING = (
    "5. **首次使用或换机器先体检。** 在项目根目录跑 `python .claude/doctor.py`"
    "（`python3` 视系统而定），它会检查 Python、pandoc、Zotero 与外部接口；"
    "配置 AMiner／Zotero 密钥用 `--configure`。体检只读，不会改文献库。"
)
DOCTOR_NEW_WRITING = (
    "5. **首次使用或换机器先体检。** 体检脚本是本 skill 的 `tools/doctor.py`，"
    "用法见入口 `SKILL.md` 的「部署与体检」；它会检查 Python、pandoc、Zotero 与外部接口。"
    "体检只读，不会改文献库。"
)
DOCTOR_OLD_OPS = (
    "4. **首次使用或换机器先体检。** 在项目根目录跑 `python .claude/doctor.py`"
    "（`python3` 视系统而定）；缺 Python／pandoc／Zotero 按报告提示处理，"
    "配置 AMiner／Zotero 密钥跑 `python .claude/doctor.py --configure`。体检只读，不会改文献库。"
)
DOCTOR_NEW_OPS = (
    "4. **首次使用或换机器先体检。** 体检脚本是本 skill 的 `tools/doctor.py`，"
    "用法见入口 `SKILL.md` 的「部署与体检」；缺 Python／pandoc／Zotero 按报告提示处理。"
    "体检只读，不会改文献库。"
)


def fail(msg: str) -> "NoReturn":
    print(f"错误：{msg}", file=sys.stderr)
    raise SystemExit(1)


def body_of(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        fail(f"{path} 缺少 YAML frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        fail(f"{path} 的 frontmatter 没有闭合")
    return text[end + 5:].lstrip("\n")


def module_text(src: Path, label: str, own_task: str, other: str, other_task: str) -> str:
    """取 SKILL.md 正文，并把「单卷/合并包」部署说明改写成模块内说法。"""
    text = body_of(src)
    pattern = re.compile(r"^(\d+)\. \*\*单卷与合并包。\*\*[^\n]*$", re.M)
    replacement = (
        r"\1. **单卷与合并包。** 本模块已在合并包 `survey-manager` 内："
        f"{own_task}直接读本文件，{other_task}读 `references/{other}.md`；"
        f"只有独立双卷安装时才需另装 `{other}`。"
    )
    text, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        fail(f"{src} 中找不到「单卷与合并包」说明，无法改写为模块内说法")

    if label == "写作卷":
        if DOCTOR_OLD_WRITING not in text:
            fail(f"{src} 中找不到写作卷的体检说明")
        text = text.replace(DOCTOR_OLD_WRITING, DOCTOR_NEW_WRITING, 1)
    else:
        if DOCTOR_OLD_OPS not in text:
            fail(f"{src} 中找不到体系卷的体检说明")
        text = text.replace(DOCTOR_OLD_OPS, DOCTOR_NEW_OPS, 1)

    # 合并包内脚本就在 scripts/，去掉独立卷的 survey-ops/ 前缀
    text = text.replace("survey-ops/scripts/", "scripts/")
    return (
        f"<!-- 合并包模块：{label}。本模块已在 survey-manager 内，无需另装独立卷；"
        "所有路径以本 skill 根目录为基准。 -->\n\n" + text
    )


def write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")
    print(f"  [写入] {path.relative_to(ROOT)}")


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")

    for d in (WRITING, OPS):
        if not d.is_dir():
            fail(f"找不到 {d.name}/ —— 请在技能包根目录运行本脚本")
    if not (BUNDLE / "SKILL.md").is_file():
        fail("survey-manager/SKILL.md 不存在；请先保留路由入口再运行本脚本")

    handoff_w = WRITING / "references" / "handoff.md"
    handoff_o = OPS / "references" / "handoff.md"
    if not handoff_w.is_file() or not handoff_o.is_file():
        fail("两卷的 references/handoff.md 必须都存在")
    if handoff_w.read_text(encoding="utf-8") != handoff_o.read_text(encoding="utf-8"):
        fail("两卷的 references/handoff.md 内容不一致，请先同步再打包")

    print("== 生成 survey-manager/ ==")

    write(
        BUNDLE / "references" / "survey-writing.md",
        module_text(
            WRITING / "SKILL.md",
            "写作卷",
            "写作判断",
            "survey-ops",
            "文献核验、台账、Zotero 等体系动作",
        ),
    )
    write(
        BUNDLE / "references" / "survey-ops.md",
        module_text(
            OPS / "SKILL.md",
            "体系卷",
            "机械运转",
            "survey-writing",
            "写作判断",
        ),
    )

    daily_ref = OPS / "references" / "daily-lit.md"
    if daily_ref.is_file():
        daily_ref.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(daily_ref, BUNDLE / "references" / "daily-lit.md")
        print("  [复制] references/daily-lit.md")

    citation = WRITING / "references" / "citation_style_notes.md"
    if citation.is_file():
        text = citation.read_text(encoding="utf-8").replace("survey-ops/scripts/", "scripts/")
        (BUNDLE / "references" / "citation_style_notes.md").write_text(
            text, encoding="utf-8", newline="\n")
        print("  [复制] references/citation_style_notes.md")

    template = WRITING / "templates" / "section_workflow.md"
    if template.is_file():
        (BUNDLE / "templates").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, BUNDLE / "templates" / "section_workflow.md")
        print("  [复制] templates/section_workflow.md")

    for name in ("daily_triage.md", "daily_config.example.json"):
        tpl = OPS / "templates" / name
        if tpl.is_file():
            (BUNDLE / "templates").mkdir(parents=True, exist_ok=True)
            shutil.copyfile(tpl, BUNDLE / "templates" / name)
            print(f"  [复制] templates/{name}")

    key_setup = ROOT / "KEY_SETUP.md"
    if key_setup.is_file():
        text = key_setup.read_text(encoding="utf-8")
        text = text.replace(
            ".claude/skills/survey-ops/scripts/",
            ".claude/skills/survey-manager/scripts/",
        )
        note = (
            "> 合并包说明：本 skill 的体检脚本在 `tools/doctor.py`，核验脚本在 `scripts/`。"
            "下面的 `.claude/doctor.py` 指把它复制到项目 `.claude/` 后的路径；"
            "若未复制，用 `.claude/skills/survey-manager/tools/doctor.py`。"
        )
        text = text.replace("# 密钥接入明细\n\n", "# 密钥接入明细\n\n" + note + "\n\n", 1)
        (BUNDLE / "references" / "KEY_SETUP.md").write_text(
            text, encoding="utf-8", newline="\n")
        print("  [复制] references/KEY_SETUP.md")

    convert = ROOT / "tools" / "convert.cmd"
    if convert.is_file():
        (BUNDLE / "tools").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(convert, BUNDLE / "tools" / "convert.cmd")
        print("  [复制] tools/convert.cmd")

    doctor = ROOT / "tools" / "doctor.py"
    if doctor.is_file():
        (BUNDLE / "tools").mkdir(parents=True, exist_ok=True)
        shutil.copyfile(doctor, BUNDLE / "tools" / "doctor.py")
        print("  [复制] tools/doctor.py")

    # 递归复制 scripts/（含 daily/ 子目录与 .ps1/.sh/.json 等非 .py 文件）
    scripts = sorted(
        p for p in (OPS / "scripts").rglob("*")
        if p.is_file()
        and "__pycache__" not in p.parts
        and p.suffix.lower() != ".pyc"
    )
    if not scripts:
        fail("survey-ops/scripts/ 下没有可复制的文件")
    for script in scripts:
        rel = script.relative_to(OPS / "scripts")
        dst = BUNDLE / "scripts" / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(script, dst)
        print(f"  [复制] scripts/{rel.as_posix()}")

    handoff = handoff_w.read_text(encoding="utf-8")
    if HANDOFF_OLD_NOTE in handoff:
        handoff = handoff.replace(HANDOFF_OLD_NOTE, HANDOFF_BUNDLE_NOTE, 1)
    write(BUNDLE / "references" / "handoff.md", handoff)

    print(f"完成。上传时只上传 {BUNDLE.relative_to(ROOT).as_posix()}/ 整个目录。")


if __name__ == "__main__":
    main()
