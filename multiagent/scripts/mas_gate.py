# -*- coding: utf-8 -*-
"""多智能体轮次闸门（只读）。

用法：
    python scripts/mas_gate.py reports/_raw/mas/r4_20261117
    python scripts/mas_gate.py --all          # 扫全部轮次，出对比表

判据来自 docs/task_cards/ 下的五件：
  · reader.md 必须保留「回味／悬置账／节读感」三块——主控只许在文件头加元信息，不许压缩合并；
  · audit.md 须含八项；verdict.md 须写死授权单位与体量；
  · U 账（mas_pending.md）的修改时间必须不早于 verdict.md——否则就是"收了工没结账"；
  · 出现结构级条目时，须有 reviewer.md，或在 verdict 里写明未跑与原因。

只读：不写、不改、不删任何文件。退出码 0=全过，1=有 FAIL。
"""
import io
import os
import re
import sys
import glob

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PENDING = os.path.join(ROOT, 'docs', 'task_cards', 'mas_pending.md')

# audit.md 的八项。关键词取宽一点：同一项用中文或英文写法都算。
R_READER = ['回味', '悬置账', '节读感']
R_AUDIT = [
    ['引用'],
    ['表结构'],
    ['数字', '口径'],
    ['台账'],
    ['冻结'],
    ['门面', '题名', '摘要'],
    ['progress', '进度'],
    ['概念首现', '首现'],
]
R_BUDGET = ['授权单位', '体量']


def read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except IOError:
        return None


def check(d):
    rows = []
    rd = read(os.path.join(d, 'reader.md'))
    au = read(os.path.join(d, 'audit.md'))
    vd = read(os.path.join(d, 'verdict.md'))
    rv = read(os.path.join(d, 'reviewer.md'))

    # 1 读者产出未被压缩
    if rd is None:
        rows.append(('FAIL', 'reader.md 缺失', '冷读席未落盘'))
    else:
        miss = [k for k in R_READER if k not in rd]
        if miss:
            rows.append(('FAIL', 'reader.md 缺块：' + '／'.join(miss),
                         '主控压缩了读者产出——五块是这一席唯一的产出物，压掉等于没跑'))
        else:
            rows.append(('PASS', 'reader.md 三块齐', ''))
        if '席前自报' not in rd:
            rows.append(('WARN', 'reader.md 无席前自报', '无法确认它读了什么、认了哪几条法'))

    # 2 对账八项
    if au is None:
        rows.append(('FAIL', 'audit.md 缺失', '对账席未落盘'))
    else:
        got = [i for i, words in enumerate(R_AUDIT) if any(w in au for w in words)]
        if len(got) < len(R_AUDIT):
            miss = [str(i + 1) for i in range(len(R_AUDIT)) if i not in got]
            rows.append(('WARN', 'audit.md 项数 %d/%d' % (len(got), len(R_AUDIT)),
                         '缺第 ' + '、'.join(miss) + ' 项；缺项须在报告里写明原因'))
        else:
            rows.append(('PASS', 'audit.md 八项齐', ''))

    # 3 裁决表预算
    if vd is None:
        rows.append(('FAIL', 'verdict.md 缺失', '法官未出裁决'))
        return rows
    if '授权单位' not in vd:
        rows.append(('FAIL', 'verdict.md 缺授权单位', '没写死授权单位，执笔可以无限扩'))
    elif '措辞轮' in vd and '体量' not in vd:
        rows.append(('FAIL', 'verdict.md 缺体量', '措辞轮必须写死体量上限'))
    elif '体量' in vd:
        rows.append(('PASS', 'verdict.md 预算已写死', ''))
    else:
        rows.append(('PASS', 'verdict.md 授权单位已写死（非措辞轮，不要求体量）', ''))

    # 4 U 账是否结账
    if not os.path.exists(PENDING):
        rows.append(('FAIL', 'U 账缺失', 'docs/task_cards/mas_pending.md 不存在，收工无从结账'))
    else:
        pm = os.path.getmtime(PENDING)
        vm = os.path.getmtime(os.path.join(d, 'verdict.md'))
        if pm + 1 < vm:
            rows.append(('FAIL', 'U 账未更新',
                         'mas_pending.md 的 mtime 早于本轮 verdict.md——收工没结账'))
        else:
            rows.append(('PASS', 'U 账已更新', ''))

    # 5 结构级条目要审稿
    if '进结构队列' in vd:
        if rv is None:
            written = ('未跑审稿' in vd) or ('无 reviewer' in vd)
            if written:
                rows.append(('WARN', '结构条目在案但未跑审稿（已注明）', '结构轮前必跑，本轮可放行'))
            else:
                rows.append(('FAIL', '结构条目在案却无 reviewer.md，也未注明原因', '结构轮前必跑审稿'))
        else:
            rows.append(('PASS', '结构条目在案且有 reviewer.md', ''))

    return rows


def show(d):
    name = os.path.basename(d.rstrip('\\/'))
    rows = check(d)
    fail = sum(1 for r in rows if r[0] == 'FAIL')
    print('\n== %s ==  %s' % (name, 'FAIL %d' % fail if fail else '全部通过'))
    for tag, what, why in rows:
        print('  [%s] %s%s' % (tag, what, ('\n         → ' + why) if why else ''))
    return fail


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    if sys.argv[1] == '--all':
        base = os.path.join(ROOT, 'reports', '_raw', 'mas')
        dirs = sorted([p for p in glob.glob(os.path.join(base, 'r*'))
                       if os.path.isdir(p)])
        total = 0
        lines = []
        for d in dirs:
            rows = check(d)
            fail = sum(1 for r in rows if r[0] == 'FAIL')
            warn = sum(1 for r in rows if r[0] == 'WARN')
            total += fail
            lines.append((os.path.basename(d), fail, warn,
                          '；'.join(w for t, w, _ in rows if t != 'PASS') or '—'))
        print('%-16s %5s %5s  %s' % ('轮次', 'FAIL', 'WARN', '不合格项'))
        for n, f, w, s in lines:
            print('%-16s %5d %5d  %s' % (n, f, w, s[:70]))
        print('\n合计 FAIL %d' % total)
        return 1 if total else 0
    d = sys.argv[1]
    if not os.path.isdir(d):
        d = os.path.join(ROOT, sys.argv[1])
    if not os.path.isdir(d):
        print('找不到轮次目录：%s' % sys.argv[1])
        return 2
    return 1 if show(d) else 0


if __name__ == '__main__':
    sys.exit(main())
