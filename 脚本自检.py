# -*- coding: utf-8 -*-
"""脚本自检：按 v2 硬核叙事体阈值检查纯口播文本。

用法：
    python 脚本自检.py <纯口播.txt> [目标分钟]

输出各项指标与 PASS/WARN/FAIL；全部 PASS 时退出码 0，否则 1。
"""
import re
import sys

CJK = re.compile(r'[^\u4e00-\u9fff0-9A-Za-z]')


def eff(s):
    return CJK.sub('', s)


def main():
    if len(sys.argv) < 2:
        print('用法: python 脚本自检.py <纯口播.txt> [目标分钟]')
        return 2
    path = sys.argv[1]
    target = float(sys.argv[2]) if len(sys.argv) > 2 else 6.5
    cpm = float(sys.argv[3]) if len(sys.argv) > 3 else 250.0   # 语速口径：旧片 250，频道B 实测 218
    text = open(path, encoding='utf-8').read()
    segs = [s.strip() for s in re.split(r'\n\s*\n', text) if s.strip()]
    alltext = '\n'.join(segs)
    n = len(eff(alltext))
    sents = [x.strip() for x in re.split(r'[。！？]', alltext) if x.strip()]
    lens = [len(eff(x)) for x in sents]
    avg = sum(lens) / len(lens) if lens else 0
    longest = max(lens) if lens else 0
    longs = [(l, x) for l, x in zip(lens, sents) if l > 40]
    ex = alltext.count('！')
    q = alltext.count('？')
    q_int = n / q if q else float('inf')
    mins = n / cpm
    low, high = target * 0.9, target * 1.1
    items = [
        ('段数', len(segs), '—', 'PASS' if len(segs) >= 5 else 'WARN'),
        ('有效字数', n, '—', 'PASS'),
        (f'预计时长({cpm:.0f}字/分)', f'{mins:.2f} 分', f'{target:.1f}±10%',
         'PASS' if low <= mins <= high else 'FAIL'),
        ('句数', len(sents), '—', 'PASS'),
        ('平均句长', f'{avg:.1f} 字', '≤24', 'PASS' if avg <= 24 else 'FAIL'),
        ('最长句', f'{longest} 字', '≤40', 'PASS' if longest <= 40 else 'FAIL'),
        ('40字以上长句', len(longs), '0', 'PASS' if not longs else 'FAIL'),
        ('感叹号', ex, '0', 'PASS' if ex == 0 else 'FAIL'),
        ('设问', q, '—', 'PASS'),
        ('每问平均字数', f'{q_int:.1f}' if q else '—', '100–150',
         'PASS' if q and 100 <= q_int <= 150 else ('WARN' if q else 'WARN')),
    ]
    print(f'文件: {path}')
    print(f'{"指标":<16}{"实测":<14}{"阈值":<12}结果')
    print('-' * 52)
    for k, v, t, r in items:
        print(f'{k:<16}{str(v):<14}{t:<12}{r}')
    if longs:
        print('\n超长句：')
        for l, x in longs:
            print(f'  {l} 字 | {x}')
    bad = [i for i in items if i[3] == 'FAIL']
    print('\n结论:', 'PASS' if not bad else f'FAIL（{len(bad)} 项）')
    return 0 if not bad else 1


if __name__ == '__main__':
    sys.exit(main())
