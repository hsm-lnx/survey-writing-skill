# -*- coding: utf-8 -*-
r"""按题名向 Crossref 找 DOI，再按 DOI 取完整著录与摘要，并与台账对重。

用法：
    python enrich_crossref.py                    # 读 inbox\_parsed.json
    python enrich_crossref.py --input <_parsed.json> --out-dir <dir>

输出：
    <out-dir>\_enriched.md   供简报步骤阅读
    <out-dir>\_enriched.json 机器可读
    state\raw_crossref\<日期>\*.json   原始返回，便于复核

设计要点：
- 两步走：query.bibliographic 找候选 DOI → works/{DOI} 取权威著录。
  邮件本身没有 DOI/作者/日期，这一步把它们补齐。
- 题名相似度打分，>=0.97 视为匹配，0.90–0.97 标"待核"，<0.90 不采用；
  不因模糊匹配把 A 论文的 DOI 安到 B 论文头上。
- 摘要 Crossref 常缺，缺时用 OpenAlex 的 inverted index 还原；两者都没有就写"未取到"。
- 与 ..\bib\verified.md 做 DOI 精确 + 题名子串双重对重；命中即标"已引[n]"。
- 网络失败不编造：逐条记 status，全部失败时退出码 2，由调度器决定是否继续。
"""
import argparse
import difflib
import html
import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

BASE = Path(__file__).parent
CONFIG = BASE / "config.json"
DEFAULT_LEDGER = BASE.parent / "bib" / "verified.md"
DEFAULT_MANUSCRIPT_GLOBS = ("manuscript/*.md", "docs/*.md")
UA = "survey-manager-daily/1.0 (mailto:audit@example.org)"
SELECT = ("DOI,title,author,container-title,issued,published,published-print,"
          "published-online,type,volume,issue,page,publisher,abstract,"
          "is-referenced-by-count,subject")


def norm(s):
    s = html.unescape(s or "").lower()
    s = re.sub(r"<[^>]+>", " ", s)
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def similarity(a, b):
    na, nb = norm(a), norm(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def fetch_json(url, timeout=30, tries=3):
    last = ""
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read()), "ok"
        except urllib.error.HTTPError as e:
            last = f"HTTP {e.code}"
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(2 + 3 * i)
                continue
            return None, last
        except Exception as e:
            last = type(e).__name__
            time.sleep(1 + 2 * i)
    return None, last


def strip_jats(s):
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s)
    return re.sub(r"\s+", " ", s).strip()


