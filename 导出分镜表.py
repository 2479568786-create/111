# -*- coding: utf-8 -*-
"""按双轨规则导出《分镜表.csv》：句序,句子,镜号,画面,预计秒,类型,要点数据。
类型四选一：录屏 / 字卡 / 动效 / 图形。未标的一律「录屏」。
叠加层清单（CSV：触发句,类型,要点数据）按「触发句」匹配到分镜表的句子。

用法：
  python 导出分镜表.py <逐句卡点对照表.csv> <scene_plan.json> [--overlay 叠加层.csv] [--out 分镜表.csv]
"""
import argparse
import csv
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("sync_csv")
    ap.add_argument("plan")
    ap.add_argument("--overlay", default="")
    ap.add_argument("--out", default="分镜表.csv")
    a = ap.parse_args()

    plan = json.load(open(a.plan, encoding="utf-8"))
    pic = {sh["slot"]: sh["picture"] for sc in plan["scenes"] for sh in sc["shots"]}

    rows = []
    for r in csv.DictReader(open(a.sync_csv, encoding="utf-8-sig")):
        slot = (r["对应镜号"] or "").split("/")[0]
        rows.append({
            "句序": r["句序"], "句子": r["句子"], "镜号": r["对应镜号"],
            "画面": pic.get(slot, ""),
            "预计秒": round(float(r["预计止(秒)"]) - float(r["预计起(秒)"]), 2),
            "类型": "录屏", "要点数据": "",
        })

    hit = 0
    if a.overlay:
        for ov in csv.DictReader(open(a.overlay, encoding="utf-8-sig")):
            key = ov["触发句"].strip()
            for row in rows:
                if key and key in row["句子"]:
                    row["类型"] = ov["类型"].strip()
                    row["要点数据"] = ov.get("要点数据", "").strip()
                    hit += 1
                    break
            else:
                print("⚠ 叠加层没匹配到句子:", key)

    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["句序", "句子", "镜号", "画面", "预计秒", "类型", "要点数据"])
        w.writeheader()
        w.writerows(rows)
    from collections import Counter
    c = Counter(r["类型"] for r in rows)
    print(f"行 {len(rows)} | 叠加层命中 {hit} | 类型分布:", "；".join(f"{k} {v}" for k, v in c.items()))
    print("写出:", a.out)


if __name__ == "__main__":
    main()
