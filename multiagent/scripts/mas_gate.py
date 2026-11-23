# -*- coding: utf-8 -*-
"""多智能体轮次闸门（只读）。

用法：
    python scripts/mas_gate.py reports/_raw/mas/r4_20261117
    python scripts/mas_gate.py --all          # 扫全部轮次，出对比表
    python scripts/mas_gate.py --strict <dir> # 缺机器头也算 FAIL

判据分两档，按 verdict.md 第一行有没有机器头自动选择：

  v2（有机器头，2026-11-23 起）
    <!-- mas {"round":"r6_20261123","format_version":2,"seat":"judge",
              "manuscript_sha":"2AAD792B","authorization":"段",
              "budget":{"wording":12,"structure":0},"allow_frozen":[],
              "structural":[],"pending_updates":[],"stalled_ack":[],
              "pending_hash":"..."} -->
    · reader／audit／reviewer 也要各自的机器头，seat 与 manuscript_sha 对得上；
    · reader 五块齐全且过最小长度，files_read 只许正文或隔离副本；
    · audit 八项齐全，实测表 ≥8 行；有 docs/state.json 时须引其 SHA 与字节；
    · verdict 预算为数字（wording ≤20，structure ≤2），U 账按内容哈希结账；
    · U 账所有「滞」条目须在 pending_updates 或 stalled_ack 中认领；
    · reader／audit 出现「从略／同上／见上轮」等压缩标记即 FAIL。

  legacy（无机器头）
    按旧判据检查：reader 三块、audit 八项、verdict 授权与体量、U 账 mtime、结构条目要有 reviewer。
    旧轮次不强制补头；加 --strict 才把缺头判 FAIL。

只读：不写、不改、不删任何文件。退出码 0=全过，1=有 FAIL，2=用法错误。

项目可选文件：
  docs/state.json            提供 manuscript、sha256_8、bytes 时启用对应实测项
  docs/task_cards/mas_pending.md   U 账；不存在时 v2 判 FAIL，legacy 判 FAIL
没有 state.json 的项目，闸门跳过 manuscript_sha／字节核对，并明确标「未启用」。
"""
import glob
import hashlib
import io
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PENDING = os.path.join(ROOT, 'docs', 'task_cards', 'mas_pending.md')
STATE = os.path.join(ROOT, 'docs', 'state.json')

R_READER_LEGACY = ['回味', '悬置账', '节读感']
READER_SECTIONS = [('回味', 80), ('节读感', 40), ('悬置账', 40), ('仍未合上', 40), ('语言层面', 0)]
R_AUDIT = ['引用', '表结构', '数字', '台账', '冻结', '门面', 'progress', '概念首现']
HDR = re.compile(r'<!--\s*mas\s*(\{.*?\})\s*-->', re.S)
KILL_ANY = ['从略', '见上轮', '与前轮相同', '不再重复']
KILL_BOUNDED = ['同上', '重复项']
FORBIDDEN_READ = ('bib/', 'docs/progress', 'docs/claims', 'docs/concepts',
                  'docs/freeze', 'docs/task_cards', 'pdfs/', 'reports/_raw/mas')


def read(p):
    try:
        return io.open(p, encoding='utf-8', errors='replace').read()
    except IOError:
        return None


def header(text):
    if not text:
        return None
    m = HDR.search(text)
    if not m:
        return None
    try:
        return json.loads(m.group(1))
    except ValueError:
        return None


def state():
    try:
        with io.open(STATE, encoding='utf-8') as f:
            return json.load(f)
    except (IOError, ValueError):
        return {}


def manuscript_rel(st):
    for k in ('manuscript', 'manuscript_path'):
        v = st.get(k)
        if isinstance(v, str) and v.strip():
            return v.strip()
    ms = st.get('manuscripts')
    if isinstance(ms, list) and ms and isinstance(ms[0], str):
        return ms[0]
    for base in (os.path.join(ROOT, 'manuscript'), os.path.join(ROOT, 'draft')):
        if os.path.isdir(base):
            for p in sorted(glob.glob(os.path.join(base, '*.md'))):
                return os.path.relpath(p, ROOT).replace('\\', '/')
    return ''


