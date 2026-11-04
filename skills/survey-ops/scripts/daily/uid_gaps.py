# -*- coding: utf-8 -*-
"""只读诊断：统计邮箱文件夹的 UID 空洞，排查 UID 与序列号错位导致的漏信。"""
import argparse
import imaplib
import json
import ssl
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--folder", default="INBOX")
    args = ap.parse_args()

    cfg = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
    M = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg["imap_port"]),
                          ssl_context=ssl.create_default_context())
    M.login(cfg["email"], cfg["auth_code"])
    typ, _ = M.select(f'"{args.folder}"', readonly=True)
    if typ != "OK":
        print(f"[ABORT] 无法打开文件夹 {args.folder}")
        sys.exit(2)
    typ, d = M.uid("SEARCH", None, "ALL")
    uids = [int(x) for x in d[0].split()]
    if not uids:
        print("UID 数: 0")
        M.logout()
        return
    gaps = [u for u in range(1, max(uids) + 1) if u not in set(uids)]
    print(f"文件夹: {args.folder}")
    print("UID 数:", len(uids), " 最大 UID:", max(uids), " 空洞数:", len(gaps))
    print("空洞 UID:", gaps)
    M.logout()


if __name__ == "__main__":
    main()
