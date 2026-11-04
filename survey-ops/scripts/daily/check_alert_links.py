# -*- coding: utf-8 -*-
"""只读诊断：检查一封 Alert 邮件里到底有几条记录、View all 指向哪里、有没有隐藏块。

用法：
    python check_alert_links.py [邮件路径]
不给路径时，自动取 inbox/ 与 processed/ 下最新的一封 .eml。
"""
import email
import pathlib
import re
import sys
from urllib.parse import parse_qs, unquote, urlparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = pathlib.Path(__file__).resolve().parent


def latest_eml():
    files = list((BASE / "inbox").glob("*.eml")) if (BASE / "inbox").is_dir() else []
    if (BASE / "processed").is_dir():
        files += list((BASE / "processed").rglob("*.eml"))
    if not files:
        return None
    return max(files, key=lambda p: p.stat().st_mtime)


def main():
    if len(sys.argv) > 1:
        p = pathlib.Path(sys.argv[1])
    else:
        p = latest_eml()
    if not p or not p.is_file():
        print("[ABORT] 没找到 .eml。请给一个邮件路径，或先跑 pull_mail.py。")
        sys.exit(2)

    msg = email.message_from_bytes(p.read_bytes())
    parts = [x for x in msg.walk() if x.get_content_type() == "text/html"]
    if not parts:
        print(f"[ABORT] {p} 里没有 text/html 部件")
        sys.exit(2)
    html = parts[0].get_payload(decode=True).decode("utf-8", "replace")

    print("邮件:", p)
    print("full-record 出现次数:", html.count("full-record"))
    print("display:none 出现次数:", html.count("display:none"))
    print("visibility:hidden:", html.count("visibility:hidden"))
    print("View all 文本:", re.findall(r"View all[^<]*", html)[:5])
    for m in re.finditer(r"<a\b[^>]*>(.*?)</a>", html, re.S | re.I):
        txt = re.sub(r"<[^>]+>", "", m.group(1)).strip()
        if "View all" in txt:
            hm = re.search(r"href=['\"]([^'\"]+)", m.group(0))
            href = hm.group(1) if hm else ""
            q = parse_qs(urlparse(href).query)
            print("View all link:", unquote(q["u"][0]) if "u" in q else href)
    print("邮件 MIME 部件:")
    for x in msg.walk():
        print(" ", x.get_content_type(), x.get("Content-Disposition"))


if __name__ == "__main__":
    main()
