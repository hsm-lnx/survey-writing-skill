# -*- coding: utf-8 -*-
"""Crossref 检索界实测：类型、深度、非期刊覆盖。

回答的不是「协议写了什么」，而是「这条通道实际捕到了什么、边界在哪」。
四个子命令：

  types       逐条查目标文献的 Crossref 记录类型（量 type:journal-article 的影响面）
  depth       对指定查询取消早停、取满 N 页，看深翻是否还有相关记录
  type-free   摘掉类型过滤重跑，按记录类型统计被挡在通道外的记录
  non-journal 定向枚举会议论文/书章/预印本等非期刊类型

全部只读：不写台账、不改正文，只把实测结果落盘。是否改检索式由人裁决。

用法示例：
  python retrieval_boundary.py types --manuscript manuscript/正文.md --targets 9,25,44
  python retrieval_boundary.py depth --query "welding \"reinforcement learning\"" --pages 30
  python retrieval_boundary.py type-free --query "welding AND \"reinforcement learning\""
  python retrieval_boundary.py non-journal --query "welding AND \"reinforcement learning\""

注意：Crossref query.bibliographic 检索题名/作者/容器等著录字段，不支持摘要
检索；题名筛只是粗筛，不能替代摘要判读。
"""
import argparse
import os
import sys
import time
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_common as sc  # noqa: E402

DEFAULT_SIGNAL_WORDS = (
    "reinforcement learning", "deep reinforcement learning", "training environment",
    "surrogate model", "digital twin", "sim-to-real", "process model",
    "learning environment",
)
DEFAULT_FILTER = "from-pub-date:2015-01-01,until-pub-date:2026-12-31"
DEFAULT_NONJOURNAL_TYPES = ("proceedings-article", "book-chapter", "posted-content")


def fetch_crossref(query, filter_str, pages, rows, sleep):
    """按 cursor 翻页；返回 (items, pages_fetched, stopped_reason)。"""
    items, cursor, fetched = [], "*", 0
    while fetched < pages:
        params = {
            "query.bibliographic": query,
            "rows": str(rows),
            "cursor": cursor,
            "select": "DOI,title,type,issued,container-title,abstract",
        }
        if filter_str:
            params["filter"] = filter_str
        try:
            data = sc.crossref_get("/works", params)
        except Exception as e:
            return items, fetched, "error: %r" % e
        page_items = (data.get("message") or {}).get("items") or []
        items.extend(page_items)
        cursor = (data.get("message") or {}).get("next-cursor")
        fetched += 1
        if not page_items or not cursor:
            return items, fetched, "exhausted"
        time.sleep(sleep)
    return items, fetched, "page-cap"


def load_known(args):
    dois, titles = set(), set()
    if args.pool and os.path.isfile(args.pool):
        data = sc.load_json(args.pool)
        records = data if isinstance(data, list) else (data.get("records") or [])
        for r in records:
            if r.get("doi"):
                dois.add(sc.norm_doi(r["doi"]))
            if r.get("title"):
                titles.add(sc.norm_title(r["title"]))
    dois |= sc.known_dois([args.ledger, args.manuscript])
    return dois, titles


def screen_and_diff(items, known_dois, known_titles, weld_words, signal_words):
    seen = {}
    for item in items:
        rec = sc.crossref_record(item)
        key = rec["doi"] or ("t" + sc.norm_title(rec["title"]))
        if key and key not in seen:
            seen[key] = rec
    screened = []
    for rec in seen.values():
        blob = (rec["title"] or "") + " " + (rec.get("abstract") or "")
        if sc.contains_any(blob, weld_words) and sc.contains_any(blob, signal_words):
            screened.append(rec)
    new = [r for r in screened
           if (r["doi"] not in known_dois) and (sc.norm_title(r["title"]) not in known_titles)]
    new.sort(key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))
    return seen, screened, new


def add_common_query_args(ap, default_filter):
    ap.add_argument("--query", action="append", required=True,
                    help="检索式，可重复（Crossref query.bibliographic 语法）")
    ap.add_argument("--filter", default=default_filter,
                    help="Crossref filter；传空字符串表示不加过滤")
    ap.add_argument("--pages", type=int, default=30, help="每个查询最多取多少页")
    ap.add_argument("--rows", type=int, default=100)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--pool", default="", help="存活池 JSON（可选，用于差集）")
    ap.add_argument("--ledger", default="bib/verified.md")
    ap.add_argument("--manuscript", default="")
    ap.add_argument("--weld-words", default=",".join(sc.DEFAULT_TOPIC_WORDS))
    ap.add_argument("--signal-words", default=",".join(DEFAULT_SIGNAL_WORDS))
    ap.add_argument("--out", default="reports/_raw/retrieval_boundary_%s.json" % sc.today_stamp())


