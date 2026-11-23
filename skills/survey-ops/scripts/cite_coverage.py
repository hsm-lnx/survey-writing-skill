# -*- coding: utf-8 -*-
r"""正文引用覆盖核对（写作卷 §4.1）。

口径三条，缺一即假阳性：
  ① 只截正文区（参考文献标记之前），文献表自身的 [n] 不计入正文覆盖；
  ② 区间引用 \[a\]--\[b\] 视为引用 a~b 全部，实体集先展开再比对；
  ③ [U] 占位与数学区间 \[0,1) 这类「转义开括号 + 逗号 + 闭圆括号」都不是引用，
     先剔除，避免 \[…\] 裸配对扫描吞掉邻近的真实引用。

token 与实体分开报：token = 印出的引用标记个数（区间按两端计 2 个），
实体 = 展开区间后的被引编号集合。两者混用会把区间覆盖误判成「未引」。

用法：
  python cite_coverage.py <manuscript.md> [-m "# 参考文献"] [-s "# 补充材料"] [-n N] [-o report.txt]
  N 缺省自文献表行首条目号推导；两种转义形态 \[n\] 与 \[n] 均认；
  补充材料区（默认 # 补充材料 之后）单独计 token 与实体，仅补材被引的实体不计正文缺口。

退出码：0 = 全覆盖；1 = 有缺口或形态异常（必须回读原文再下结论）；2 = 无法定 N。
"""
import argparse
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

RANGE_RE = re.compile(r'\\\[(\d+)\\?\]\s*(?:--|-|–|—)\s*\\\[(\d+)\\?\]')
MATH_RE = re.compile(r'\\\[\s*-?\d+(?:\.\d+)?\s*,\s*-?\d+(?:\.\d+)?\s*[\)\]]')
PLACEHOLDER_RE = re.compile(r'\\\[U\\?\]')
TOKEN_RE = re.compile(r'\\\[(\d+)\\?\]')
ODD_RE = re.compile(r'\\\[[^\]]*\\?\]')


def _read(path):
    # utf-8-sig：兼容带 BOM 的导出文件
    return pathlib.Path(path).read_text(encoding='utf-8-sig')


def _scan(zone):
    """区内扫描：返回 (tokens 数, 实体集, 区间, math, placeholder, odd)。"""
    ranges = [(int(a), int(b)) for a, b in RANGE_RE.findall(zone)]
    math_forms = MATH_RE.findall(zone)
    placeholders = PLACEHOLDER_RE.findall(zone)
    rest = MATH_RE.sub(' ', PLACEHOLDER_RE.sub(' ', zone))
    tokens = TOKEN_RE.findall(rest)
    cited = {int(x) for x in tokens}
    odd = [x[:80] for x in ODD_RE.findall(TOKEN_RE.sub(' ', rest))]
    expanded = set(cited)
    for a, b in ranges:
        expanded |= set(range(min(a, b), max(a, b) + 1))
    return len(tokens), expanded, ranges, math_forms, placeholders, odd


def parse(path, marker, n_max, supp_marker='# 补充材料'):
    text = _read(path)
    parts = text.split(marker, 1)
    body = parts[0]
    tail = parts[1] if len(parts) > 1 else ''
    supp = tail.split(supp_marker, 1)[1] if supp_marker and supp_marker in tail else ''

    bt, b_ent, b_rng, b_math, b_ph, b_odd = _scan(body)
    st, s_ent, s_rng, s_math, s_ph, s_odd = _scan(supp)

    expanded = b_ent | s_ent
    expected = set(range(1, n_max + 1))
    supp_only = sorted(s_ent - b_ent)
    return {
        'marker_found': marker in text,
        'body_chars': len(body),
        'ranges': b_rng,
        'tokens': bt,
        'entities': len(b_ent),
        'supp_tokens': st,
        'supp_entities': sorted(s_ent),
        'supp_only': supp_only,
        'placeholders': b_ph + s_ph,
        'math_forms': b_math + s_math,
        'odd_forms': b_odd + s_odd,
        'missing': sorted(expected - expanded),
        'extra': sorted(expanded - expected),
    }


def derive_max(path, marker):
    """从文献表行首条目号推导最大编号（阈值不硬编码，避免过期）。"""
    text = _read(path)
    if marker not in text:
        return None
    refs = text.split(marker, 1)[1]
    nums = [int(x) for x in re.findall(r'(?m)^\\\[(\d+)\\?\]', refs)]
    return max(nums) if nums else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('manuscript')
    ap.add_argument('-m', '--marker', default='# 参考文献')
    ap.add_argument('-s', '--supp-marker', default='# 补充材料',
                    help='补充材料区标题；给空串则不分补材区')
    ap.add_argument('-n', '--max', type=int, default=None,
                    help='期望覆盖 1..N；缺省自文献表行首条目号推导')
    ap.add_argument('-o', '--out')
    a = ap.parse_args()

    n_max = a.max if a.max is not None else derive_max(a.manuscript, a.marker)
    if not n_max:
        print('marker 未找到或文献表无条目号，无法推导 N；请用 -n 显式给定')
        sys.exit(2)
    derived = '（自文献表推导）' if a.max is None else '（显式给定）'

    r = parse(a.manuscript, a.marker, n_max, a.supp_marker)
    lines = [
        f'n_max={n_max}{derived} marker_found={r["marker_found"]} body_chars={r["body_chars"]}',
        f'range_citations={len(r["ranges"])} {r["ranges"]}',
        f'tokens={r["tokens"]} entities={r["entities"]} | supp_tokens={r["supp_tokens"]} supp_entities={r["supp_entities"]}（仅补材被引：{r["supp_only"]}）',
        f'placeholders_U={r["placeholders"]} math_forms={len(r["math_forms"])} {r["math_forms"]}',
        f'missing_1_{n_max}={r["missing"]}',
        f'extra={r["extra"]}',
        f'odd_bracket_forms={len(r["odd_forms"])} {r["odd_forms"]}',
    ]
    ok = not r['missing'] and not r['extra'] and not r['odd_forms'] and r['marker_found']
    lines.append('verdict=' + ('全覆盖' if ok else
                              '有缺口／形态异常——回读原句后再下结论（阴性不出门，写作卷 §4.1）'))

    if a.out:
        pathlib.Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    sys.exit(0 if ok else 1)


if __name__ == '__main__':
    main()
