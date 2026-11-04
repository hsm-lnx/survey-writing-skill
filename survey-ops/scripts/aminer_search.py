# -*- coding: utf-8 -*-
"""
Round-1 verification -- AMiner layer.

Endpoint: POST https://searchtest.aminer.cn/aminer-search/search/publicationV2
          (the search gateway behind aminer.cn's own search UI; free, Bearer token
           from env AMINER_API_KEY).

Processes every entry whose Crossref-layer result is PENDING_AMINER (no DOI / no arXiv id,
and Crossref bibliographic query found nothing convincing). Every query string tried is
recorded in the output so that NOT_FOUND verdicts can list their full search evidence.

Usage:
    python scripts/aminer_search.py <entries.json> <aminer_out.json> <verify_out1.json> [<verify_out2.json> ...]
"""
import difflib
import json
import os
import re
import sys
import time
import urllib.request

URL = "https://searchtest.aminer.cn/aminer-search/search/publicationV2"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_round1 import norm_words  # reuse normalization

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def aminer_query(q, size=5):
    key = os.environ.get("AMINER_API_KEY")
    if not key:
        raise SystemExit("AMINER_API_KEY not set")
    body = json.dumps({"query": q, "needDetails": True, "page": 0, "size": size},
                      ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(URL, data=body, headers={
        "Content-Type": "application/json; charset=utf-8",
        "Authorization": "Bearer " + key,
    })
    with urllib.request.urlopen(req, timeout=30) as r:
        d = json.loads(r.read().decode("utf-8"))
    dd = d.get("data") or {}
    hits = []
    for h in dd.get("hitList") or []:
        authors = []
        for a in h.get("authors") or []:
            nm = a.get("name") or a.get("nameZh") or a.get("nameEn") or ""
            if nm:
                authors.append(nm)
        venue = h.get("venue") or {}
        hits.append({
            "id": h.get("id"),
            "title": h.get("title"),
            "titleZh": h.get("titleZh"),
            "year": h.get("year"),
            "authors": authors,
            "venue": venue.get("raw"),
            "venue_type": venue.get("t"),
            "volume": h.get("volume"),
            "issue": h.get("issue"),
            "pageString": h.get("pageString"),
            "doi": h.get("doi"),
            "ncitation": h.get("ncitation"),
            "issn": h.get("issn"),
            "url": h.get("url"),
        })
    return dd.get("hitsTotal"), hits


def hit_ratio(entry, hit):
    t = norm_words(entry["raw"]["title"])
    best, field = 0.0, None
    for f in ("titleZh", "title"):
        if hit.get(f):
            r = difflib.SequenceMatcher(None, t, norm_words(hit[f])).ratio()
            if r > best:
                best, field = r, f
    return best, field


def short_title(title):
    """Strip subtitle / punctuation for a second-chance keyword query."""
    t = re.split(r"[:：]", title)[0].strip() if re.search(r"[:：]", title) else title
    return t


def search_entry(entry):
    raw = entry["raw"]
    queries, all_hits = [], []
    tried = []
    title = raw["title"]
    tried.append(("完整标题", title))
    if short_title(title).lower() != title.lower():
        tried.append(("主标题（去副标题）", short_title(title)))
    if not raw.get("authors"):
        kws = [w for w in norm_words(title).split() if len(w) > 3][:6]
        if kws:
            tried.append(("标题关键词", " ".join(kws)))
    if raw.get("authors"):
        fam = raw["authors"][0]
        tried.append(("第一作者 + 主标题", f"{fam} {short_title(title)}"))
        kws = [w for w in norm_words(title).split() if len(w) > 3][:4]
        if kws:
            tried.append(("第一作者 + 标题关键词", f"{fam} {' '.join(kws[:2])}"))
    seen_ids = set()
    total = None
    for label, q in tried:
        try:
            tot, hits = aminer_query(q, size=5)
        except Exception as e:
            queries.append({"strategy": label, "query_string": q, "error": repr(e)})
            time.sleep(1)
            continue
        queries.append({"strategy": label, "query_string": q, "hitsTotal": tot})
        total = tot if total is None else total
        for h in hits:
            if h["id"] not in seen_ids:
                seen_ids.add(h["id"])
                r, field = hit_ratio(entry, h)
                all_hits.append({**h, "match": {"ratio": round(r, 3), "matched_field": field,
                                                "year": h.get("year")}})
        if all_hits and max(h["match"]["ratio"] for h in all_hits) >= 0.85:
            break  # good hit found; later strategies unnecessary
        time.sleep(1)
    all_hits.sort(key=lambda h: -h["match"]["ratio"])
    return {"n": entry["n"], "queries": queries, "hitsTotal_first_query": total,
            "top_hits": all_hits[:3],
            "proposed": ("AMINER_MATCH" if all_hits and all_hits[0]["match"]["ratio"] >= 0.85
                         else "AMINER_CANDIDATES" if all_hits and all_hits[0]["match"]["ratio"] >= 0.6
                         else "NOT_FOUND")}


def main():
    entries_path, out_path = sys.argv[1], sys.argv[2]
    verify_paths = sys.argv[3:]
    with open(entries_path, encoding="utf-8") as f:
        entries = {e["n"]: e for e in json.load(f)}
    pending = set()
    for vp in verify_paths:
        with open(vp, encoding="utf-8") as f:
            for r in json.load(f):
                if r.get("proposed") in ("PENDING_AMINER", "REVIEW_CANDIDATES"):
                    pending.add(r["n"])
    results = []
    for n in sorted(pending):
        e = entries[n]
        res = search_entry(e)
        results.append(res)
        top = res["top_hits"][0] if res["top_hits"] else None
        print(f"[{n}] {res['proposed']}"
              + (f" ratio={top['match']['ratio']} <- {top.get('titleZh') or top.get('title')}" if top else "")
              + f" | queries_tried={len(res['queries'])}")
        time.sleep(1)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"saved -> {out_path} ({len(results)} entries)")


if __name__ == "__main__":
    main()
