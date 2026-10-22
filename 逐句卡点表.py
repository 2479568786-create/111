# -*- coding: utf-8 -*-
"""生成「逐句卡点对照表」：一句一行 → 字幕条 → 所属场景/镜号 → 预计起止。
给剪映工作流用：拖一句画面、对一条字幕，按表查镜号。

用法：python 逐句卡点表.py <scene_plan.json> [--out 对照表.csv]
"""
import argparse
import csv
import json
import re

CJK = re.compile(r"[^\u4e00-\u9fff0-9A-Za-z]")
NEED_CHECK = ("AI", "Ozon", "ERP", "GitHub", "FPV", "README", "Codex")


def n_chars(s):
    return len(CJK.sub("", s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--out", default="逐句卡点对照表.csv")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))

    rows, idx = [], 0
    for sc in plan["scenes"]:
        lines = sc["oral_lines"]
        # 一行可能含多句：拆成「一句一条字幕」
        sents, line_of = [], []
        for li, ln in enumerate(lines, 1):
            for s in re.split(r"(?<=[。！？])", ln):
                s = s.strip()
                if s:
                    sents.append(s)
                    line_of.append(li)
        total = sum(n_chars(x) for x in sents) or 1
        t = sc["start_s"]
        span = sc["end_s"] - sc["start_s"]
        slots = [sh["slot"] for sh in sc["shots"]]
        acc = 0.0
        for ln, li in zip(sents, line_of):
            idx += 1
            n = n_chars(ln)
            dur = span * n / total
            s, e = t + acc, t + acc + dur
            hit = []
            for sh in sc["shots"]:
                if sh["end_s"] > s + 1e-6 and sh["start_s"] < e - 1e-6:
                    hit.append(sh["slot"])
            words = [w for w in NEED_CHECK if w in ln]
            rows.append({
                "句序": idx,
                "原稿行号": li,
                "场景": sc["id"],
                "句子": ln,
                "字数": n,
                "预计起(秒)": round(s, 2),
                "预计止(秒)": round(e, 2),
                "对应镜号": "/".join(hit) if hit else (slots[0] if slots else ""),
                "字幕必校对": " ".join(words),
            })
            acc += dur

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["句序", "原稿行号", "场景", "句子", "字数",
                                          "预计起(秒)", "预计止(秒)", "对应镜号", "字幕必校对"])
        w.writeheader()
        w.writerows(rows)
    tot = sum(r["字数"] for r in rows)
    print(f"句 {len(rows)} 行 | 念读字 {tot} | 需校对的英文词句 {sum(1 for r in rows if r['字幕必校对'])} 行")
    print("写出:", a.out)


if __name__ == "__main__":
    main()
