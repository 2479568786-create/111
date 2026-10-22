"""把配音实测时间回写进编剧的 scene_plan.json（timing.source: estimated → measured）。

用法: python sync_scene_timing.py --scene-plan …_scene_plan.json --timeline timeline_v5.json [--out 新文件]
映射：按汉字累计偏移把场景/镜头边界插值到 timeline 块内 → 场景与镜头 start_s/end_s 改成实测值。
"""
import argparse, json
from datetime import datetime
from pathlib import Path
import re

HAN = re.compile(r"[\u4e00-\u9fff]")

def han(s):
    return "".join(HAN.findall(s or ""))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene-plan", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    sp = json.loads(Path(args.scene_plan).read_text(encoding="utf-8-sig"))
    tl = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
    chunks = tl["chunks"]
    # 块的字数与累计
    cum = 0.0
    marks = []  # (char_start, char_end, t_start, t_end)
    for c in chunks:
        n = max(len(han(c["text"])), 1)
        marks.append((cum, cum + n, c["start"], c["end"]))
        cum += n
    total_chars = cum

    def t_at(char_pos):
        for cs, ce, ts, te in marks:
            if char_pos <= ce + 1e-6:
                frac = min(max((char_pos - cs) / max(ce - cs, 1e-6), 0.0), 1.0)
                return ts + frac * (te - ts)
        return marks[-1][3]

    # 场景累计字数（按纯口播 han 计）
    shifts = []
    char_cursor = 0.0
    for sc in sp["scenes"]:
        n = len(han(sc.get("oral_text", "")))
        if n == 0:
            n = float(sc.get("char_count") or 0)
        sc_start = t_at(char_cursor)
        sc_end = t_at(char_cursor + n)
        old = (sc["start_s"], sc["end_s"])
        sc["start_s"], sc["end_s"] = round(sc_start, 3), round(sc_end, 3)
        # 镜头按原时长比例重排到新场景区间
        shots = sc.get("shots") or []
        if shots:
            tot = sum(float(x.get("duration") or (x["end_s"] - x["start_s"])) for x in shots) or 1.0
            t = sc["start_s"]
            for i, sh in enumerate(shots):
                d = (sc["end_s"] - sc["start_s"]) * (float(sh.get("duration") or (sh["end_s"] - sh["start_s"])) / tot)
                sh["start_s"] = round(t, 3)
                sh["end_s"] = round(sc["end_s"] if i == len(shots) - 1 else t + d, 3)
                sh["duration"] = round(sh["end_s"] - sh["start_s"], 3)
                t = sh["end_s"]
        shifts.append((sc["id"], round(old[0], 2), sc["start_s"], round(sc["start_s"] - old[0], 2)))
        char_cursor += n

    sp["timing"] = {
        "source": "measured",
        "total_s": tl.get("target"),
        "cpm_basis": sp.get("timing", {}).get("cpm_basis", 220.0),
        "overwrite_by": "video:measured_timeline",
        "measured_from": Path(args.timeline).name,
        "measured_at": datetime.now().isoformat(timespec="seconds"),
        "scene_shift_max_s": max((abs(x[3]) for x in shifts), default=0),
    }
    out = Path(args.out) if args.out else Path(args.scene_plan).with_name(Path(args.scene_plan).stem + ".measured.json")
    out.write_text(json.dumps(sp, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"总汉字 {total_chars:.0f}，场景 {len(sp['scenes'])}")
    print("场景起点偏移：", [(i, s, d) for i, s, _, d in shifts])
    print(f"最大偏移 {sp['timing']['scene_shift_max_s']:.2f}s → {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
