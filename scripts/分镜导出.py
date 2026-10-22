# -*- coding: utf-8 -*-
"""md 逐字稿 → 机读分镜表 scene_plan/v2（SOP 8.2 固定七字段）。

字段：镜号 id / 时长 duration_s / 画面 picture / 台词 oral / 花字 onscreen / 可视化 visual / 素材slot asset_slot
用法：
  python 分镜导出.py <逐字稿.md> [--total 443.433] [--cpm 220] [--version v1.3] [--out x.json]
口径：
  - 台词按「场景」归属，镜内不做假精度切分（oral 字段为该场景台词全文，视频制作实测后可细分）；
  - 可视化 visual 由画面文字启发式推断（翻页/描红/图形动画/快切/空镜…），可人工改 json；
  - 时间默认按 md 各段区间比例分配到 --total（成片实测总长），配音出来由视频制作改 measured 回写。
"""
import argparse
import json
import re
import sys

HEAD = re.compile(r"^### (\d+:\d+)[–\-—](\d+:\d+) ｜ (.+?)\s*$")
TIME = re.compile(r"^(\d+):(\d+)$")
BEATS = {1: "hook", 2: "setup", 3: "evidence", 4: "case", 5: "mechanism",
         6: "consequence", 7: "turn", 8: "present", 9: "present",
         10: "converge", 11: "cta"}

# 画面文字 → 可视化方式（按顺序匹配，命中即止）
VISUAL_RULES = [
    (("翻页", "书影", "刻本", "页边"), "翻页/书影缓推"),
    (("描红", "高亮", "亮起", "逐字"), "局部描红/逐条亮起"),
    (("图形动画", "图示", "饼图", "天平", "俯视"), "图形动画/动态示意"),
    (("三连切", "快切", "切"), "快切/硬切"),
    (("空镜",), "空镜"),
    (("复原", "遗址", "石刻", "画像砖", "古画", "耕织图", "宋刻本"), "资料画面（缓推）"),
    (("实拍", "录制", "截屏"), "实拍/录屏"),
]


def mmss(t):
    m, s = TIME.match(t).groups()
    return int(m) * 60 + int(s)


def cjk_len(text):
    return len(re.findall(r"[\u4e00-\u9fff\u3007]", text))


def guess_visual(picture):
    for keys, label in VISUAL_RULES:
        if any(k in picture for k in keys):
            return label
    return "实拍/资料画面"


def parse_md(path):
    sections, cur, in_oral = [], None, False
    for raw in open(path, encoding="utf-8").read().splitlines():
        s = raw.strip()
        m = HEAD.match(s)
        if m:
            cur = {"start_est": mmss(m.group(1)), "end_est": mmss(m.group(2)),
                   "title": m.group(3), "oral": [], "broll": [], "onscreen": [],
                   "subtitle": ""}
            sections.append(cur)
            in_oral = False
            continue
        if cur is None:
            continue
        if s == "**口播**":
            in_oral = True
            continue
        if in_oral and s.startswith("> "):
            t = s[2:].strip()
            if t:
                cur["oral"].append(t)
            continue
        if in_oral and s:
            in_oral = False
        if s.startswith("**画面**："):
            cur["broll"] = [x.strip() for x in re.split(r"[；;]", s.split("：", 1)[1]) if x.strip()]
        elif s.startswith("**字幕**："):
            cur["subtitle"] = s.split("：", 1)[1].strip()
        elif s.startswith("**花字"):
            body = s.split("：", 1)[1] if "：" in s else ""
            cur["onscreen"] = [x.strip() for x in re.split(r"[；;]", body) if x.strip()]
    return [x for x in sections if x["oral"]]


