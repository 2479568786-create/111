# -*- coding: utf-8 -*-
"""对比 md 逐字稿口播行 与 纯口播.txt，逐行一致性。

用法：python 稿本同步检查.py [md] [txt]
不带参数时用董仲舒片的默认文件（向后兼容）。
"""
import sys

md_path = sys.argv[1] if len(sys.argv) > 1 else '董仲舒_拿了大的别再拿小的_逐字稿_6-7min.md'
txt_path = sys.argv[2] if len(sys.argv) > 2 else '董仲舒_拿了大的别再拿小的_纯口播.txt'

md = open(md_path, encoding='utf-8').read()
txt = open(txt_path, encoding='utf-8').read()

# 取「逐字稿」主版本一节：优先 ## 二、逐字稿，其次 ## 三、
if '## 二、逐字稿' in md:
    sec = md.split('## 二、逐字稿', 1)[1]
    sec = sec.split('\n## ', 1)[0]
elif '## 三、逐字稿' in md:
    sec = md.split('## 三、逐字稿', 1)[1].split('\n## ', 1)[0]
else:
    sys.exit('md 里找不到逐字稿小节（## 二、逐字稿 或 ## 三、逐字稿）')

lines, in_oral = [], False
for ln in sec.splitlines():
    s = ln.strip()
    if s.startswith('**口播**'):
        in_oral = True
        continue
    if s.startswith('**') and s.endswith('**'):
        in_oral = False
        continue
    if in_oral and s.startswith('>'):
        t = s.lstrip('> ').strip()
        if t:
            lines.append(t)

t2 = [l.strip() for l in txt.splitlines() if l.strip()]

print('md:', md_path)
print('txt:', txt_path)
print('md 口播行数:', len(lines), '| txt 行数:', len(t2))
bad = 0
for i, (a, b) in enumerate(zip(lines, t2), 1):
    if a != b:
        bad += 1
        print(f'第{i}行不一致:\n  md : {a}\n  txt: {b}')
if len(lines) != len(t2):
    print('行数不等，多出部分:')
    for x in lines[len(t2):]:
        print('  md-only:', x)
    for x in t2[len(lines):]:
        print('  txt-only:', x)
print('MISMATCH' if bad or len(lines) != len(t2) else 'ALL SYNC')