def cmd_types(args):
    refs = sc.parse_refs(args.manuscript, args.ref_heading) if args.manuscript else {}
    rows, counts = [], {}
    for token in args.targets.split(","):
        token = token.strip()
        if not token:
            continue
        try:
            n = int(token)
        except ValueError:
            print("[warn] 跳过非编号目标：%s" % token)
            continue
        body = refs.get(n, "")
        doi = sc.first_doi(body)
        if not doi:
            rows.append({"n": n, "type": "no-doi", "doi": "", "ref": body[:100]})
            counts["no-doi"] = counts.get("no-doi", 0) + 1
            continue
        try:
            data = sc.crossref_get("/works/" + urllib.parse.quote(doi, safe="/"), {})
            typ = (data.get("message") or {}).get("type") or "?"
        except Exception as e:
            typ = "ERR:" + type(e).__name__
        counts[typ] = counts.get(typ, 0) + 1
        rows.append({"n": n, "type": typ, "doi": doi, "ref": body[:100]})
        time.sleep(args.sleep)
    print("Crossref type counts over %d targets: %s" % (len(rows), counts))
    for r in rows:
        flag = "" if r["type"] == "journal-article" else "  <-- 不在 journal-article 通道"
        print("%3s | %-20s | %s%s" % (r["n"], r["type"], r["doi"] or "-", flag))
    sc.save_json(args.out, {"targets": rows, "counts": counts})
    print("\nsaved=%s" % args.out)


def _run_queries(args, filter_default, types=None):
    weld_words = [w.strip() for w in args.weld_words.split(",") if w.strip()]
    signal_words = [w.strip().lower() for w in args.signal_words.split(",") if w.strip()]
    known_dois, known_titles = load_known(args)
    result = {"queries": {}, "counts": {}, "new": []}
    per = {}
    for query in args.query:
        combos = types or [None]
        for typ in combos:
            filt = args.filter if args.filter is not None else filter_default
            if typ:
                filt = ((filt + ",") if filt else "") + "type:" + typ
            items, pages, reason = fetch_crossref(
                query, filt, args.pages, args.rows, args.sleep)
            label = query if not typ else "%s | %s" % (query, typ)
            seen, screened, new = screen_and_diff(
                items, known_dois, known_titles, weld_words, signal_words)
            per[label] = {
                "filter": filt, "pages_requested": args.pages, "pages_fetched": pages,
                "stop_reason": reason, "fetched": len(items), "unique": len(seen),
                "screened": len(screened), "new": new,
            }
            print("[%s] pages=%d fetched=%d unique=%d screened=%d NEW=%d (%s)" % (
                label[:70], pages, len(items), len(seen), len(screened), len(new), reason))
            result["new"].extend(new)
    # 全局去重
    dedup = {}
    for r in result["new"]:
        key = r["doi"] or sc.norm_title(r["title"])
        dedup.setdefault(key, r)
    result["new"] = sorted(dedup.values(),
                           key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))
    result["queries"] = per
    result["counts"] = {
        "queries": len(args.query),
        "types": len(types) if types else 1,
        "new_total": len(result["new"]),
    }
    return result


def cmd_depth(args):
    res = _run_queries(args, DEFAULT_FILTER + ",type:journal-article")
    print("\nNEW total: %d" % res["counts"]["new_total"])
    for r in res["new"]:
        print("%s | %s | %s" % (r.get("year"), (r.get("title") or "")[:95], r.get("doi")))
    sc.save_json(args.out, res)
    print("\nsaved=%s" % args.out)


def cmd_type_free(args):
    res = _run_queries(args, DEFAULT_FILTER)
    print("\nNEW total: %d" % res["counts"]["new_total"])
    for r in res["new"]:
        print("%s | %-20s | %s | %s" % (
            r.get("year"), r.get("type"), (r.get("title") or "")[:88], r.get("doi")))
    sc.save_json(args.out, res)
    print("\nsaved=%s" % args.out)


def cmd_nonjournal(args):
    types = [t.strip() for t in args.types.split(",") if t.strip()]
    res = _run_queries(args, DEFAULT_FILTER, types=types)
    print("\nNEW total: %d" % res["counts"]["new_total"])
    for r in res["new"]:
        print("%s | %-20s | %s | %s" % (
            r.get("year"), r.get("type"), (r.get("title") or "")[:88], r.get("doi")))
    sc.save_json(args.out, res)
    print("\nsaved=%s" % args.out)


def main():
    ap = argparse.ArgumentParser(description="Crossref 检索界实测（只读）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("types", help="逐条查 Crossref 记录类型")
    p.add_argument("--manuscript", required=True)
    p.add_argument("--targets", required=True, help="参考文献编号，逗号分隔")
    p.add_argument("--ref-heading", default=None)
    p.add_argument("--sleep", type=float, default=0.15)
    p.add_argument("--out", default="reports/_raw/crossref_types_%s.json" % sc.today_stamp())
    p.set_defaults(func=cmd_types)

    p = sub.add_parser("depth", help="取消早停、取满 N 页")
    add_common_query_args(p, DEFAULT_FILTER + ",type:journal-article")
    p.set_defaults(func=cmd_depth)

    p = sub.add_parser("type-free", help="摘掉类型过滤重跑")
    add_common_query_args(p, DEFAULT_FILTER)
    p.set_defaults(func=cmd_type_free)

    p = sub.add_parser("non-journal", help="定向枚举非期刊类型")
    add_common_query_args(p, DEFAULT_FILTER)
    p.add_argument("--types", default=",".join(DEFAULT_NONJOURNAL_TYPES))
    p.set_defaults(func=cmd_nonjournal)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
