# -*- coding: utf-8 -*-
"""按兜底方案生成「非实拍槽（公版/自制/官方截屏）制作清单」，给视频制作把占位字卡换成真素材。

输入：兜底方案.csv（素材兜底方案.py 生成）+ scene_plan
输出：slot, 场景, 画面, 槽类型, 需要时长(s), 制作方式, 公版/来源建议
"""
import argparse
import csv
import json

MAKE = [
    (("书影", "刻本", "宋刻本", "竹简", "织机", "画像砖", "石刻", "耕织图", "古画", "遗址", "文物", "博物馆"),
     "公版图 + 翻页/缓推（Ken Burns 之外用缩放位移，别用静帧）",
     "维基共享资源（Wikimedia Commons，公有领域）/ 中华珍宝馆 / 国图古籍数字化；下载后存素材包并记 URL"),
    (("图形", "动画", "饼图", "天平", "俯视", "示意", "图表", "数据", "递进", "进度条",
      "柱状", "对比", "图标", "阵列", "条形", "分拣", "传送带", "三层"),
     "自绘 SVG/HTML 动画（一镜一页，元素逐个入场）",
     "无需外部素材；配色跟频道主色，字号≥64px 保证 1080p 可读"),
    (("截屏", "评论", "版面", "处罚", "罚单", "决定书"),
     "官方页面重新截屏 + 日期来源角标（或改文字卡）",
     "人民日报 2020-12-11 版面 / 市场监管总局处罚决定书页面；截图时带上日期与域名"),
    (("黑底白字", "文字卡"),
     "文字排版动画（逐字打出 + 落版停 1.5s）",
     "无需外部素材；花字与字幕严格分层，别压字"),
    (("APP", "录屏", "界面"),
     "自制 UI 演示动画（自绘手机界面，价格页打码）",
     "无需外部素材；避免真实 APP 截图（版权与隐私）"),
]


def make_for(pic):
    for keys, how, src in MAKE:
        if any(k in pic for k in keys):
            return how, src
    return "公版图 + 缓推，或纯文字卡", "维基共享资源（公有领域）"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("csv_in")
    ap.add_argument("--out", default="董仲舒_样本_字卡槽制作清单.csv")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    fb = {r["slot"]: r for r in csv.DictReader(open(a.csv_in, encoding="utf-8-sig"))}
    dur = {sh["slot"]: sh["duration"] for sc in plan["scenes"] for sh in sc["shots"]}

    rows = []
    for slot, r in fb.items():
        if r["槽类型"] == "实拍视频":
            continue
        how, src = make_for(r["画面"])
        rows.append({
            "slot": slot, "场景": r["场景"], "画面": r["画面"], "槽类型": r["槽类型"],
            "需要时长(s)": round(dur.get(slot, 0), 1),
            "制作方式": how, "公版/来源建议": src,
        })
    rows.sort(key=lambda x: x["slot"])
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    tot = sum(r["需要时长(s)"] for r in rows)
    from collections import Counter
    c = Counter(r["槽类型"] for r in rows)
    print(f"非实拍槽 {len(rows)} 个 | 合计 {tot:.1f}s |", "；".join(f"{k} {v}" for k, v in c.items()))
    print("写出:", a.out)


if __name__ == "__main__":
    main()