def sha8(st):
    v = st.get('sha256_8')
    if isinstance(v, str) and v:
        return v
    v = st.get('sha256')
    if isinstance(v, str) and len(v) >= 8:
        return v[:8]
    return ''


def size_bytes(st):
    v = st.get('bytes', st.get('size'))
    return v if isinstance(v, int) else None


def pending_hash():
    try:
        with open(PENDING, 'rb') as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]
    except OSError:
        return ''


def stalled_items():
    """U 账里状态列为「滞」的条目编号。状态列取表格最后一列。"""
    text = read(PENDING) or ''
    out = []
    for line in text.split('\n'):
        s = line.strip()
        if not s.startswith('| U'):
            continue
        cells = [c.strip() for c in s.strip('|').split('|')]
        if cells and '滞' in cells[-1]:
            out.append(cells[0])
    return out


def section_text(text, key):
    m = re.search(r'\n#+\s*[^\n]*' + re.escape(key) + r'[^\n]*\n', text)
    if m:
        rest = text[m.end():]
    else:
        idx = text.find(key)
        if idx < 0:
            return ''
        rest = text[idx + len(key):]
    m2 = re.search(r'\n##\s', rest)
    if m2:
        rest = rest[:m2.start()]
    return rest.strip()


def word_markers(text):
    hits = [k for k in KILL_ANY if k in text]
    hits += [k for k in KILL_BOUNDED
             if re.search(r'(^|[|｜\s（(：:，,；;])' + re.escape(k) + r'($|[|｜\s）)。，,；;])', text)]
    return hits


def table_rows(text):
    n = 0
    for line in text.split('\n'):
        s = line.strip()
        if s.startswith('|') and s.endswith('|') and '---' not in s and s.count('|') >= 5:
            n += 1
    return n


def check_header(h, seat, name, st, rows, required=()):
    if h is None:
        rows.append(('FAIL', '%s 缺机器头' % name, '需 <!-- mas {...} --> 头（format_version=2）'))
        return False
    if h.get('format_version') != 2:
        rows.append(('FAIL', '%s format_version≠2' % name, '旧格式不按 v2 判，请补头'))
        return False
    if h.get('seat') != seat:
        rows.append(('FAIL', '%s seat=%r ≠ %r' % (name, h.get('seat'), seat), '席位标识不符'))
    want = sha8(st)
    if want and h.get('manuscript_sha') != want:
        rows.append(('FAIL', '%s manuscript_sha=%r ≠ state %r' % (
            name, h.get('manuscript_sha'), want), '量的可能是旧稿'))
    for k in required:
        if not h.get(k):
            rows.append(('FAIL', '%s 头缺 %s' % (name, k), 'v2 必填字段'))
    return True


def check_files_read(h, st, rows, ms_rel):
    fr = h.get('files_read')
    if not isinstance(fr, list) or not fr:
        rows.append(('FAIL', 'reader 头缺 files_read', 'v2 必填：只读正文的清单'))
        return
    bad = [x for x in fr if not isinstance(x, str) or any(t in x.replace('\\', '/') for t in FORBIDDEN_READ)]
    if bad:
        rows.append(('FAIL', 'reader files_read 含非正文：%s' % bad[:3],
                     '冷读不得读台账／纲要／回执／往轮产出'))
        return
    if ms_rel:
        base = os.path.basename(ms_rel)
        odd = [x for x in fr if os.path.basename(x.replace('\\', '/')) != base]
        if odd:
            rows.append(('FAIL', 'reader files_read 与正文文件名不符：%s' % odd[:3],
                         '只许正文或同名隔离副本'))


