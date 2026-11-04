# -*- coding: utf-8 -*-
"""每日拉取 WOS Alert 邮件到 inbox\\ 目录。

用法：python pull_mail.py
依赖：仅 Python 标准库（imaplib / email / json / ssl / pathlib）。

要点（2026-10-24 修订）：
- 全流程只用 UID：UID SEARCH + UID FETCH。旧版用序列号枚举却把真 UID
  当序列号取正文，一旦手机端删过信（UID 与序列号错位）就永远取不到新邮件，
  且只打一行 [WARN] 就当"无新邮件"退出。这是 2026-10-24 漏掉 UID 373 的原因。
- 扫描 INBOX + Junk（WOS 邮件可能被判为广告），不依赖 \\Seen 状态，
  手机上看过的邮件照样能拉到。
- QQ 的 IMAP SEARCH 不支持固定域名子串匹配（FROM "clarivate.com" 返回 0），
  故服务端只做全量枚举，发件人过滤在客户端按域名做。
- 按 Message-ID 持久去重（state/seen_message_ids.json），已归档邮件不会重复落盘。
- 取正文失败不写入 state，且以非零退出码上报（3），让调度器保留邮件并告警，
  不再静默当成"没有新邮件"。
- 不改邮箱状态：不标记已读、不移动邮件。
"""
import hashlib
import imaplib
import json
import re
import ssl
import sys
import time

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from email import message_from_bytes
from email.header import decode_header
from email.utils import parseaddr, parsedate_to_datetime
from pathlib import Path

BASE = Path(__file__).parent
CONFIG = BASE / "config.json"
STATE = BASE / "state" / "seen_message_ids.json"


def dec(s):
    if not s:
        return ""
    out = []
    for txt, enc in decode_header(s):
        if isinstance(txt, bytes):
            for cand in (enc, "utf-8", "gb18030"):
                if not cand:
                    continue
                try:
                    out.append(txt.decode(cand, errors="replace"))
                    break
                except (LookupError, UnicodeDecodeError):
                    continue
            else:
                out.append(txt.decode("utf-8", errors="replace"))
        else:
            out.append(txt)
    return "".join(out)


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            print("[WARN] state 文件损坏，按空表处理")
    return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(STATE)


def parse_headers(data):
    """把一批 BODY[HEADER] 响应解析成 [(uid, 解析后的头部字典)]。"""
    out = []
    for item in data:
        if not isinstance(item, tuple):
            continue
        meta, payload = item
        m = re.search(rb"UID (\d+)", meta)
        if not m:
            continue
        uid = int(m.group(1))
        h = message_from_bytes(payload)
        out.append((uid, h))
    return out


def sender_ok(from_header, cfg):
    addr = parseaddr(dec(from_header))[1].lower()
    exact = cfg.get("from_filter", "").lower()
    domain = cfg.get("match_domain", "clarivate.com").lower()
    if not addr:
        return False
    return addr == exact or addr.endswith("@" + domain)


def msg_key(h, uid):
    mid = (h.get("Message-ID") or "").strip()
    if mid:
        return mid
    raw = f"{h.get('From','')}|{h.get('Subject','')}|{h.get('Date','')}|{uid}"
    return "sha1:" + hashlib.sha1(raw.encode("utf-8", "replace")).hexdigest()


def safe_name(subject, limit=40):
    s = re.sub(r"\s+", " ", subject).strip()
    s = re.sub(r"^Web of Science Alert\s*[-_:]*\s*", "", s)
    s = "".join(c if c.isalnum() or c in " -_" else "_" for c in s)
    s = re.sub(r"_+", "_", s)
    s = re.sub(r"\s+", " ", s).strip(" _")
    return s[:limit].strip() or "no-subject"


