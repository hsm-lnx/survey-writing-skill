#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""只读检查 daily/config.json 是否填好；绝不显示授权码。

用法（在 daily/ 目录）：
    python check_config.py
    python check_config.py --test-imap    # 可选：实际登录一次邮箱，确认授权码可用

退出码：
    0  字段齐全（--test-imap 时也登录成功）
    2  config.json 缺失、不是合法 JSON，或有字段没填/仍是占位
    3  --test-imap 登录失败（授权码过期、IMAP 未开、网络不通等）
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PLACEHOLDER_BITS = ("待填", "your-email", "example.com")


def say(msg: str) -> None:
    print(msg)


def is_placeholder(value) -> bool:
    if not isinstance(value, str):
        return True
    text = value.strip()
    if not text:
        return True
    return any(bit in text.lower() for bit in PLACEHOLDER_BITS)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="检查每日 Alert 监控配置")
    ap.add_argument("--config", default=str(BASE / "config.json"),
                    help="配置文件路径（默认：脚本同目录 config.json）")
    ap.add_argument("--test-imap", action="store_true",
                    help="实际登录一次 IMAP；会联网，成功后不显示授权码")
    args = ap.parse_args()

    path = Path(args.config)
    if not path.is_file():
        say(f"[MISSING] 找不到 {path}")
        say("          先运行 init_daily.py 生成配置，再填写。")
        return 2
    try:
        cfg = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        say(f"[FAIL] config.json 不是合法 JSON：{exc}")
        return 2
    if not isinstance(cfg, dict):
        say("[FAIL] config.json 顶层必须是对象 {...}")
        return 2

    problems = []

    def need(key: str, label: str, check=None):
        value = cfg.get(key)
        if value is None or (isinstance(value, str) and not value.strip()):
            problems.append(f"{key}（{label}）未填")
            return None
        if isinstance(value, str) and is_placeholder(value):
            problems.append(f"{key}（{label}）还是占位符")
            return None
        if check and not check(value):
            problems.append(f"{key}（{label}）格式不对")
            return None
        return value

    need("imap_server", "IMAP 服务器",
         lambda v: isinstance(v, str) and "." in v.strip() and " " not in v.strip())
    need("imap_port", "IMAP 端口",
         lambda v: isinstance(v, int) and 1 <= v <= 65535)
    email = need("email", "收信邮箱完整地址",
                 lambda v: isinstance(v, str) and bool(EMAIL_RE.match(v.strip())))
    need("auth_code", "邮箱客户端授权码",
         lambda v: isinstance(v, str) and len(v.strip()) >= 6)

    from_filter = cfg.get("from_filter")
    domain = cfg.get("match_domain")
    has_filter = isinstance(from_filter, str) and from_filter.strip() and not is_placeholder(from_filter)
    has_domain = isinstance(domain, str) and domain.strip() and not is_placeholder(domain)
    if not has_filter and not has_domain:
        problems.append("from_filter / match_domain 至少填一个：Alert 发件人完整地址或发件人域名")

    folders = cfg.get("folders", ["INBOX", "Junk"])
    if not (isinstance(folders, list) and all(isinstance(x, str) and x.strip() for x in folders)):
        problems.append("folders 必须是字符串数组，例如 [\"INBOX\", \"Junk\"]")

    if "use_ssl" in cfg and not isinstance(cfg["use_ssl"], bool):
        problems.append("use_ssl 必须是 true / false")

    ledger = cfg.get("ledger_path", "")
    if ledger and not isinstance(ledger, str):
        problems.append("ledger_path 必须是字符串；留空表示用 ../bib/verified.md")

    globs = cfg.get("manuscript_globs", [])
    if globs and not (isinstance(globs, list) and all(isinstance(x, str) for x in globs)):
        problems.append("manuscript_globs 必须是字符串数组；留空表示用默认正文位置")

    say(f"[INFO] 配置文件：{path}")
    say("[INFO] 只检查字段是否齐全，不显示授权码。")

    if problems:
        say("")
        for item in problems:
            say(f"[NOT READY] {item}")
        say("")
        say("填好后重跑：python check_config.py")
        return 2

    say("")
    say("[OK] 必填字段齐全，格式检查通过。")
    say("[OK] 授权码已填写（未显示）。")

    gitignore = path.parent / ".gitignore"
    if gitignore.is_file():
        if "config.json" in gitignore.read_text(encoding="utf-8", errors="replace"):
            say("[OK] .gitignore 已排除 config.json。")
        else:
            say("[WARN] .gitignore 里没有 config.json；提交前务必确认不要把它带进 git。")
    else:
        say("[WARN] daily/ 下没有 .gitignore；提交前务必确认不要提交 config.json。")

    if not args.test_imap:
        say("")
        say("下一步可选手动验证：python check_config.py --test-imap")
        return 0

    import imaplib
    import ssl

    say("")
    say("[INFO] 正在登录 IMAP（不会显示授权码）...")
    try:
        client = imaplib.IMAP4_SSL(str(cfg["imap_server"]), int(cfg["imap_port"]),
                                   ssl_context=ssl.create_default_context())
        try:
            client.login(str(email), str(cfg["auth_code"]))
            client.logout()
        finally:
            try:
                client.shutdown()
            except Exception:
                pass
    except Exception as exc:
        say(f"[FAIL] IMAP 登录失败：{type(exc).__name__}: {exc}")
        say("       常见原因：授权码过期、IMAP 服务未开启、邮箱地址不完整、网络/代理不通。")
        return 3

    say("[OK] IMAP 登录成功，配置可用。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
