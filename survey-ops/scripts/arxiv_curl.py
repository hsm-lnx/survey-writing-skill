# -*- coding: utf-8 -*-
"""
arXiv layer via curl (arXiv throttles urllib's TLS fingerprint with HTTP 406;
curl is served normally). Reuses comparison logic from verify_round1.

Usage: python scripts/arxiv_curl.py <n1> <n2> ... <out.json>
       n* are entry numbers in scripts/entries_rest.json with an "arxiv" field.
"""
import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from verify_round1 import compare, crossref_query, norm_words, re

ATOM = "{http://www.w3.org/2005/Atom}"

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def fetch_arxiv_curl(aid):
    for attempt in range(3):
        r = subprocess.run(
            ["curl", "-s", "-m", "30",
             f"https://export.arxiv.org/api/query?id_list={aid}&max_results=1"],
            capture_output=True)
        text = r.stdout.decode("utf-8", errors="replace")
        if "<entry" in text:
            try:
                return text, 200
            except Exception:
                pass
        time.sleep(5)
    return text if 'r' in dir() else "", "error"


def parse_arxiv(text, aid):
    root = ET.fromstring(text)
    entry = root.find(ATOM + "entry")
    if entry is None:
        return {"status": "NOT_FOUND"}
    t_el = entry.find(ATOM + "title")
    title = (t_el.text or "").strip() if t_el is not None else ""
    if title.strip().casefold() == "error" or not title:
        return {"status": "NOT_FOUND"}
    authors = []
    for a in entry.findall(ATOM + "author"):
        n_el = a.find(ATOM + "name")
        if n_el is not None and n_el.text:
            parts = n_el.text.strip().split()
            authors.append({"given": parts[0] if parts else "",
                            "family": " ".join(parts[1:]) or (parts[0] if parts else ""),
                            "name": n_el.text.strip()})
    pub = (entry.find(ATOM + "published").text or "")[:10] if entry.find(ATOM + "published") is not None else None
    upd = (entry.find(ATOM + "updated").text or "")[:10] if entry.find(ATOM + "updated") is not None else None
    return {"status": "OK", "title": re.sub(r"\s+", " ", title), "authors": authors,
            "v1_date": pub, "updated_date": upd,
            "years": sorted({int(pub[:4]) if pub else None, int(upd[:4]) if upd else None} - {None})}


def main():
    ns = [int(x) for x in sys.argv[1:-1]]
    out_path = sys.argv[-1]
    here = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(here, "entries_rest.json"), encoding="utf-8") as f:
        entries = {e["n"]: e for e in json.load(f)}

    results = []
    for n in ns:
        e = entries[n]
        aid = e.get("arxiv") or (e.get("doi") or "").split("arXiv.")[-1]
        text, status = fetch_arxiv_curl(aid)
        out = {"n": n, "stated_doi": e.get("doi"), "mode": "arxiv", "arxiv_id": aid,
               "note": e.get("note")}
        if status != 200:
            out["arxiv"] = {"status": f"API_ERROR_{status}"}
            out["proposed"] = out["arxiv"]["status"]
            results.append(out)
            print(f"[{n}] API_ERROR_{status}")
            time.sleep(3)
            continue
        ax = parse_arxiv(text, aid)
        out["arxiv"] = ax
        rec = None
        if ax["status"] == "OK":
            rec = {"doi": None, "title": ax["title"], "container": "arXiv (preprint)",
                   "short_container": None, "authors": ax["authors"], "years": ax["years"],
                   "print_year": None, "online_year": None, "volume": None, "issue": None,
                   "page": None, "article_number": None, "type": "preprint",
                   "publisher": "arXiv", "cited_by_crossref": None,
                   "url": f"https://arxiv.org/abs/{aid}"}
            _, pubhits = crossref_query({"query.bibliographic": e["raw"]["title"], "rows": 3,
                                         "select": "DOI,title,container-title,issued"})
            for ph in pubhits:
                if norm_words(ph["title"]) == norm_words(e["raw"]["title"]):
                    out["published_version"] = {"doi": ph["doi"], "container": ph["container"],
                                                "year": ph["years"][0] if ph["years"] else None}
                    break
            time.sleep(1)
        if rec is not None:
            fields, hard = compare(e, rec)
            out["fields"] = fields
            out["mismatch_fields"] = hard
            out["proposed"] = "OK" if not hard else "MISMATCH"
        else:
            out["proposed"] = ax["status"]
        results.append(out)
        print(f"[{n}] proposed={out['proposed']}"
              + (f" mismatch={hard}" if rec is not None and hard else "")
              + (f" | published: {out['published_version']['doi']}" if "published_version" in out else ""))
        time.sleep(3)

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"saved -> {out_path}")


if __name__ == "__main__":
    main()
