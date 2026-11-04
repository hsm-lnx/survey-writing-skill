# -*- coding: utf-8 -*-
"""正文引用覆盖核对（SKILL §4.1）。

口径三条，缺一即假阳性：
  ① 只截正文区（参考文献标记之前），文献表自身的 [n] 不计入正文覆盖；
  ② 区间引用 \\[a\\]--\\[b\\] 视为引用 a~b 全部，实体集先展开再比对；
  ③ [U] 占位与数学区间 \\[0,1) 这类「转义开括号 + 逗号 + 闭圆括号」都不是引用，
     先剔除，避免 \\[…\\] 裸配对扫描吞掉邻近的真实引用。

token 与实体分开报：token = 印出的引用标记个数（区间按两端计 2 个），
实体 = 展开区间后的被引编号集合。两者混用会把区间覆盖误判成"未引"。

用法：
  python cite_coverage.py <manuscript.md> [-m "# 参考文献"] [-n 期望条数] [-o report.txt]

  -n 省略时以实际出现的最大编号为界；指定时按 1..n 全集核对缺口。

退出码：0 = 全覆盖；1 = 有缺口或形态异常（必须回读原文再下结论）。
"""
import argparse
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

RANGE_RE = re.compile(r'\\\[(\d+)\\\]\s*(?:--|-|–|—)\s*\\\[(\d+)\\\]')
MATH_RE = re.compile(r'\\\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*[\)\]]')
PLACEHOLDER_RE = re.compile(r'\\\[U\\\]')
TOKEN_RE = re.compile(r'\\\[([^\]]*)\\\]')


def parse(path, marker, n_max):
    text = pathlib.Path(path).read_text(encoding='utf-8')
    body = text.split(marker)[0]

    ranges = [(int(a), int(b)) for a, b in RANGE_RE.findall(body)]
    math_forms = MATH_RE.findall(body)
    placeholders = PLACEHOLDER_RE.findall(body)

    rest = MATH_RE.sub(' ', PLACEHOLDER_RE.sub(' ', body))
    tokens = [x for x in TOKEN_RE.findall(rest) if re.fullmatch(r'\d+', x.strip())]
    cited = {int(x) for x in tokens}
    odd = [x[:80] for x in TOKEN_RE.findall(rest) if not re.fullmatch(r'\d+', x.strip())]

    expanded = set(cited)
    for a, b in ranges:
        expanded |= set(range(min(a, b), max(a, b) + 1))

    if not n_max:
        n_max = max(expanded) if expanded else 0

    expected = set(range(1, n_max + 1))
    return {
        'n_max': n_max,
        'marker_found': marker in text,
        'body_chars': len(body),
        'ranges': ranges,
        'tokens': len(tokens),
        'entities': len(expanded),
        'placeholders': len(placeholders),
        'math_forms': math_forms,
        'missing': sorted(expected - expanded),
        'extra': sorted(expanded - expected),
        'odd_forms': odd,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('manuscript')
    ap.add_argument('-m', '--marker', default='# 参考文献')
    ap.add_argument('-n', '--max', type=int, default=None,
                    help='期望的文献总条数；省略时取实际最大编号')
    ap.add_argument('-o', '--out')
    a = ap.parse_args()

    r = parse(a.manuscript, a.marker, a.max)
    lines = [
        f'marker_found={r["marker_found"]} body_chars={r["body_chars"]}',
        f'range_citations={len(r["ranges"])} {r["ranges"]}',
        f'tokens={r["tokens"]} entities={r["entities"]}',
        f'placeholders_U={r["placeholders"]} math_forms={len(r["math_forms"])} {r["math_forms"]}',
        f'missing_1_{r["n_max"]}={r["missing"]}',
        f'extra={r["extra"]}',
        f'odd_bracket_forms={len(r["odd_forms"])} {r["odd_forms"]}',
    ]
    ok = not r['missing'] and not r['extra'] and not r['odd_forms'] and r['marker_found']
    lines.append('verdict=' + ('全覆盖' if ok else
                              '有缺口／形态异常——回读原句后再下结论（阴性不出门，SKILL §4.1）'))

    if a.out:
        pathlib.Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
