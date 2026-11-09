# -*- coding: utf-8 -*-
"""给池外候选补摘要，并按信号词判定是否值得人工判读。

输入是 citation_screen.py 的 candidates（也可直接给任何含 doi/title/oa_id 的
JSON 列表）。优先用 OpenAlex 摘要；加 --crossref-fallback 时，对仍无摘要的
DOI 逐条查 Crossref。Crossref 的 abstract 字段并非每篇都有，拿不到就如实
记「无摘要」，不得据此判「无关」。

只出候选，不作准入判定。

用法：
  python citation_abstracts.py --candidates reports/_raw/citation_chase_screen.json \
      --signal "reinforcement learning|强化学习" \
      --out reports/_raw/citation_chase_abstracts.json
"""
import argparse
import os
import re
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_common as sc  # noqa: E402


def load_candidates(path):
    data = sc.load_json(path)
    if isinstance(data, list):
        return data
    return data.get("candidates") or []


def enrich_openalex(cands, batch_size, sleep):
    by_id = [c for c in cands if c.get("oa_id")]
    by_doi = [c for c in cands if not c.get("oa_id") and c.get("doi")]
    fetched = 0

    for i in range(0, len(by_id), batch_size):
        chunk = by_id[i:i + batch_size]
        ids = [str(c["oa_id"]).rstrip("/").rsplit("/", 1)[-1] for c in chunk]
        try:
            _, page = sc.openalex_get("/works", {
                "filter": "openalex_id:" + "|".join(ids),
                "per-page": str(batch_size),
                "select": "id,doi,title,publication_year,abstract_inverted_index,type",
            })
        except Exception as e:
            print("[warn] OpenAlex batch %d: %r" % (i, e))
            continue
        got = {}
        for w in page.get("results", []):
            got[str(w.get("id", "")).rstrip("/").rsplit("/", 1)[-1]] = w
        for c in chunk:
            wid = str(c["oa_id"]).rstrip("/").rsplit("/", 1)[-1]
            w = got.get(wid)
            if w:
                c["abstract"] = sc.abstract_of(w.get("abstract_inverted_index"))
                c["abs_src"] = "openalex"
                fetched += bool(c["abstract"])
        time.sleep(sleep)

    for i in range(0, len(by_doi), batch_size):
        chunk = by_doi[i:i + batch_size]
        dois = [sc.norm_doi(c["doi"]) for c in chunk if c.get("doi")]
        if not dois:
            continue
        try:
            _, page = sc.openalex_get("/works", {
                "filter": "doi:" + "|".join(dois),
                "per-page": str(batch_size),
                "select": "id,doi,title,publication_year,abstract_inverted_index,type",
            })
        except Exception as e:
            print("[warn] OpenAlex batch %d: %r" % (i, e))
            continue
        got = {sc.norm_doi(w.get("doi")): w for w in page.get("results", [])}
        for c in chunk:
            w = got.get(sc.norm_doi(c.get("doi")))
            if w:
                c["abstract"] = sc.abstract_of(w.get("abstract_inverted_index"))
                c["abs_src"] = "openalex"
                if not c.get("oa_id"):
                    c["oa_id"] = w.get("id")
                fetched += bool(c["abstract"])
        time.sleep(sleep)
    return fetched


def enrich_crossref(cands, sleep):
    fetched = 0
    for i, c in enumerate(cands):
        if c.get("abstract") or not c.get("doi"):
            continue
        try:
            path = "/works/" + urllib.parse.quote(c["doi"], safe="/")
            data = sc.crossref_get(path, {})
            msg = data.get("message") or {}
            abstract = sc.strip_tags(msg.get("abstract") or "")
            if abstract:
                c["abstract"] = abstract
                c["abs_src"] = "crossref"
                fetched += 1
        except Exception:
            pass
        time.sleep(sleep)
        if (i + 1) % 50 == 0:
            print("  crossref fallback %d/%d, abstracts %d" % (i + 1, len(cands), fetched))
    return fetched


def main():
    ap = argparse.ArgumentParser(description="补摘要并按信号词初判")
    ap.add_argument("--candidates", required=True)
    ap.add_argument("--out", default="reports/_raw/citation_abstracts_%s.json" % sc.today_stamp())
    ap.add_argument("--signal", default=sc.DEFAULT_SIGNAL_RE.pattern,
                    help="信号词正则（默认强化学习）")
    ap.add_argument("--topic-words", default=",".join(sc.DEFAULT_TOPIC_WORDS),
                    help="主题词，逗号分隔；只用于标注 topic 命中")
    ap.add_argument("--batch", type=int, default=50)
    ap.add_argument("--sleep", type=float, default=0.2)
    ap.add_argument("--crossref-fallback", action="store_true",
                    help="OpenAlex 无摘要时逐条查 Crossref（较慢）")
    args = ap.parse_args()

    signal_re = re.compile(args.signal, re.I)
    topic_words = [w.strip() for w in args.topic_words.split(",") if w.strip()]
    cands = load_candidates(args.candidates)
    if not cands:
        print("没有候选，退出")
        return

    print("candidates: %d" % len(cands))
    n_oa = enrich_openalex(cands, args.batch, args.sleep)
    print("OpenAlex abstracts: %d" % n_oa)
    if args.crossref_fallback:
        n_cr = enrich_crossref(cands, args.sleep)
        print("Crossref fallback abstracts: %d" % n_cr)

    hits = []
    for c in cands:
        blob = (c.get("title") or "") + " " + (c.get("abstract") or "")
        m = signal_re.search(blob)
        c["signal_hit"] = bool(m)
        c["signal_match"] = m.group(0) if m else ""
        c["topic_hit"] = sc.contains_any(c.get("title") or "", topic_words)
        c["has_abstract"] = bool((c.get("abstract") or "").strip())
        if c["signal_hit"] and c["topic_hit"]:
            hits.append(c)

    hits.sort(key=lambda c: (-(c.get("year") or 0), (c.get("title") or "").lower()))
    no_abs = [c for c in cands if not c["has_abstract"]]
    print("\nsignal+topic hits: %d | with abstract: %d | no abstract: %d" % (
        len(hits), sum(1 for c in cands if c["has_abstract"]), len(no_abs)))
    for c in hits:
        print("%s | %s | %s | %s" % (
            c.get("year"), (c.get("signal_match") or "")[:16],
            (c.get("title") or "")[:88], c.get("doi")))

    sc.save_json(args.out, {"candidates": cands, "hits": hits, "no_abstract": no_abs})
    print("\nsaved=%s" % args.out)
    if no_abs:
        print("无摘要 %d 条：只能按题名判读，不得当作「已排除」；报告里须声明覆盖缺口。" % len(no_abs))


if __name__ == "__main__":
    main()