def check_v2(d, name, st, rows, rd, au, vd, rv, hv):
    ms_rel = manuscript_rel(st)
    ok_sha = sha8(st)
    if ok_sha:
        rows.append(('INFO', '按 docs/state.json 核对 SHA %s' % ok_sha, ''))
    else:
        rows.append(('INFO', '未启用 manuscript_sha 核对（无 docs/state.json）', ''))

    if hv.get('round') != name:
        rows.append(('FAIL', 'verdict 头 round=%r ≠ 目录 %r' % (hv.get('round'), name), '轮次标识不符'))

    if rd is None:
        rows.append(('FAIL', 'reader.md 缺失', '冷读席未落盘'))
    else:
        hv_rd = header(rd)
        check_header(hv_rd, 'reader', 'reader.md', st, rows)
        if hv_rd:
            check_files_read(hv_rd, st, rows, ms_rel)
    if au is None:
        rows.append(('FAIL', 'audit.md 缺失', '对账席未落盘'))
    else:
        check_header(header(au), 'auditor', 'audit.md', st, rows)
    if rv is not None:
        check_header(header(rv), 'reviewer', 'reviewer.md', st, rows)

    # reader：五块 + 自报 + 压缩标记
    if rd is not None:
        for key, need in READER_SECTIONS:
            body = section_text(rd, key)
            if key not in rd:
                rows.append(('FAIL', 'reader 缺块：%s' % key, '五块是这一席唯一的产出物'))
            elif len(body) < need:
                rows.append(('FAIL', 'reader 块「%s」过短（%d<%d 字）' % (key, len(body), need),
                             '空标题不算跑过'))
        if '席前自报' not in rd and '自报' not in rd:
            rows.append(('FAIL', 'reader 无席前自报', '缺自报＝未开工'))
        hit = word_markers(rd)
        if hit:
            rows.append(('FAIL', 'reader 含压缩标记：' + '／'.join(hit), '冷读每轮都是新的'))

    # audit：八项 + 实测表 + state 数字 + 压缩标记
    if au is not None:
        got = [k for k in R_AUDIT if k in au]
        if len(got) < 8:
            rows.append(('FAIL', 'audit 项数 %d/8' % len(got), '缺项即未完成'))
        else:
            rows.append(('PASS', 'audit 八项齐', ''))
        nrow = table_rows(au)
        if nrow < 8:
            rows.append(('FAIL', 'audit 实测表仅 %d 行（<8）' % nrow, '八项须逐项给实测值'))
        if ok_sha and ok_sha not in au:
            rows.append(('FAIL', 'audit 未引 state SHA %s' % ok_sha, '须写明量的是哪一版'))
        b = size_bytes(st)
        if b is not None and str(b) not in au and '{:,}'.format(b) not in au:
            rows.append(('FAIL', 'audit 未引 state 字节 %s' % b, '须与 state 对账'))
        hit = word_markers(au)
        if hit:
            rows.append(('FAIL', 'audit 含压缩标记：' + '／'.join(hit), 'audit 不许从略'))

    # verdict：授权、预算、类型、U 账、结构
    auth = hv.get('authorization')
    if not auth:
        rows.append(('FAIL', 'verdict 缺 authorization', '没写死授权单位，执笔可无限扩'))
    budget = hv.get('budget') or {}
    try:
        w = int(budget.get('wording', -1))
        s = int(budget.get('structure', -1))
    except (TypeError, ValueError):
        w, s = -1, -1
    if w < 0 or s < 0:
        rows.append(('FAIL', 'verdict 缺 budget{wording,structure}', 'v2 必填数字预算'))
    else:
        if w > 20:
            rows.append(('FAIL', 'verdict wording 预算 %d>20' % w, '任务卡上限 20'))
        if s > 2:
            rows.append(('FAIL', 'verdict structure 预算 %d>2' % s, '任务卡上限 2'))
        if w <= 20 and s <= 2:
            rows.append(('PASS', 'verdict 预算已写死', ''))

    af = hv.get('allow_frozen')
    if not isinstance(af, list):
        rows.append(('FAIL', 'verdict allow_frozen 须为列表', '如 [] 或 [50]'))
    elif any(not isinstance(x, int) for x in af):
        rows.append(('FAIL', 'allow_frozen 含非整数', '只认行号'))
    else:
        rows.append(('INFO', 'allow_frozen=%s（本项目无冻结基线时仅作声明）' % af, ''))

    ph = hv.get('pending_hash')
    cur_ph = pending_hash()
    if not ph:
        rows.append(('FAIL', 'verdict 缺 pending_hash', 'U 账按内容结账，不按 mtime'))
    elif cur_ph and ph != cur_ph:
        rows.append(('FAIL', 'pending_hash %s ≠ U 账当前 %s' % (ph, cur_ph),
                     'U 账内容与裁决时不一致（或未更新）'))

    ups = hv.get('pending_updates')
    if not isinstance(ups, list):
        rows.append(('FAIL', 'verdict pending_updates 须为列表', '如 [] 或 ["U1"]'))
        ups = []
    else:
        ptext = read(PENDING) or ''
        for u in ups:
            if u and u not in ptext:
                rows.append(('FAIL', 'U 账缺 %s' % u, '裁决提到的 U 条目必须已入账'))

    ack = hv.get('stalled_ack')
    if not isinstance(ack, list):
        rows.append(('FAIL', 'verdict 缺 stalled_ack', 'U 账所有「滞」须在 pending_updates 或 stalled_ack 中认领'))
    else:
        have = set(ups) | set(ack)
        need = [u for u in stalled_items() if u not in have]
        if need:
            rows.append(('FAIL', '有「滞」未认领：%s' % '、'.join(need), '清账闸：漏一条即 FAIL'))
        else:
            rows.append(('PASS', '「滞」条目已全部认领', ''))

    struct = hv.get('structural')
    if struct is None:
        rows.append(('FAIL', 'verdict 缺 structural', '如 [] 或 ["U2"]'))
    elif struct:
        if rv is None:
            rows.append(('FAIL', '结构条目在案却无 reviewer.md', '结构轮前必跑审稿'))
        else:
            if table_rows(rv) < 3:
                rows.append(('FAIL', 'reviewer 主张表 <3 行', '审稿席须给主张—凭据表'))
            if '必答' not in rv:
                rows.append(('FAIL', 'reviewer 缺必答问题', '审稿席须列必答问题'))
            if table_rows(rv) >= 3 and '必答' in rv:
                rows.append(('PASS', '结构条目在案且有 reviewer.md', ''))