def split_lines(lines, groups):
    """按字数把整句分成 groups 组（贪心），每组至少一句；返回长度 = groups 的字符串列表。"""
    if groups <= 0:
        return []
    if groups == 1:
        return ["".join(lines)]
    if len(lines) <= groups:
        return [l for l in lines] + [""] * (groups - len(lines))
    total = sum(cjk_len(l) for l in lines)
    target = total / groups
    out, cur, acc = [], [], 0
    for idx, l in enumerate(lines):
        cur.append(l)
        acc += cjk_len(l)
        left_lines = len(lines) - idx - 1
        left_groups = groups - len(out) - 1
        if left_groups <= 0:
            continue
        if acc >= target and left_lines >= left_groups:
            out.append("".join(cur))
            cur, acc = [], 0
    out.append("".join(cur))
    while len(out) < groups:
        out.append("")
    return out[:groups]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("md")
    ap.add_argument("--total", type=float, default=443.433)
    ap.add_argument("--cpm", type=float, default=220.0)
    ap.add_argument("--version", default="")
    ap.add_argument("--channel", default="糊塗說")
    ap.add_argument("--alloc", choices=["chars", "heading"], default="chars",
                    help="时间分配：chars=按字数均摊（全片语速一致，推荐）；heading=按 md 时间码比例")
    ap.add_argument("--promise", default=(
        "这不是幻灯片：全片零文言朗读、每镜有具体画面槽、原文与专名全部花字上屏、"
        "最长连续静态 ≤8s 且无黑帧、结尾一句可截图当标题。"))
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    secs = parse_md(a.md)
    if not secs:
        sys.exit("没解析到带口播的段落，检查 md 结构")

    chars = [cjk_len("".join(x["oral"])) for x in secs]
    est_total = sum(x["end_est"] - x["start_est"] for x in secs)
    t, scenes = 0.0, []
    total_chars = sum(chars) or 1
    for i, (sec, n) in enumerate(zip(secs, chars), 1):
        if a.alloc == "chars":
            dur = n / total_chars * a.total          # 按字数均摊语速，全片 cpm 一致
        else:
            dur = (sec["end_est"] - sec["start_est"]) / est_total * a.total
        oral_text = "".join(sec["oral"])
        slots = sec["broll"] or ["实拍/资料画面（待补）"]
        oral_parts = split_lines(sec["oral"], len(slots))
        shots, st = [], t
        weights = [max(cjk_len(p), 1) for p in oral_parts]
        empties = [j for j, p in enumerate(oral_parts) if not p]
        base = dur * 0.2 / len(empties) if empties else 0.0
        text_total = dur - base * len(empties)
        wtext = [0 if j in empties else weights[j] for j in range(len(oral_parts))]
        wtot = sum(wtext) or 1
        for j, pic in enumerate(slots, 1):
            if j - 1 in empties:
                sd = base
            else:
                sd = text_total * weights[j - 1] / wtot
            shots.append({
                "id": f"S{i:02d}-{j:02d}",                 # 镜号
                "start_s": round(st, 3),
                "end_s": round(st + sd, 3),
                "duration": round(sd, 3),                  # 时长
                "picture": pic,                            # 画面
                "viz": guess_visual(pic),                  # 可视化
                "texts": sec["onscreen"],                  # 花字
                "line": oral_parts[j - 1] if j - 1 < len(oral_parts) else "",  # 台词
                "slot": f"S{i:02d}-{j:02d}",               # 素材 slot
            })
            st += sd
        scenes.append({
            "id": f"S{i:02d}", "title": sec["title"], "beat": BEATS.get(i, "body"),
            "start_s": round(t, 3), "end_s": round(t + dur, 3),
            "oral_lines": sec["oral"], "oral_text": oral_text,
            "char_count": n, "cpm": round(n / dur * 60, 1),
            "texts": sec["onscreen"], "subtitle_hint": sec["subtitle"],
            "shots": shots,
        })
        t += dur

    plan = {
        "contract": "scene_plan/v2",
        "project": re.sub(r"_逐字稿.*$", "", a.md.split("\\")[-1].split("/")[-1]),
        "channel": a.channel,
        "script_version": a.version,
        "language": "zh-CN",
        "format": {"resolution": "1920x1080", "fps": 30},
        "delivery_promise": {
            "statement": a.promise,
            "machine_checks": [c for c in [
                "no_classical_in_audio", "every_shot_has_picture",
                "duration_360_to_480",
                "ending_is_question" if "结尾" in a.promise else None,
                "max_static_run_le_8s" if "静态" in a.promise else None,
                "no_black_frames" if "黑帧" in a.promise else None,
            ] if c],
        },
        "timing": {"source": "estimated", "total_s": round(t, 3),
                   "cpm_basis": a.cpm, "overwrite_by": "video:measured_timeline"},
        "scenes": scenes,
    }
    out = a.out or re.sub(r"_逐字稿.*\.md$", "_scene_plan.json", a.md)
    json.dump(plan, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    shots_n = sum(len(s["shots"]) for s in scenes)
    print(f"场景 {len(scenes)} 个 | 镜 {shots_n} 个 | 念读字 {sum(chars)} | 总长 {t:.3f}s")
    print("写出:", out)


if __name__ == "__main__":
    main()
