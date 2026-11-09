# -*- coding: utf-8 -*-
"""算法名／术语扩展检索：补「主题词写法不同」造成的漏检。

主检索通常用「主题词 AND 方法词」。但有些研究全篇只写具体算法名或同义
表述，不写主题词，按主题词检索会漏。本脚本用一组算法名/同义表述做扩展
检索，再把结果与台账/正文做差集。

默认三组查询是强化学习焊接的示例；换主题时用 --query NAME=QUERY 覆盖。

用法：
  python algo_name_search.py --ledger bib/verified.md --manuscript manuscript/正文.md
  python algo_name_search.py --query "A=welding AND (DQN OR PPO)" \
      --query "B=weld AND \"reinforcement learning\"" --years 2015-2026

只出池外候选，不作准入判定。
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_common as sc  # noqa: E402

DEFAULT_QUERIES = {
    "A_algo_acronym": 'welding AND ("Q-learning" OR DQN OR PPO OR SAC OR TD3 OR DDPG OR "actor-critic" OR A2C OR A3C)',
    "B_algo_long": 'weld AND ("deep reinforcement learning" OR "reinforcement learning") AND (sequence OR bead OR penetration OR distortion OR "welding parameters")',
    "C_drl_topic": '(weld OR welding) AND "deep reinforcement learning"',
}


def fetch_query(query, years, max_records, sleep):
    records = []
    cursor = "*"
    while cursor and len(records) < max_records:
        _, page = sc.openalex_get("/works", {
            "filter": "title_and_abstract.search:%s,publication_year:%s" % (query, years),
            "per-page": "200",
            "cursor": cursor,
            "select": "id,doi,title,publication_year,type,primary_location,abstract_inverted_index",
        })
        batch = page.get("results", [])
        records.extend(batch)
        cursor = (page.get("meta") or {}).get("next_cursor")
        if not batch or not cursor:
            break
        time.sleep(sleep)
    return records


def main():
    ap = argparse.ArgumentParser(description="算法名／术语扩展检索")
    ap.add_argument("--query", action="append", default=[],
                    help="NAME=QUERY，可重复；不给则用内置三组示例")
    ap.add_argument("--years", default="2015-2026")
    ap.add_argument("--max-per-query", type=int, default=800)
    ap.add_argument("--signal", default=sc.DEFAULT_SIGNAL_RE.pattern)
    ap.add_argument("--topic-words", default=",".join(sc.DEFAULT_TOPIC_WORDS))
    ap.add_argument("--ledger", default="bib/verified.md")
    ap.add_argument("--manuscript", default="")
    ap.add_argument("--sleep", type=float, default=0.2)
    ap.add_argument("--out", default="reports/_raw/algo_name_search_%s.json" % sc.today_stamp())
    args = ap.parse_args()

    queries = dict(DEFAULT_QUERIES)
    if args.query:
        queries = {}
        for item in args.query:
            if "=" not in item:
                ap.error("--query 须写成 NAME=QUERY：%s" % item)
            name, q = item.split("=", 1)
            queries[name.strip()] = q.strip()

    signal_re = _compile(args.signal)
    topic_words = [w.strip() for w in args.topic_words.split(",") if w.strip()]
    known = sc.known_dois([args.ledger, args.manuscript])

    raw, seen = {}, {}
    for name, query in queries.items():
        try:
            raw[name] = fetch_query(query, args.years, args.max_per_query, args.sleep)
        except Exception as e:
            raw[name] = []
            print("[warn] %s ERROR %r" % (name, e))
        print("[%s] %d records" % (name, len(raw[name])))

        for w in raw[name]:
            doi = sc.norm_doi(w.get("doi"))
            title = w.get("title") or ""
            abstract = sc.abstract_of(w.get("abstract_inverted_index"))
            blob = title + " " + abstract
            if not (signal_re.search(blob) and sc.contains_any(blob, topic_words)):
                continue
            key = doi or ("t" + sc.norm_title(title))
            if key in seen:
                if name not in seen[key]["queries"]:
                    seen[key]["queries"].append(name)
                continue
            source = (w.get("primary_location") or {}).get("source") or {}
            seen[key] = {
                "doi": doi,
                "title": title,
                "year": w.get("publication_year"),
                "venue": source.get("display_name"),
                "type": w.get("type"),
                "oa_id": w.get("id"),
                "known": bool(doi) and doi in known,
                "queries": [name],
            }

    relevant = list(seen.values())
    new = [r for r in relevant if not r["known"]]
    new.sort(key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))
    print("\nsignal+topic relevant: %d | known: %d | OUT-OF-POOL: %d" % (
        len(relevant), len(relevant) - len(new), len(new)))
    for r in new:
        print("%s | %s | %s | %s | %s" % (
            r.get("year"), (r.get("title") or "")[:82], r.get("type"),
            r.get("doi"), r.get("venue")))

    sc.save_json(args.out, {
        "run_date": sc.today_stamp(),
        "queries": queries,
        "fetched": {k: len(v) for k, v in raw.items()},
        "relevant": relevant,
        "out_of_pool": new,
    })
    print("\nsaved=%s" % args.out)


def _compile(pattern):
    import re
    return re.compile(pattern, re.I)


if __name__ == "__main__":
    main()
