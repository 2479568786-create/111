# -*- coding: utf-8 -*-
"""从兜底方案 + scene_plan 生成「实拍槽替换清单」：每个实拍槽给首选检索短语和公版兜底。

用法：python 实拍槽替换清单.py <scene_plan.json> <兜底方案.csv> [--out 替换清单.csv]
"""
import argparse
import csv
import json

# 画面关键词 → 公版/自制兜底（不需要外部实拍）
FALLBACK = [
    (("菜市场", "摊", "集市", "白菜"),
     "菜市场摊位构图用自制图形（手绘摊位＋菜筐）叠在公版《耕织图》市集局部上，加轻微推镜"),
    (("城市", "夜景", "天际线"),
     "公版民国上海城市影像（Wikimedia，公版）＋ 自绘天际线剪影缓推"),
    (("地铁", "便利店", "法院", "写字楼", "办公室"),
     "自绘线条场景（站台/门脸/台阶）＋ 文字卡叠压，配环境音；或改用公版新闻版面素材"),
    (("扫码", "手机", "APP", "团购"),
     "自制手机界面演示动画（自绘 UI，无第三方素材）"),
    (("人", "背影", "工人", "摊主"),
     "公版老照片人物背影（Wikimedia/国会图书馆公版）＋ 慢推；避免正脸"),
]


def fallback_for(pic):
    for keys, text in FALLBACK:
        if any(k in pic for k in keys):
            return text
    return "公版图像＋缓推，或纯文字卡（不需外部实拍）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("csv_in")
    ap.add_argument("--out", default="董仲舒_样本_实拍槽替换清单.csv")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    fb = {r["slot"]: r for r in csv.DictReader(open(a.csv_in, encoding="utf-8-sig"))}

    dur = {}
    for sc in plan["scenes"]:
        for sh in sc["shots"]:
            dur[sh["slot"]] = sh["duration"]

    rows = []
    for slot, r in fb.items():
        if r["槽类型"] != "实拍视频":
            continue
        rows.append({
            "slot": slot,
            "场景": r["场景"],
            "画面": r["画面"],
            "需要时长(s)": round(dur.get(slot, 0), 1),
            "首选_已核实免费素材_检索短语": r["英文检索短语"],
            "次选_无需外部实拍_公版兜底": fallback_for(r["画面"]),
            "备注": "避免正脸与可识别门牌；B站来源一律不采用",
        })
    rows.sort(key=lambda x: x["slot"])
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"实拍槽 {len(rows)} 个 | 合计需要 {sum(r['需要时长(s)'] for r in rows):.1f}s")
    print("写出:", a.out)


if __name__ == "__main__":
    main()
