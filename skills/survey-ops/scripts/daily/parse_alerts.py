# -*- coding: utf-8 -*-
"""把 inbox\\*.eml（Web of Science Alert）解析成结构化的 _parsed.md。

用法：python parse_alerts.py
输出：inbox\\_parsed.md（供简报步骤阅读），stdout 打印摘要。

为什么要这一步：WOS 邮件是 quoted-printable 编码的 HTML，直接读 .eml 会被
=3D、换行折行和表格标签淹没；且 DOI/作者/日期本来就不在邮件里，只有题名、
期刊名、一段截断摘要和 WOS 入藏号。先做确定性解析，再让模型做判断，
才能保证题名不被读错、入藏号不丢。
"""
import email
import html
import json
import re
import sys
from email.header import decode_header
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).parent
INBOX = BASE / "inbox"
MANUAL = BASE / "manual" / "extra_titles.txt"


def dec(s):
    if not s:
        return ""
    out = []
    for txt, enc in decode_header(s):
        if isinstance(txt, bytes):
            for cand in (enc, "utf-8", "gb18030"):
                if not cand or cand.lower() in ("unknown-8bit", "unknown8bit"):
                    continue
                try:
                    out.append(txt.decode(cand, errors="replace"))
                    break
                except LookupError:
                    continue
            else:
                out.append(txt.decode("utf-8", errors="replace"))
        else:
            out.append(txt)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def html_text(fragment):
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = re.sub(r"<br\s*/?>|</p>|</div>|</tr>|</h[1-6]>|</li>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", " ", t)
    t = html.unescape(t)
    t = t.replace(" ", " ")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n\s*\n+", "\n", t)
    return t.strip()


def unwrap(url):
    """拆 snowplow 跳转，拿到真实 WOS 链接。"""
    try:
        q = parse_qs(urlparse(url).query)
        if "u" in q:
            return unquote(q["u"][0])
    except Exception:
        pass
    return url


def wos_id(link):
    m = re.search(r"full-record/([A-Z]+%3A[^&/?]+|[A-Z]+:[^&/?]+)", link)
    if not m:
        return ""
    return unquote(m.group(1))


def body_text(msg):
    htmls, plains = [], []
    for p in msg.walk():
        ct = p.get_content_type()
        if ct not in ("text/html", "text/plain"):
            continue
        try:
            raw = p.get_payload(decode=True) or b""
            enc = p.get_content_charset() or "utf-8"
            txt = raw.decode(enc, errors="replace")
        except Exception:
            continue
        (htmls if ct == "text/html" else plains).append(txt)
    return htmls[0] if htmls else (plains[0] if plains else "")


RECORD_LINK_RE = re.compile(
    r"<a\b[^>]*href=[\"']([^\"']*full-record[^\"']*)[\"'][^>]*>(.*?)</a>",
    re.I | re.S,
)


def parse_alert(path):
    msg = email.message_from_bytes(path.read_bytes())
    subject = dec(msg.get("Subject", ""))
    try:
        when = parsedate_to_datetime(msg.get("Date", "")).strftime("%Y-%m-%d %H:%M")
    except Exception:
        when = msg.get("Date", "")

    h = body_text(msg)
    text = html_text(h)

    records = []
    matches = list(RECORD_LINK_RE.finditer(h))
    for i, m in enumerate(matches):
        link = unwrap(html.unescape(m.group(1)))
        title = html_text(m.group(2))
        if not title:
            continue
        # 该条记录之后到下一个记录链接之前的可见文本
        seg_end = matches[i + 1].start() if i + 1 < len(matches) else len(h)
        seg = html_text(h[m.end():seg_end])
        seg = re.split(
            r"Showing\s+\d+\s+of\s+the\s+\d+|View all\s+\d+\s+records|You are receiving this email",
            seg,
            maxsplit=1,
            flags=re.I,
        )[0]
        lines = [ln.strip() for ln in seg.split("\n") if ln.strip()]
        venue = lines[0] if lines else ""
        snippet = " ".join(lines[1:]) if len(lines) > 1 else ""
        records.append(
            {
                "title": re.sub(r"\s+", " ", title).strip(),
                "link": link,
                "wos_id": wos_id(link),
                "venue": venue,
                "snippet": re.sub(r"\s+", " ", snippet).strip(),
            }
        )

    total = shown = ""
    m = re.search(r"has\s+(\d+)\s+new records", text, re.I)
    if m:
        total = m.group(1)
    if not total and re.search(r"\b(no|0)\s+new records?\b", text, re.I):
        total = "0"
    m = re.search(r"Showing\s+(\d+)\s+of\s+the\s+(\d+)", text, re.I)
    if m:
        shown, total = m.group(1), m.group(2)
    since = ""
    m = re.search(r"new records since\s*\n?\s*([A-Z][a-z]{2} \d{1,2}(?:st|nd|rd|th)? \d{4})", text)
    if m:
        since = m.group(1)
    query = ""
    m = re.search(r"Your search,\s*(.+?)\s*\n\s*has\s+\d+\s+new records", text, re.S)
    if m:
        query = re.sub(r"\s+", " ", m.group(1)).strip()

    return {
        "file": path.name,
        "subject": subject,
        "date": when,
        "total": total,
        "shown": shown or str(len(records)),
        "since": since,
        "query": query,
        "records": records,
    }


