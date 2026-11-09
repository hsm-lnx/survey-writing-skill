# -*- coding: utf-8 -*-
"""前向被引追踪：对一组种子文献抓取 OpenAlex `cites:` 全量引用记录。

为什么需要：后向引文追溯（翻种子文献的参考文献表）只能找到比种子更早的
研究；只按关键词检索又会漏掉「摘要只写算法名、不写主题词」的研究。前向被引
补的是这两条路径之间的空隙。

本脚本只取题录，不作准入判定；原始返回落到 --out 指定的 JSON。

用法示例：
  python citation_chase.py --manuscript manuscript/正文.md --targets 9,25,44
  python citation_chase.py --dois-file seeds.txt --out reports/_raw/citation_chase.json
  python citation_chase.py --manuscript 正文.md --targets 12,13 --max-citing 500

环境变量（均可选）：
  OPENALEX_API_KEY   有 key 时额度更高；没有也能跑，但匿名限流更紧
  OPENALEX_MAILTO    或 CROSSREF_MAILTO，用于礼貌池标识
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_common as sc  # noqa: E402


def collect_targets(args):
    targets = {}
    if args.manuscript and args.targets:
        refs = sc.parse_refs(args.manuscript, args.ref_heading)
        for token in args.targets.split(","):
            token = token.strip()
            if not token:
                continue
            try:
                n = int(token)
            except ValueError:
                sys.stderr.write("[warn] 跳过非编号目标：%s\n" % token)
                continue
            body = refs.get(n, "")
            label = "ref_%d" % n
            if not body:
                targets[label] = {"doi": "", "ref": "", "error": "not in reference list"}
                continue
            doi = sc.first_doi(body)
            targets[label] = {"doi": doi, "ref": body[:200]}
            if not doi:
                targets[label]["error"] = "no DOI in reference entry"
    if args.dois_file:
        with open(args.dois_file, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                doi = sc.norm_doi(line.strip())
                if not doi:
                    continue
                targets["doi_%d" % i] = {"doi": doi, "ref": ""}
    return targets


def chase_one(label, info, args):
    rec = dict(info)
    if rec.get("error") or not rec.get("doi"):
        return rec
    try:
        _, work = sc.openalex_get("/works/doi:" + rec["doi"], {})
        rec["openalex_id"] = work.get("id")
        rec["cited_by_count"] = work.get("cited_by_count")
        rec["title"] = work.get("title")
    except Exception as e:
        rec["error"] = repr(e)
        return rec

    oid = (rec.get("openalex_id") or "").rstrip("/").rsplit("/", 1)[-1]
    if not oid:
        rec["error"] = "OpenAlex work id missing"
        return rec

    citing = []
    cursor = "*"
    while cursor and len(citing) < args.max_citing:
        try:
            _, page = sc.openalex_get("/works", {
                "filter": "cites:" + oid,
                "per-page": str(args.per_page),
                "cursor": cursor,
                "select": "id,doi,title,publication_year,primary_location,type",
            })
        except Exception as e:
            rec["citing_error"] = repr(e)
            break
        batch = page.get("results", [])
        citing.extend(batch)
        cursor = (page.get("meta") or {}).get("next_cursor")
        if not batch or not cursor:
            break
        time.sleep(args.sleep)
    rec["citing"] = citing
    rec["citing_n"] = len(citing)
    return rec


def main():
    ap = argparse.ArgumentParser(description="OpenAlex 前向被引追踪（只取题录，不作准入判定）")
    ap.add_argument("--manuscript", help="含参考文献表的 md 文件")
    ap.add_argument("--targets", help="参考文献编号，逗号分隔，如 9,25,44")
    ap.add_argument("--ref-heading", help="参考文献标题关键字；默认自动找「参考文献」/References")
    ap.add_argument("--dois-file", help="每行一个 DOI 的种子文件")
    ap.add_argument("--out", default="reports/_raw/citation_chase_%s.json" % sc.today_stamp())
    ap.add_argument("--per-page", type=int, default=200)
    ap.add_argument("--max-citing", type=int, default=2000, help="每个种子的被引记录上限")
    ap.add_argument("--sleep", type=float, default=0.15, help="翻页间隔秒数")
    args = ap.parse_args()

    if not (args.dois_file or (args.manuscript and args.targets)):
        ap.error("至少给 --dois-file，或同时给 --manuscript 与 --targets")

    targets = collect_targets(args)
    out = {
        "run_date": sc.today_stamp(),
        "source": "OpenAlex works?filter=cites:<openalex_id>",
        "targets": {},
    }
    errors = 0
    for label, info in targets.items():
        rec = chase_one(label, info, args)
        out["targets"][label] = rec
        if rec.get("error"):
            errors += 1
        print("[%s] doi=%s cited_by=%s fetched=%s %s" % (
            label, rec.get("doi") or "-", rec.get("cited_by_count"),
            rec.get("citing_n", "-"),
            (rec.get("title") or rec.get("error") or "")[:70]))
        time.sleep(args.sleep)

    sc.save_json(args.out, out)
    print("\ntargets=%d errors=%d saved=%s" % (len(targets), errors, args.out))
    if errors:
        print("有目标未解析成功，先修 DOI 或稍后重跑；已成功的目标照常落盘。")


if __name__ == "__main__":
    main()
