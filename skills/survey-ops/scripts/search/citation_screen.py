# -*- coding: utf-8 -*-
"""前向被引筛选：去重、按主题词初筛、与台账/正文做差集。

输入是 citation_chase.py 的原始返回。输出两份清单：
- candidates：题名含主题词、且不在台账/正文 DOI 集里的池外候选；
- known：题名含主题词但已经出现过的记录（留档，避免下次重判）。

只出候选，不作准入判定。

用法：
  python citation_screen.py --raw reports/_raw/citation_chase.json \
      --ledger bib/verified.md --manuscript manuscript/正文.md \
      --out reports/_raw/citation_chase_screen.json
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_common as sc  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="前向被引去重与主题词初筛")
    ap.add_argument("--raw", required=True, help="citation_chase.py 的输出")
    ap.add_argument("--ledger", default="bib/verified.md")
    ap.add_argument("--manuscript", default="", help="正文 md，用于排除已引记录")
    ap.add_argument("--topic-words", default=",".join(sc.DEFAULT_TOPIC_WORDS),
                    help="题名初筛词，逗号分隔（默认焊接词表）")
    ap.add_argument("--out", default="reports/_raw/citation_chase_screen_%s.json" % sc.today_stamp())
    args = ap.parse_args()

    data = sc.load_json(args.raw)
    topic_words = [w.strip() for w in args.topic_words.split(",") if w.strip()]
    known = sc.known_dois([args.ledger, args.manuscript])

    seen = {}
    for label, rec in (data.get("targets") or {}).items():
        for c in rec.get("citing", []):
            doi = sc.norm_doi(c.get("doi"))
            title = c.get("title") or ""
            key = doi or ("t" + sc.norm_title(title))
            if not key:
                continue
            if key in seen:
                seen[key]["citing"].add(label)
                continue
            source = (c.get("primary_location") or {}).get("source") or {}
            seen[key] = {
                "doi": doi,
                "title": title,
                "year": c.get("publication_year"),
                "venue": source.get("display_name"),
                "type": c.get("type"),
                "oa_id": c.get("id"),
                "known": bool(doi) and doi in known,
                "citing": {label},
            }

    topic_hits = []
    for rec in seen.values():
        if sc.contains_any(rec["title"], topic_words):
            rec["citing"] = sorted(rec["citing"])
            topic_hits.append(rec)

    candidates = [r for r in topic_hits if not r["known"]]
    known_hits = [r for r in topic_hits if r["known"]]
    candidates.sort(key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))

    print("citing records total : %d" % len(seen))
    print("topic-related        : %d" % len(topic_hits))
    print("  already known      : %d" % len(known_hits))
    print("  OUT-OF-POOL        : %d" % len(candidates))
    print()
    for r in candidates:
        print("%s | %s | %s | %s | via %s" % (
            r.get("year"), (r.get("title") or "")[:95], r.get("venue"),
            r.get("doi"), ",".join(r["citing"])))

    sc.save_json(args.out, {"candidates": candidates, "known": known_hits})
    print("\nsaved=%s" % args.out)


if __name__ == "__main__":
    main()
