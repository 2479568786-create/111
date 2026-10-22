# -*- coding: utf-8 -*-
"""按 scene_plan 的 32 个镜头，给每个槽出「素材兜底方案」（D 闸门转绿备用，口播不动）。

用法：python 素材兜底方案.py <scene_plan.json> [--out 兜底方案.csv]
输出列：slot,场景,画面,viz,槽类型,版权风险,兜底方案,英文检索短语
"""
import argparse
import csv
import json
import re

# 画面关键词 → (槽类型, 兜底方案, 英文检索短语)
RULES = [
    (("书影", "刻本", "画像砖", "耕织图", "古画", "故城", "石刻", "汉阙", "竹简",
      "织机", "复原图", "菜园", "空镜", "宋刻本", "遗址"),
     ("公版图片", "直接换公版（Wikimedia/古籍数字化），零版权风险",
      "ancient chinese book page, ink brush, macro")),
    (("图形", "动画", "饼图", "天平", "俯视", "示意", "图表", "数据", "递进",
      "进度条", "文字卡", "UI", "界面演示", "柱状", "对比", "图标", "阵列", "条形",
      "分拣", "传送带", "三层", "黑底白字", "文字卡", "录屏"),
     ("自制动画", "自制图形/文字卡，无需外部素材",
      "flat motion graphic, data chart, minimal")),
    (("刑具", "牢房", "博物馆", "文物"),
     ("公版图片", "博物馆/档案公版图（Wikimedia）＋慢推",
      "ancient chinese artifact, museum, macro")),
    (("截屏", "评论", "版面", "处罚", "罚单", "决定书"),
     ("官方截屏", "官方页面重新截屏并标注日期来源，或改文字卡",
      "official document screenshot, text card")),
    (("菜市场", "摊", "集市", "蔬果", "白菜"),
     ("实拍视频", "换成已核实免费素材（Pexels/Pixabay），按检索词找",
      "busy vegetable market, street vendors, handheld")),
    (("城市", "夜景", "天际线", "高楼", "街道", "街边"),
     ("实拍视频", "换成已核实免费素材（Pexels/Pixabay），按检索词找",
      "night city skyline, neon, timelapse")),
    (("地铁", "便利店", "法院", "写字楼", "办公室", "电梯"),
     ("实拍视频", "换成已核实免费素材（Pexels/Pixabay），按检索词找",
      "empty subway station, convenience store, night")),
    (("扫码", "手机", "APP", "团购"),
     ("实拍视频", "换成已核实免费素材，或用手机界面自制演示",
      "smartphone app screen, hands, close up")),
    (("背影", "工人", "摊主", "人群"),
     ("实拍视频", "换成已核实免费素材，注意避免正脸与可识别信息",
      "crowd of people walking, back view, city")),
]

RISK = {"公版图片": "低（可直接换公版）", "自制动画": "无", "官方截屏": "低（重截并标注）",
        "实拍视频": "高（D2c 卡点，必须换已核实素材）"}


def classify(pic):
    for keys, (kind, plan, phrase) in RULES:
        if any(k in pic for k in keys):
            return kind, plan, phrase
    return ("实拍视频", "按现有画面找已核实免费素材，或用公版图像+缓推兜底",
            "abstract background, slow motion, mood")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--out", default="素材兜底方案.csv")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    rows, stat = [], {}
    for sc in plan["scenes"]:
        for sh in sc["shots"]:
            kind, fb, phrase = classify(sh["picture"])
            stat[kind] = stat.get(kind, 0) + 1
            rows.append({
                "slot": sh["slot"], "场景": sc["id"], "画面": sh["picture"],
                "viz": sh["viz"], "槽类型": kind, "版权风险": RISK[kind],
                "兜底方案": fb, "英文检索短语": phrase,
            })
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["slot", "场景", "画面", "viz", "槽类型",
                                          "版权风险", "兜底方案", "英文检索短语"])
        w.writeheader()
        w.writerows(rows)
    print(f"槽 {len(rows)} 个：", "；".join(f"{k} {v}" for k, v in sorted(stat.items())))
    print("写出:", a.out)


if __name__ == "__main__":
    main()