def check_legacy(d, rows, rd, au, vd, rv):
    if rd is None:
        rows.append(('FAIL', 'reader.md 缺失', '冷读席未落盘'))
    else:
        miss = [k for k in R_READER_LEGACY if k not in rd]
        if miss:
            rows.append(('FAIL', 'reader.md 缺块：' + '／'.join(miss),
                         '主控压缩了读者产出——压掉等于没跑'))
        else:
            rows.append(('PASS', 'reader.md 三块齐', ''))
        if '席前自报' not in rd and '自报' not in rd:
            rows.append(('WARN', 'reader.md 无席前自报', '无法确认它读了什么、认了哪几条法'))

    if au is None:
        rows.append(('FAIL', 'audit.md 缺失', '对账席未落盘'))
    else:
        got = [k for k in R_AUDIT if k in au]
        if len(got) < len(R_AUDIT):
            miss = [k for k in R_AUDIT if k not in au]
            rows.append(('WARN', 'audit.md 项数 %d/%d' % (len(got), len(R_AUDIT)),
                         '缺 ' + '、'.join(miss) + '；缺项须在报告里写明原因'))
        else:
            rows.append(('PASS', 'audit.md 八项齐', ''))

    if vd is None:
        rows.append(('FAIL', 'verdict.md 缺失', '法官未出裁决'))
        return
    if '授权单位' not in vd:
        rows.append(('FAIL', 'verdict.md 缺授权单位', '没写死授权单位，执笔可以无限扩'))
    elif '措辞轮' in vd and '体量' not in vd:
        rows.append(('FAIL', 'verdict.md 缺体量', '措辞轮必须写死体量上限'))
    else:
        rows.append(('PASS', 'verdict.md 授权单位与体量已写', ''))

    if not os.path.exists(PENDING):
        rows.append(('FAIL', 'U 账缺失', 'docs/task_cards/mas_pending.md 不存在，收工无从结账'))
    else:
        pm = os.path.getmtime(PENDING)
        vm = os.path.getmtime(os.path.join(d, 'verdict.md'))
        if pm + 1 < vm:
            rows.append(('FAIL', 'U 账未更新', 'mas_pending.md 的 mtime 早于本轮 verdict.md——收工没结账'))
        else:
            rows.append(('PASS', 'U 账已更新', ''))

    if '进结构队列' in vd:
        if rv is None:
            if ('未跑审稿' in vd) or ('无 reviewer' in vd):
                rows.append(('WARN', '结构条目在案但未跑审稿（已注明）', '结构轮前必跑，本轮可放行'))
            else:
                rows.append(('FAIL', '结构条目在案却无 reviewer.md，也未注明原因', '结构轮前必跑审稿'))
        else:
            rows.append(('PASS', '结构条目在案且有 reviewer.md', ''))


