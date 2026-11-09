# -*- coding: utf-8 -*-
"""存活池整池筛查：把检索池逐条过信号词，而不是只看「反查引用集」选中的那些。

背景：L3 全文核验若只以引用集为界做目的性选样，池内合格研究可能从未被看过。
本脚本把池内每一条的题名＋摘要过一遍信号词，输出三层：

  known  已在台账/正文（不再判）
  out    题名或摘要含信号词、且不在台账/正文（待人工判读）
  blind  无摘要且题名无信号词（只能按题名判，须在报告里声明覆盖缺口）

只排序与分诊，不作准入判定。

输入 JSON 支持两种形状：
  {"records": [{"doi","title","year","venue","abstract"}, ...]}
  [{"doi","title","year","venue","abstract"}, ...]

用法：
  python pool_screen.py --pool reports/_raw/pool.json \
      --ledger bib/verified.md --manuscript manuscript/正文.md \
      --out reports/_raw/pool_screen.json --digest reports/_raw/pool_digest.txt
"""
import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import search_common as sc  # noqa: E402


def load_pool(path):
    data = sc.load_json(path)
    if isinstance(data, list):
        return data
    return data.get("records") or data.get("pool") or []


def score_process(rec, process_words, motion_words):
    title = rec.get("title") or ""
    abstract = rec.get("abstract") or ""
    p = sum(1 for w in process_words if w and w in sc.match_text(title))
    m = sum(1 for w in motion_words if w and w in sc.match_text(title))
    pa = sum(1 for w in process_words if w and w in sc.match_text(abstract))
    ma = sum(1 for w in motion_words if w and w in sc.match_text(abstract))
    return (p - m) * 2 + (pa - ma), p, m, pa, ma


def main():
    ap = argparse.ArgumentParser(description="存活池整池信号词筛查")
    ap.add_argument("--pool", required=True)
    ap.add_argument("--ledger", default="bib/verified.md")
    ap.add_argument("--manuscript", default="")
    ap.add_argument("--signal", default=sc.DEFAULT_SIGNAL_RE.pattern,
                    help="信号词正则（默认强化学习）")
    ap.add_argument("--topic-words", default=",".join(sc.DEFAULT_TOPIC_WORDS))
    ap.add_argument("--out", default="reports/_raw/pool_screen_%s.json" % sc.today_stamp())
    ap.add_argument("--digest", default="", help="可选：把 out 层按工艺/运动词排序后写成文本")
    ap.add_argument("--process-words", default="",
                    help="摘要排读用的工艺层词，逗号分隔（可选）")
    ap.add_argument("--motion-words", default="",
                    help="摘要排读用的运动层词，逗号分隔（可选）")
    args = ap.parse_args()

    signal_re = re.compile(args.signal, re.I)
    topic_words = [w.strip() for w in args.topic_words.split(",") if w.strip()]
    process_words = [w.strip().lower() for w in args.process_words.split(",") if w.strip()]
    motion_words = [w.strip().lower() for w in args.motion_words.split(",") if w.strip()]
    known = sc.known_dois([args.ledger, args.manuscript])

    records = load_pool(args.pool)
    if not records:
        print("池为空或格式不识别：%s" % args.pool)
        return

    known_rows, out_rows, blind_rows, quiet = [], [], [], 0
    for r in records:
        doi = sc.norm_doi(r.get("doi"))
        title = r.get("title") or ""
        abstract = r.get("abstract") or ""
        blob = title + " " + abstract
        m = signal_re.search(blob)
        rec = {
            "doi": doi, "title": title, "year": r.get("year"),
            "venue": r.get("venue"), "libs": r.get("libs"),
            "signal_hit": bool(m), "signal_match": m.group(0) if m else "",
            "has_abstract": bool(abstract.strip()),
            "topic_hit": sc.contains_any(title, topic_words),
        }
        if doi and doi in known:
            known_rows.append(rec)
        elif m:
            out_rows.append(rec)
        elif not abstract.strip():
            blind_rows.append(rec)
        else:
            quiet += 1

    out_rows.sort(key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))
    blind_rows.sort(key=lambda r: (-(r.get("year") or 0), (r.get("title") or "").lower()))
    print("pool records     : %d" % len(records))
    print("known            : %d" % len(known_rows))
    print("signal, out      : %d" % len(out_rows))
    print("no abstract      : %d" % len(blind_rows))
    print("quiet (no signal): %d" % quiet)
    print()
    for r in out_rows:
        print("%s | %-32s | %s | %s" % (
            r.get("year"), (r.get("signal_match") or "")[:32],
            (r.get("title") or "")[:88], r.get("doi")))
    if blind_rows:
        print("\n--- no-abstract (%d) ---" % len(blind_rows))
        for r in blind_rows:
            print("%s | %s | %s" % (r.get("year"), (r.get("title") or "")[:90], r.get("doi")))

    sc.save_json(args.out, {"known": known_rows, "out": out_rows,
                            "blind": blind_rows, "quiet": quiet})
    print("\nsaved=%s" % args.out)

    if args.digest:
        scored = []
        for r in out_rows:
            score, p, m, pa, ma = score_process(r, process_words, motion_words)
            scored.append((score, p, m, pa, ma, r))
        scored.sort(key=lambda x: (-x[0], -(x[5].get("year") or 0)))
        lines = []
        for score, p, m, pa, ma, r in scored:
            lines.append("=" * 100)
            lines.append("[%+d | title proc%d mot%d | abs proc%d mot%d] %s | %s" % (
                score, p, m, pa, ma, r.get("year"), r.get("title")))
            lines.append("DOI: %s  venue: %s  libs: %s" % (
                r.get("doi"), r.get("venue"), r.get("libs")))
            lines.append("signal: %s" % (r.get("signal_match") or ""))
            lines.append("")
        with open(args.digest, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        print("digest=%s (%d out rows)" % (args.digest, len(scored)))
        print("提示：摘要排读只是阅读顺序，不是判定；没有全文的条目仍须按题名判并声明覆盖缺口。")


if __name__ == "__main__":
    main()