def manual_alert(existing_titles):
    """读 manual/extra_titles.txt：一行一条题名，# 开头为注释。

    邮件只带前 5 条，其余记录在 WOS 页面展开后才能看到；用户把题名粘到这里，
    后续 enrich_crossref.py 会按题名补 DOI 与摘要，与邮件记录合并分诊。
    """
    if not MANUAL.exists():
        return None
    seen = {re.sub(r"[^a-z0-9]+", " ", t.lower()).strip() for t in existing_titles}
    records = []
    for line in MANUAL.read_text(encoding="utf-8-sig").splitlines():
        t = line.strip().lstrip("﻿").lstrip("-*0123456789.、) ").strip()
        if not t or t.startswith("#"):
            continue
        key = re.sub(r"[^a-z0-9]+", " ", t.lower()).strip()
        if key in seen:
            continue
        seen.add(key)
        records.append({"title": t, "link": "", "wos_id": "", "venue": "", "snippet": ""})
    if not records:
        return None
    return {
        "file": "manual/extra_titles.txt",
        "subject": "手工补充（WOS 页面展开的其余记录）",
        "date": "",
        "total": str(len(records)),
        "shown": str(len(records)),
        "since": "",
        "query": "",
        "records": records,
    }


def render(alerts):
    out = ["# WOS Alert 解析结果", ""]
    for a in alerts:
        out.append(f"## {a['file']}")
        out.append(f"- 主题：{a['subject']}")
        if a.get("date"):
            out.append(f"- 接收时间：{a['date']}")
        if a.get("file", "").startswith("manual/"):
            out.append(f"- 来源：手工补充 {a['total']} 条（用户在 WOS 页面展开后粘贴的题名）")
        elif a["total"]:
            out.append(f"- 本轮新记录：{a['total']} 条；邮件正文展示 {a['shown']} 条")
        else:
            out.append("- 本轮新记录：邮件未声明（可能不是 Alert 结果邮件）")
        if a.get("since"):
            out.append(f"- 起算时间：{a['since']}")
        if a.get("query"):
            out.append(f"- 检索式：{a['query']}")
        out.append("")
        for i, r in enumerate(a["records"], 1):
            out.append(f"### R{i}. {r['title']}")
            if r.get("wos_id"):
                out.append(f"- WOS 入藏号：{r['wos_id']}")
            if r.get("venue"):
                out.append(f"- 期刊/来源：{r['venue']}")
            if r.get("snippet"):
                out.append(f"- 摘要片段：{r['snippet']}")
            if r.get("link"):
                out.append(f"- 记录链接：{r['link']}")
            if not any(r.get(k) for k in ("wos_id", "venue", "snippet", "link")):
                out.append("- （手工补充，仅有题名；DOI/摘要由 enrich_crossref.py 补）")
            out.append("")
        out.append("")
    return "\n".join(out)


def main():
    files = sorted(INBOX.glob("*.eml"))
    has_manual = MANUAL.exists() and any(
        ln.strip() and not ln.strip().lstrip("﻿").startswith("#")
        for ln in MANUAL.read_text(encoding="utf-8-sig").splitlines()
    )
    if not files and not has_manual:
        print("[INFO] inbox 为空，manual 也无补充题名")
        return
    alerts = [parse_alert(f) for f in files]
    titles = [r["title"] for a in alerts for r in a["records"]]
    extra = manual_alert(titles)
    if extra:
        alerts.append(extra)

    total_records = sum(len(a["records"]) for a in alerts)
    if total_records == 0:
        subs = "; ".join(a["subject"][:60] for a in alerts) or "（无邮件）"
        print(f"[PARSE] 本轮 0 条记录，空提醒/非结果邮件（{subs}），不生成简报")
        sys.exit(4)

    md = render(alerts)
    (INBOX / "_parsed.md").write_text(md, encoding="utf-8")
    (INBOX / "_parsed.json").write_text(
        json.dumps(alerts, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    n = sum(len(a["records"]) for a in alerts)
    manual = sum(1 for a in alerts if str(a.get("file", "")).startswith("manual/"))
    print(f"[PARSE] {len(alerts) - manual} 封邮件 + {manual} 份手工补充，"
          f"共 {n} 条记录 -> inbox\\_parsed.md")


if __name__ == "__main__":
    main()
