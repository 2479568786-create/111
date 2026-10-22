# -*- coding: utf-8 -*-
"""把 md 里 ### 标题的时间码改成 scene_plan.json 的时间轴（一次性的口径对齐）。
用法: python 对齐md时间码.py <md> <scene_plan.json>
"""
import json
import re
import sys

md_path, plan_path = sys.argv[1], sys.argv[2]
plan = json.load(open(plan_path, encoding="utf-8"))
spans = [(s["start_s"], s["end_s"]) for s in plan["scenes"]]


def fmt(t):
    t = int(round(t))
    return f"{t // 60}:{t % 60:02d}"


HEAD = re.compile(r"^### (\d+:\d+)[–\-—](\d+:\d+) ｜ (.+?)\s*$")
lines = open(md_path, encoding="utf-8").read().splitlines()
i = 0
out = []
for ln in lines:
    m = HEAD.match(ln.strip())
    if m and i < len(spans):
        start, end = spans[i]
        out.append(f"### {fmt(start)}–{fmt(end)} ｜ {m.group(3)}")
        i += 1
    else:
        out.append(ln)
if i != len(spans):
    sys.exit(f"标题数 {i} 与场景数 {len(spans)} 不一致，未写入")
open(md_path, "w", encoding="utf-8").write("\n".join(out) + "\n")
print(f"已对齐 {i} 个标题时间码；总长 {fmt(spans[-1][1])}")
