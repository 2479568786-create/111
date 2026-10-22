# -*- coding: utf-8 -*-
"""从 scene_plan 生成「切点表」：保证每 ≤8s 有一次画面变化（兑现 promise max_static_run_le_8s）。

规则：
- 每个镜头起止本身就是一个切点；
- 单镜 >8s 时按台词整句边界细分（无台词则均分），细分点不超过 8s；
- 输出 CSV：序号, 时间(s), 类型, slot, 场景, 说明

用法：python 切点表.py <scene_plan.json> [--max 8.0] [--out 切点表.csv]
"""
import argparse
import csv
import json
import re

SENT = re.compile(r"[^。！？]*[。！？]?")


def split_line(text, parts):
    """把一句台词按字数切成 parts 段（返回累计字数的边界比例）。"""
    sents = [s for s in SENT.findall(text) if s]
    if len(sents) < parts:  # 句子不够就均分
        return [i / parts for i in range(1, parts)]
    total = sum(len(s) for s in sents)
    acc, bounds, k = 0, [], 0
    for i, s in enumerate(sents):
        acc += len(s)
        if len(bounds) < parts - 1 and acc / total >= (len(bounds) + 1) / parts:
            bounds.append(acc / total)
    while len(bounds) < parts - 1:
        bounds.append((len(bounds) + 1) / parts)
    return bounds[:parts - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--max", type=float, default=8.0)
    ap.add_argument("--out", default="切点表.csv")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))

    rows = []
    for sc in plan["scenes"]:
        for sh in sc["shots"]:
            st, dur = sh["start_s"], sh["duration"]
            n = max(1, int(-(-dur // a.max)))          # 需要几段（向上取整）
            bounds = [i / n for i in range(1, n)]       # 均分，保证每段 ≤ max
            pts = [st] + [st + dur * b for b in bounds]
            for k, t in enumerate(pts):
                rows.append({
                    "时间(s)": round(t, 2),
                    "类型": "切镜" if k == 0 else "镜内变点",
                    "slot": sh["slot"],
                    "场景": sc["id"],
                    "说明": ("换镜：" + sh["picture"][:24]) if k == 0
                            else ("镜内变点（≤8s 均分，可挪到最近句末）：" + (sh["viz"] or "推镜/花字入场")),
                })
    rows.sort(key=lambda r: r["时间(s)"])
    for i, r in enumerate(rows, 1):
        r["序号"] = i
    gaps = [rows[i + 1]["时间(s)"] - rows[i]["时间(s)"] for i in range(len(rows) - 1)]
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["序号", "时间(s)", "类型", "slot", "场景", "说明"])
        w.writeheader()
        w.writerows(rows)
    print(f"切点 {len(rows)} 个 | 最大间隔 {max(gaps):.2f}s | 最小 {min(gaps):.2f}s | 平均 {sum(gaps)/len(gaps):.2f}s")
    print("最长连续静态（=最大间隔）", "≤8s 达标" if max(gaps) <= a.max else "超 8s 不达标")
    print("写出:", a.out)


if __name__ == "__main__":
    main()
