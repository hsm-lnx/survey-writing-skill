# -*- coding: utf-8 -*-
"""忠实性核对的证据行校验（SKILL §4.2，2026-11-04 设立）。

本脚本管的是「规矩有没有被遵守」，不是「核得对不对」——后者只能人判。
机械可判的只有五件，脚本只做这五件：

  (1) 表结构：五列（正文位置／论断原文／强度／原文关键句／原等级 → 新等级）；
  (2) 枚举：强度 ∈ {弱,中,强,最高}；等级 ∈ {A,B,C}，新等级另可记「删除」；
  (3) 上限：B/C 级不得承担「强／最高」论断（§4.2 第 2、3 条）。
      「中」级要求 2~3 篇共引（§2），故此处在 B/C 上要求论断原文含 >=2 处引用；
  (4) 升 A 须有原文：新等级为 A 的行，原文关键句不得为空或占位；
  (5) 断言行与正文一致：给 -c 时，论断原文须逐字出现在正文中（去空白与反斜杠后比对）。
      找不到即说明正文已改过，该位置的 A 级自动失效（§4.2 第 1 条）。

阴性结论同样适用：新等级记「删除」或关键句含「不支持」的，必须抄出原文，
否则判为「阴性不出门」违规（SKILL §4.1）。

用法：
  python faithfulness_check.py <evidence.md> [-c <manuscript.md>] [-o report.txt]
  python faithfulness_check.py --template        # 打印空表头，供新建证据表

退出码：0 = 通过（可含警告）；1 = 有违规；2 = 用法或解析错误。
"""
import argparse
import pathlib
import re
import sys

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

HEADER = ['正文位置', '论断原文', '强度', '原文关键句', '原等级 → 新等级']
STRENGTHS = ('弱', '中', '强', '最高')
EMPTY_CELLS = {'', '—', '-', '--', '无', '未核', '待核', '（未核）', '(未核)'}

GRADE_RE = re.compile(r'[ABC]')
CITE_RE = re.compile(r'\\?\[\s*(\d+)\s*\\?\]')
RANGE_RE = re.compile(r'\\?\[\s*(\d+)\s*\\?\]\s*(?:--|-|–|—)\s*\\?\[\s*(\d+)\s*\\?\]')


def norm(s):
    """比对用归一化：去空白、去反斜杠、去 markdown 强调符。"""
    s = s.replace('\u3000', ' ')
    s = re.sub(r'\s+', '', s)
    s = s.replace('\\', '').replace('**', '').replace('*', '')
    return s


def split_row(line):
    cells = [c.strip() for c in line.strip().strip('|').split('|')]
    return cells


def parse_table(text):
    """找到表头含「论断原文」的第一张表，返回 (header, rows, 起始行号)。"""
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if not line.strip().startswith('|'):
            continue
        cells = split_row(line)
        if len(cells) >= 2 and '论断原文' in cells[1]:
            rows = []
            j = i + 1
            if j < len(lines) and re.match(r'^\|[\s:\-|]+\|?\s*$', lines[j].strip()):
                j += 1
            while j < len(lines) and lines[j].strip().startswith('|'):
                rows.append((j + 1, split_row(lines[j])))
                j += 1
            return cells, rows, i + 1
    return None, [], 0


def parse_grade(cell):
    """返回 (原等级, 新等级, 是否删除)。新等级缺省等于原等级。"""
    if '删' in cell:
        g = GRADE_RE.findall(cell)
        return (g[0] if g else '?'), '删除', True
    g = GRADE_RE.findall(cell)
    if not g:
        return '?', '?', False
    if len(g) == 1:
        return g[0], g[0], False
    return g[0], g[-1], False