def fetch_headers(M, uids, chunk=100):
    """按 UID 分批取头部，返回 [(uid, header)]。UID FETCH 的 meta 里带真 UID。"""
    out = []
    for i in range(0, len(uids), chunk):
        part = uids[i:i + chunk]
        uid_set = ",".join(u.decode() if isinstance(u, bytes) else str(u) for u in part)
        typ, data = M.uid(
            "FETCH", uid_set,
            "(BODY.PEEK[HEADER.FIELDS (FROM SUBJECT DATE MESSAGE-ID)])",
        )
        if typ != "OK":
            print(f"[WARN] 头部批次 {i // chunk + 1} 取失败（{len(part)} 封）")
            continue
        out.extend(parse_headers(data))
    return out


def fetch_body(M, uid):
    """按 UID 取整封邮件，失败重试一次。返回 bytes 或 None。"""
    for attempt in (1, 2):
        typ, md = M.uid("FETCH", str(uid), "(BODY.PEEK[])")
        if typ == "OK" and md and isinstance(md[0], tuple) and md[0][1]:
            return md[0][1]
        if attempt == 1:
            time.sleep(2)
    return None


def main():
    if not CONFIG.exists():
        print("[ABORT] 找不到 config.json。先在当前目录运行 init_daily.py，或按 references/daily-lit.md 手动创建。")
        sys.exit(2)
    try:
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[ABORT] config.json 不是合法 JSON：{e}")
        sys.exit(2)
    if not cfg.get("imap_server") or "imap" not in cfg.get("imap_server", ""):
        print("[ABORT] config.json 里 imap_server 还没填，先去邮箱网页看收发信设置。")
        sys.exit(2)
    auth_code = str(cfg.get("auth_code", ""))
    if "授权码" in auth_code or "待填" in auth_code or len(auth_code) < 6:
        print("[ABORT] config.json 里 auth_code 还是占位，填进客户端授权码再跑。")
        sys.exit(2)

    inbox_dir = Path(cfg.get("inbox_dir") or (BASE / "inbox"))
    if not inbox_dir.is_absolute():
        inbox_dir = BASE / inbox_dir
    inbox_dir.mkdir(parents=True, exist_ok=True)
    folders = cfg.get("folders", ["INBOX", "Junk"])
    state = load_state()
    known = set(state.keys())

    ctx = ssl.create_default_context()
    M = imaplib.IMAP4_SSL(cfg["imap_server"], int(cfg["imap_port"]), ssl_context=ctx)
    M.login(cfg["email"], auth_code)

    saved = 0
    failed = []
    for folder in folders:
        typ, _ = M.select(f'"{folder}"', readonly=True)
        if typ != "OK":
            print(f"[WARN] 无法打开文件夹 {folder}，跳过")
            continue
        typ, data = M.uid("SEARCH", None, "ALL")
        if typ != "OK":
            print(f"[WARN] {folder} 检索失败，跳过")
            continue
        uids = data[0].split()
        print(f"[INFO] {folder}: {len(uids)} 封")
        if not uids:
            continue

        for uid, h in fetch_headers(M, uids):
            subj = dec(h.get("Subject", ""))
            if not sender_ok(h.get("From", ""), cfg):
                continue
            key = msg_key(h, uid)
            if key in known:
                continue
            raw = fetch_body(M, uid)
            if raw is None:
                failed.append((folder, uid, subj))
                print(f"[FAIL] UID {uid} 取正文失败：{subj[:60]}")
                continue
            fname = f"{folder.replace(' ', '_')}_{uid}_{safe_name(subj)}.eml"
            (inbox_dir / fname).write_bytes(raw)
            known.add(key)
            saved += 1
            try:
                dt = parsedate_to_datetime(h.get("Date", ""))
                when = dt.strftime("%Y-%m-%d %H:%M")
            except Exception:
                when = h.get("Date", "")
            state[key] = {"folder": folder, "uid": uid, "date": when, "subject": subj}
            print(f"[SAVE] {fname}  <- {when}")

    M.logout()
    save_state(state)
    print(f"[DONE] 落盘 {saved} 封到 {inbox_dir}")
    if failed:
        print(f"[FAIL] 共 {len(failed)} 封匹配邮件未能取回，已保留在邮箱，下次重试：")
        for folder, uid, subj in failed:
            print(f"  - {folder} UID {uid}: {subj[:80]}")
        sys.exit(3)


if __name__ == "__main__":
    main()