def check(d, strict=False):
    name = os.path.basename(d.rstrip('\\/'))
    st = state()
    rd = read(os.path.join(d, 'reader.md'))
    au = read(os.path.join(d, 'audit.md'))
    vd = read(os.path.join(d, 'verdict.md'))
    rv = read(os.path.join(d, 'reviewer.md'))

    hv = header(vd)
    if hv is None:
        if strict:
            return [('FAIL', 'verdict.md 缺机器头（--strict）', 'v2 轮次须带 format_version=2')]
        rows = [('INFO', 'legacy：无机器头，按旧判据', '旧轮次不强制补头')]
        check_legacy(d, rows, rd, au, vd, rv)
        return rows
    if hv.get('format_version') != 2:
        return [('FAIL', 'verdict.md format_version≠2', '本闸门只认 v2')]
    rows = []
    check_v2(d, name, st, rows, rd, au, vd, rv, hv)
    if not any(r[0] == 'FAIL' for r in rows):
        rows.append(('PASS', 'v2 内容判据全过', ''))
    return rows


def show(d, strict=False):
    name = os.path.basename(d.rstrip('\\/'))
    rows = check(d, strict)
    fail = sum(1 for r in rows if r[0] == 'FAIL')
    print('\n== %s ==  %s' % (name, 'FAIL %d' % fail if fail else '全部通过'))
    for tag, what, why in rows:
        print('  [%s] %s%s' % (tag, what, ('\n         → ' + why) if why else ''))
    return fail


def main(argv):
    args = [a for a in argv[1:] if not a.startswith('--')]
    flags = [a for a in argv[1:] if a.startswith('--')]
    strict = '--strict' in flags
    if not args and '--all' not in flags:
        print(__doc__)
        return 2
    if '--all' in flags:
        base = os.path.join(ROOT, 'reports', '_raw', 'mas')
        dirs = sorted([p for p in glob.glob(os.path.join(base, 'r*')) if os.path.isdir(p)])
        total = 0
        lines = []
        for d in dirs:
            rows = check(d, strict)
            fail = sum(1 for r in rows if r[0] == 'FAIL')
            warn = sum(1 for r in rows if r[0] == 'WARN')
            total += fail
            lines.append((os.path.basename(d), 'FAIL' if fail else 'PASS', fail, warn,
                          '；'.join(w for t, w, _ in rows if t in ('FAIL', 'WARN')) or '—'))
        print('%-16s %5s %5s %5s  %s' % ('轮次', '状态', 'FAIL', 'WARN', '不合格项'))
        for n, status, f, w, s in lines:
            print('%-16s %5s %5d %5d  %s' % (n, status, f, w, s[:60]))
        print('\n合计 FAIL %d' % total)
        return 1 if total else 0
    d = args[0]
    if not os.path.isdir(d):
        d = os.path.join(ROOT, d)
    if not os.path.isdir(d):
        print('找不到轮次目录：%s' % args[0])
        return 2
    return 1 if show(d, strict) else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