def cite_count(claim):
    """论断原文中的引用处数；区间引用按展开后计。"""
    n = len(CITE_RE.findall(claim))
    for a, b in RANGE_RE.findall(claim):
        n += abs(int(b) - int(a))
    return n


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('evidence', nargs='?')
    ap.add_argument('-c', '--manuscript')
    ap.add_argument('-o', '--out')
    ap.add_argument('--template', action='store_true')
    a = ap.parse_args()

    if a.template:
        print('| ' + ' | '.join(HEADER) + ' |')
        print('|' + '|'.join(['---'] * len(HEADER)) + '|')
        return 0

    if not a.evidence:
        sys.stderr.write('缺少证据表路径。用 --template 打印空表头。\n')
        return 2

    p = pathlib.Path(a.evidence)
    if not p.is_file():
        sys.stderr.write('证据表不存在：%s\n' % a.evidence)
        return 2
    text = p.read_text(encoding='utf-8')

    header, rows, _ = parse_table(text)
    if header is None:
        sys.stderr.write('未找到表头含「论断原文」的证据表。\n')
        return 2

    problems, warns = [], []

    if len(header) != 5:
        problems.append('表头列数 %d，应为 5（%s）' % (len(header), '／'.join(HEADER)))
    for k in range(min(len(header), 5)):
        if header[k] != HEADER[k]:
            problems.append('表头第 %d 列是「%s」，应为「%s」' % (k + 1, header[k], HEADER[k]))

    if not rows:
        problems.append('证据表为空：0 行。核对结论不落成证据行，视为未核对（§4.2 第 4 条）。')

    ms_norm = None
    if a.manuscript:
        mp = pathlib.Path(a.manuscript)
        if not mp.is_file():
            sys.stderr.write('正文文件不存在：%s\n' % a.manuscript)
            return 2
        ms_norm = norm(mp.read_text(encoding='utf-8'))

    seen = {}
    for ln, cells in rows:
        tag = '第 %d 行' % ln
        if len(cells) != 5:
            problems.append('%s：列数 %d，应为 5' % (tag, len(cells)))
            continue
        pos, claim, strength, quote, grade_cell = cells
        old, new, deleted = parse_grade(grade_cell)

        if old not in ('A', 'B', 'C'):
            problems.append('%s：等级「%s」不可解析' % (tag, grade_cell))
            continue
        if not deleted and new not in ('A', 'B', 'C'):
            problems.append('%s：新等级「%s」不可解析' % (tag, grade_cell))
            continue
        if strength not in STRENGTHS:
            problems.append('%s：强度「%s」不在 %s 内' % (tag, strength, '／'.join(STRENGTHS)))
            continue
        if not pos.strip():
            problems.append('%s：正文位置为空' % tag)
        if not claim.strip():
            problems.append('%s：论断原文为空' % tag)

        quote_empty = quote.strip() in EMPTY_CELLS
        claim_cites = cite_count(claim)

        # (3) 等级上限
        if old in ('B', 'C') and strength in ('强', '最高'):
            problems.append('%s：%s 级承担「%s」论断——%s 级不得支撑强／最高论断（§4.2 第 2、3 条）'
                            % (tag, old, strength, old))
        elif old in ('B', 'C') and strength == '中' and claim_cites < 2:
            problems.append('%s：%s 级单独承担「中」论断（共引 %d 处，需 >=2 篇，§2）'
                            % (tag, old, claim_cites))

        # (4) 升 A 须有原文
        if new == 'A' and quote_empty:
            problems.append('%s：新等级为 A 但无原文关键句——升 A 必须摘出原文（§4.2 第 4 条）' % tag)

        # 阴性不出门
        if (deleted or '不支持' in quote or '不支持' in claim) and quote_empty:
            problems.append('%s：阴性结论（删除／不支持）未抄原文——阴性不出门（§4.1）' % tag)

        # (5) 与正文一致
        if ms_norm is not None and claim.strip():
            if norm(claim) not in ms_norm:
                problems.append('%s：论断原文在正文中找不到——正文已改过，该位置等级须重判（§4.2 第 1 条）' % tag)

        key = (norm(pos), norm(claim))
        if key in seen:
            problems.append('%s：与第 %d 行重复登记（同一位置同一论断）' % (tag, seen[key]))
        else:
            seen[key] = ln

        if old == 'A' and new != 'A' and not deleted:
            warns.append('%s：A 降 %s——确认是失效检查所得，不是顺手改判（§4.2 第 1 条）' % (tag, new))

    lines = [
        'evidence=%s rows=%d' % (a.evidence, len(rows)),
        'manuscript_check=%s' % ('on' if ms_norm is not None else 'off'),
        'violations=%d warnings=%d' % (len(problems), len(warns)),
    ]
    for w in warns:
        lines.append('[WARN] ' + w)
    for q in problems:
        lines.append('[FAIL] ' + q)
    lines.append('verdict=' + ('通过' if not problems else
                               '有违规——按 §4.2 逐条改正后重跑'))

    if a.out:
        pathlib.Path(a.out).write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    return 0 if not problems else 1


if __name__ == '__main__':
    sys.exit(main())
