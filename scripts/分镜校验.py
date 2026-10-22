# -*- coding: utf-8 -*-
"""校验机读分镜表 scene_plan/v2（SOP 8.2 + 8.4）。与纯口播.txt 交叉验证。

用法：python 分镜校验.py <scene_plan.json> [--txt 纯口播.txt]
退出码：0 全 PASS / 1 有 FAIL
"""
import argparse
import json
import re
import sys

REQUIRED_TOP = ["contract", "project", "scenes", "timing", "delivery_promise"]
REQUIRED_SCENE = ["id", "title", "beat", "start_s", "end_s", "oral_lines",
                  "oral_text", "char_count", "shots"]
SHOT_FIELDS = ["id", "duration", "picture", "line", "texts", "viz", "slot"]
BANNED_IN_AUDIO = ["受大者", "汉书", "夫天亦", "公仪休"]   # 禁读项；生僻字只禁新增
OK, FAIL = "PASS", "FAIL"


def cjk_len(text):
    return len(re.findall(r"[\u4e00-\u9fff\u3007]", text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("plan")
    ap.add_argument("--txt", default="")
    a = ap.parse_args()
    plan = json.load(open(a.plan, encoding="utf-8"))
    rows = []

    def chk(name, ok, detail=""):
        rows.append((name, OK if ok else FAIL, detail))
        return ok

    chk("契约版本 v2", plan.get("contract") == "scene_plan/v2", str(plan.get("contract")))
    chk("顶层字段", all(k in plan for k in REQUIRED_TOP),
        "缺:" + ",".join(k for k in REQUIRED_TOP if k not in plan) if any(
            k not in plan for k in REQUIRED_TOP) else "齐")
    scenes = plan.get("scenes", [])
    chk("场景字段", all(all(k in s for k in REQUIRED_SCENE) for s in scenes),
        f"{len(scenes)} 个场景")

    shots = [sh for s in scenes for sh in s.get("shots", [])]
    chk("镜七字段齐全", all(all(k in sh for k in SHOT_FIELDS) for sh in shots), f"{len(shots)} 个镜")

    ids = [s["id"] for s in scenes]
    chk("场景编号连续", ids == [f"S{i:02d}" for i in range(1, len(scenes) + 1)], ",".join(ids))

    gaps = [round(scenes[i + 1]["start_s"] - scenes[i]["end_s"], 3)
            for i in range(len(scenes) - 1)]
    chk("场景时间轴连续", all(abs(g) <= 0.05 for g in gaps), f"最大缝隙 {max(gaps, default=0)}s")

    shot_gaps = [round(shots[i + 1]["start_s"] - shots[i]["end_s"], 3)
                 for i in range(len(shots) - 1)]
    chk("镜时间轴连续", all(abs(g) <= 0.05 for g in shot_gaps),
        f"最大缝隙 {max(shot_gaps, default=0)}s")

    total = plan["timing"]["total_s"]
    chk("末镜收在总长", abs(shots[-1]["end_s"] - total) <= 0.1,
        f"末镜 {shots[-1]['end_s']}s / timing {total}s")

    bad = [s["id"] for s in scenes if not 180 <= s.get("cpm", 0) <= 260]
    chk("场景语速 180–260 字/分", not bad, "超界:" + ",".join(bad) if bad else
        f"{min(s['cpm'] for s in scenes):.1f}–{max(s['cpm'] for s in scenes):.1f}")

    missing_sub = [s["id"] for s in scenes if not s.get("subtitle_hint")]
    chk("每场景有字幕提示", not missing_sub, "缺:" + ",".join(missing_sub) if missing_sub else
        "单行 ≤18 字由字幕重出时保证（B2）")

    joined = "".join(s["oral_text"] for s in scenes)
    chk("场景字数合计", sum(s["char_count"] for s in scenes) == cjk_len(joined),
        f"{sum(s['char_count'] for s in scenes)} 念读字")

    chk("镜台词拼回场景一致", all("".join(sh["line"] for sh in s["shots"]) == s["oral_text"]
                             for s in scenes), "")

    if a.txt:
        txt = open(a.txt, encoding="utf-8").read()
        paras = ["".join(l.strip() for l in p.splitlines() if l.strip())
                 for p in txt.split("\n\n") if p.strip()]
        chk("与纯口播.txt 逐段一致", [s["oral_text"] for s in scenes] == paras,
            f"plan {len(scenes)} 段 / txt {len(paras)} 段")

    digits = re.findall(r"[0-9]", joined)
    chk("口播无阿拉伯数字", not digits, "发现:" + "".join(sorted(set(digits))) if digits else "")

    hits = [w for w in BANNED_IN_AUDIO if w in joined]
    chk("禁读项（文言/专名）", not hits, "命中:" + ",".join(hits) if hits else "0")

    empty = [sh["id"] for sh in shots if not sh["picture"] or not sh["viz"]]
    chk("每镜有画面/可视化", not empty, "空:" + ",".join(empty) if empty else f"{len(shots)} 个镜")

    bad_slot = [sh["id"] for sh in shots if sh["slot"] != sh["id"]]
    chk("素材 slot 与镜号一致", not bad_slot, ",".join(bad_slot[:5]) if bad_slot else "")

    chk("承诺·时长在 6–8 分钟内", 360 <= total <= 480, f"{total}s")
    checks = plan["delivery_promise"].get("machine_checks", [])
    if "ending_is_question" in checks:
        chk("承诺·结尾是问句", scenes[-1]["oral_lines"][-1].rstrip().endswith(("？", "?")),
            scenes[-1]["oral_lines"][-1][-20:])

    w = max(len(r[0]) for r in rows) + 2
    print(f"文件: {a.plan}")
    print("检查项".ljust(w) + "结果   说明")
    print("-" * (w + 40))
    for name, res, detail in rows:
        print(f"{name.ljust(w)}{res:<6} {detail}")
    badn = [r for r in rows if r[1] == FAIL]
    print()
    print("结论: " + ("PASS" if not badn else f"FAIL（{len(badn)} 项）"))
    sys.exit(0 if not badn else 1)


if __name__ == "__main__":
    main()