def crossref_search(title):
    params = {
        "query.bibliographic": title,
        "rows": "6",
        "select": SELECT,
    }
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(params)
    data, status = fetch_json(url)
    if not data:
        return [], status, url
    out = []
    for it in data.get("message", {}).get("items", []):
        t = (it.get("title") or [""])[0]
        out.append({
            "doi": it.get("DOI", ""),
            "title": strip_jats(t),
            "score": similarity(title, t),
            "venue": (it.get("container-title") or [""])[0],
            "year": ((it.get("issued") or {}).get("date-parts") or [[None]])[0][0],
            "type": it.get("type", ""),
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out, status, url


def crossref_work(doi):
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    data, status = fetch_json(url)
    if not data:
        return None, status, url
    return data.get("message", {}), status, url


def openalex_abstract(doi):
    url = f"https://api.openalex.org/works/doi:{urllib.parse.quote(doi, safe='')}?mailto=audit@example.org"
    data, status = fetch_json(url, tries=2)
    if not data:
        return "", status, url
    inv = data.get("abstract_inverted_index")
    if not inv:
        return "", status, url
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    return " ".join(pos[i] for i in sorted(pos)), status, url


def authors_text(work):
    names = []
    for a in work.get("author") or []:
        fam = (a.get("family") or "").strip()
        giv = (a.get("given") or "").strip()
        if fam and giv:
            names.append(f"{fam} {giv}")
        elif fam or giv:
            names.append(fam or giv)
        elif a.get("name"):
            names.append(a["name"])
    return "; ".join(names)


def date_text(work):
    for key in ("published-print", "published-online", "issued", "published"):
        dp = (work.get(key) or {}).get("date-parts") or []
        if dp and dp[0] and dp[0][0]:
            return "-".join(str(x) for x in dp[0] if x is not None)
    return ""


def load_config():
    if not CONFIG.exists():
        return {}
    try:
        return json.loads(CONFIG.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[WARN] config.json 读取失败：{e}，使用默认路径")
        return {}


def resolve_path(raw, default):
    if not raw:
        return default
    p = Path(raw)
    return p if p.is_absolute() else (BASE.parent / p)


def load_ledger(path=None):
    path = Path(path) if path else DEFAULT_LEDGER
    entries = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\[(\d+)\]\s*\|\s*(.*)$", line.strip())
        if not m:
            continue
        body = m.group(2)
        dm = re.search(r"DOI:\s*([^\s，,；;]+)", body, re.I)
        entries.append({
            "n": int(m.group(1)),
            "doi": (dm.group(1).rstrip(".").lower() if dm else ""),
            "norm": norm(body),
            "line": body[:160],
        })
    return entries


def ledger_hit(doi, title, entries):
    if doi:
        for e in entries:
            if e["doi"] and e["doi"] == doi.lower():
                return e, "DOI 精确"
    nt = norm(title)
    if len(nt) >= 25:
        for e in entries:
            if nt in e["norm"]:
                return e, "题名子串"
    return None, ""


def load_prior_briefs(today_str):
    """之前的简报正文，用于跨天去重；排除今天的（当天重跑不自我抑制）。"""
    out = []
    bdir = BASE / "brief"
    if not bdir.exists():
        return out
    for p in sorted(bdir.glob("*.md")):
        if p.stem == today_str:
            continue
        try:
            out.append((p.stem, p.read_text(encoding="utf-8", errors="replace")))
        except Exception:
            continue
    return out


def prior_brief_hit(doi, title, briefs):
    dates = []
    nt = norm(title)
    for d, text in briefs:
        if doi and doi.lower() in text.lower():
            dates.append(d)
            continue
        if len(nt) >= 25 and nt in norm(text):
            dates.append(d)
    return dates


def load_manuscripts(cfg):
    """按 config.manuscript_globs 扫描正文，返回归一化文本列表。"""
    patterns = cfg.get("manuscript_globs") or DEFAULT_MANUSCRIPT_GLOBS
    root = BASE.parent
    out = []
    for pat in patterns:
        if not isinstance(pat, str) or not pat.strip():
            continue
        p = Path(pat)
        try:
            matches = sorted(p.parent.glob(p.name)) if p.is_absolute() else sorted(root.glob(pat))
        except (OSError, ValueError):
            continue
        for f in matches:
            if not f.is_file() or f.suffix.lower() not in (".md", ".txt"):
                continue
            try:
                if f.stat().st_size > 8 * 1024 * 1024:
                    print(f"[WARN] 正文文件过大，跳过：{f}")
                    continue
                out.append(norm(f.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return out


def manuscript_hit(title, manuscript_norms):
    nt = norm(title)
    if len(nt) < 25:
        return False
    return any(nt in body for body in manuscript_norms)


def title_checks(out, title, entries, briefs, manuscript_norms):
    """无可靠 DOI 时，仍按题名做台账、正文与历史简报检查。"""
    e, how = ledger_hit("", title, entries)
    if e:
        out["ledger_n"] = e["n"]
        out["ledger_how"] = how
    out["in_manuscript"] = manuscript_hit(title, manuscript_norms)
    out["prior_briefs"] = prior_brief_hit("", title, briefs)


def enrich_record(rec, idx, entries, raw_dir, briefs, manuscript_norms=()):
    title = rec.get("title", "")
    out = {
        "index": idx,
        "email_title": title,
        "wos_id": rec.get("wos_id", ""),
        "email_venue": rec.get("venue", ""),
        "email_snippet": rec.get("snippet", ""),
        "link": rec.get("link", ""),
        "match_status": "unmatched",
        "match_score": 0.0,
        "doi": "",
        "title": "",
        "venue": "",
        "year": "",
        "date": "",
        "type": "",
        "volume": "",
        "issue": "",
        "page": "",
        "publisher": "",
        "authors": "",
        "cited_by": "",
        "abstract": "",
        "abstract_source": "",
        "ledger_n": None,
        "ledger_how": "",
        "in_manuscript": False,
        "prior_briefs": [],
        "query_status": "",
    }
    cands, st, qurl = crossref_search(title)
    out["query_status"] = st
    (raw_dir / f"q{idx:02d}.json").write_text(
        json.dumps({"url": qurl, "candidates": cands}, ensure_ascii=False, indent=1),
        encoding="utf-8",
    )
    if not cands:
        title_checks(out, title, entries, briefs, manuscript_norms)
        return out

    best = cands[0]
    out["match_score"] = round(best["score"], 3)
    if best["score"] >= 0.97:
        out["match_status"] = "matched"
    elif best["score"] >= 0.90:
        out["match_status"] = "probable"
    else:
        title_checks(out, title, entries, briefs, manuscript_norms)
        return out

    doi = best["doi"]
    out["doi"] = doi
    work, st2, wurl = crossref_work(doi)
    if work:
        out["title"] = strip_jats((work.get("title") or [""])[0])
        out["venue"] = (work.get("container-title") or [""])[0]
        out["year"] = ((work.get("issued") or {}).get("date-parts") or [[None]])[0][0]
        out["date"] = date_text(work)
        out["type"] = work.get("type", "")
        out["volume"] = work.get("volume", "")
        out["issue"] = work.get("issue", "")
        out["page"] = work.get("page", "")
        out["publisher"] = work.get("publisher", "")
        out["authors"] = authors_text(work)
        out["cited_by"] = work.get("is-referenced-by-count", "")
        out["abstract"] = strip_jats(work.get("abstract", ""))
        if out["abstract"]:
            out["abstract_source"] = "Crossref"
        (raw_dir / f"works_{re.sub(r'[^A-Za-z0-9]+', '_', doi)}.json").write_text(
            json.dumps({"url": wurl, "work": work}, ensure_ascii=False, indent=1),
            encoding="utf-8",
        )
    if not out["abstract"]:
        abs_text, st3, aurl = openalex_abstract(doi)
        if abs_text:
            out["abstract"] = abs_text
            out["abstract_source"] = "OpenAlex"
            (raw_dir / f"openalex_{re.sub(r'[^A-Za-z0-9]+', '_', doi)}.json").write_text(
                json.dumps({"url": aurl, "abstract": abs_text}, ensure_ascii=False, indent=1),
                encoding="utf-8",
            )

    e, how = ledger_hit(doi, out["title"] or title, entries)
    if e:
        out["ledger_n"] = e["n"]
        out["ledger_how"] = how
    out["in_manuscript"] = manuscript_hit(out["title"] or title, manuscript_norms)
    out["prior_briefs"] = prior_brief_hit(doi, out["title"] or title, briefs)
    return out


def render(alerts, enriched):
    lines = ["# WOS 记录补全结果（Crossref / OpenAlex）", ""]
    for a in alerts:
        lines.append(f"## {a['file']}")
        lines.append(f"- 主题：{a['subject']}")
        if str(a.get("file", "")).startswith("manual/"):
            lines.append(f"- 来源：手工补充 {a.get('total','')} 条")
        elif a.get("total"):
            lines.append(f"- 本轮新记录：{a.get('total','')} 条；邮件展示 {a.get('shown','')} 条")
        lines.append("")
        for e in enriched:
            if e.get("_alert") != a["file"]:
                continue
            lines.append(f"### R{e['index']}. {e['email_title']}")
            lines.append(f"- WOS 入藏号：{e['wos_id'] or '（无）'}")
            lines.append(f"- 邮件期刊：{e['email_venue'] or '（无）'}")
            if e["doi"]:
                lines.append(f"- DOI：{e['doi']}")
                lines.append(f"- Crossref 匹配：{e['match_status']}（相似度 {e['match_score']}）")
                lines.append(f"- Crossref 题名：{e['title']}")
                lines.append(f"- 作者：{e['authors'] or '未取到'}")
                lines.append(f"- 期刊 / 日期：{e['venue'] or '未取到'}｜{e['date'] or e['year'] or '未取到'}")
                lines.append(f"- 卷期页：{e['volume'] or '—'}（{e['issue'] or '—'}）：{e['page'] or '—'}")
                lines.append(f"- 类型 / 被引：{e['type'] or '—'}｜{e['cited_by']}")
                lines.append(f"- 摘要（{e['abstract_source'] or '未取到'}）：{e['abstract'] or '未取到'}")
            else:
                lines.append("- DOI：未匹配（Crossref 候选中无足够相似题名）")
                lines.append(f"- 匹配状态：{e['match_status']}（最高相似度 {e['match_score']}）")
                lines.append(f"- 摘要片段（仅邮件）：{e['email_snippet'] or '（无）'}")
            if e["ledger_n"]:
                lines.append(f"- 台账：**已引〔{e['ledger_n']}〕**（{e['ledger_how']}）")
            else:
                lines.append("- 台账：未入账")
            lines.append(f"- 正文：{'题名已出现' if e['in_manuscript'] else '未出现'}")
            if e["prior_briefs"]:
                lines.append(f"- 历史简报：{'、'.join(e['prior_briefs'][-3:])} 已出现（非新增）")
            else:
                lines.append("- 历史简报：未出现")
            if e["link"]:
                lines.append(f"- 记录链接：{e['link']}")
            lines.append("")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(BASE / "inbox" / "_parsed.json"))
    ap.add_argument("--out-dir", default=str(BASE / "inbox"))
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        print(f"[SKIP] 找不到 {inp}，先跑 parse_alerts.py")
        return
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    alerts = json.loads(inp.read_text(encoding="utf-8"))
    cfg = load_config()
    ledger_path = resolve_path(cfg.get("ledger_path"), DEFAULT_LEDGER)
    entries = load_ledger(ledger_path)
    manuscript_norms = load_manuscripts(cfg)
    briefs = load_prior_briefs(date.today().isoformat())
    print(f"[INFO] 台账：{ledger_path}（{len(entries)} 条）")
    print(f"[INFO] 正文：{len(manuscript_norms)} 个文件参与对重")
    raw_dir = BASE / "state" / "raw_crossref" / date.today().isoformat()
    raw_dir.mkdir(parents=True, exist_ok=True)

    enriched = []
    failures = 0
    for a in alerts:
        for i, rec in enumerate(a.get("records", []), 1):
            e = enrich_record(rec, i, entries, raw_dir, briefs, manuscript_norms)
            e["_alert"] = a["file"]
            enriched.append(e)
            if e["query_status"] != "ok":
                failures += 1
            print(f"[{e['match_status']:9}] R{i} {rec.get('wos_id','')} "
                  f"{'DOI=' + e['doi'] if e['doi'] else '无DOI'} | {e['email_title'][:60]}")
            time.sleep(0.4)

    (out_dir / "_enriched.md").write_text(render(alerts, enriched), encoding="utf-8")
    (out_dir / "_enriched.json").write_text(
        json.dumps(enriched, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    ok = sum(1 for e in enriched if e["match_status"] in ("matched", "probable"))
    print(f"[ENRICH] {len(enriched)} 条，匹配 {ok} 条，查询失败 {failures} 条 -> {out_dir}\\_enriched.md")
    if failures == len(enriched) and enriched:
        print("[ENRICH] 全部查询失败（网络不可用？），简报应退回 _parsed.md")
        sys.exit(2)


if __name__ == "__main__":
    main()
