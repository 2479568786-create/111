"""渲染前 / 交付前预检（A 档：机读契约 + 预检 + delivery promise + 签收门）。

用法:
  python preflight.py --mp4 成片.mp4 --srt 字幕.srt --txt 纯口播.txt \
      --timeline timeline.json --state 项目状态.json [--shots 分镜表.json] \
      --out 预检报告.json

检查项：
  P1 时长      P2 规格        P3 字幕（逐字/行宽/重叠）   P4 镜头覆盖
  P5 镜数与镜长 P6 静态画面占比（防 PPT）  P7 黑帧       P8 响度
  P9 delivery promise         P10 签收门（没签收不许标完成）
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

RESULTS = []
METRICS_EXTRA = {}


def rec(level, code, msg):
    RESULTS.append({"level": level, "code": code, "msg": msg})


def run(cmd):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    return (p.stdout or "") + (p.stderr or "")


def probe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)])
    return json.loads(out[out.index("{"):])


def cjk(s: str) -> str:
    return "".join(re.findall(r"[\u4e00-\u9fff]", s))


def parse_srt(path: Path):
    raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [ln for ln in block.split("\n") if ln.strip()]
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", block)
        if not m:
            continue
        g = list(map(int, m.groups()))
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        txt = "".join(ln for ln in lines if "-->" not in ln and not ln.strip().isdigit())
        cues.append((s, e, txt))
    return cues


def static_ratio(mp4: Path) -> tuple[float, float]:
    """1fps 抽 64x36 灰度帧，连续 ≥3s 差分极小 = 静态段。返回 (静态时长占比, 最长静态段秒数)。"""
    tmp = Path(tempfile.mkdtemp(prefix="pf-")) / "f.raw"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(mp4),
         "-vf", "fps=1,scale=64:36,format=gray", "-f", "rawvideo", str(tmp)])
    if not tmp.exists():
        return 0.0, 0.0
    buf = np.fromfile(tmp, dtype=np.uint8)
    n = buf.size // (64 * 36)
    if n < 2:
        return 0.0, 0.0
    frames = buf[: n * 64 * 36].reshape(n, -1).astype(np.float32)
    diffs = np.abs(np.diff(frames, axis=0)).mean(axis=1)
    static = diffs < 1.5
    longest = cur = 0
    for v in static:
        cur = cur + 1 if v else 0
        longest = max(longest, cur)
    return float(static.mean()), float(longest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mp4", required=True)
    ap.add_argument("--srt", required=True)
    ap.add_argument("--txt", required=True)
    ap.add_argument("--timeline", required=True)
    ap.add_argument("--state", required=True)
    ap.add_argument("--shots", default="")
    ap.add_argument("--scene-plan", default="", help="编剧 scene_plan JSON（优先于 --shots，用其 scenes[].shots 作为镜头表）")
    ap.add_argument("--out", default="预检报告.json")
    ap.add_argument("--target", type=float, default=0.0)
    ap.add_argument("--blocks", default="", help="逐块 ASR 日志 CSV（取最大 CER 供 promise 校验）")
    ap.add_argument("--record", default="", help="预检记录输出路径（默认与 --out 同目录的 预检记录.json）")
    args = ap.parse_args()

    # P0 契约结构校验
    sys.path.insert(0, r"C:\Users\24795\.dsh\bot\workspace\tts-lab\.pylibs")
    try:
        import jsonschema as _js
        sd = Path(__file__).parent / "schemas"
        if (sd / "project_state.schema.json").exists():
            _js.validate(json.loads(Path(args.state).read_text(encoding="utf-8-sig")),
                         json.loads((sd / "project_state.schema.json").read_text(encoding="utf-8")))
        if args.shots and Path(args.shots).exists():
            _js.validate(json.loads(Path(args.shots).read_text(encoding="utf-8-sig")),
                         json.loads((sd / "shot_table.schema.json").read_text(encoding="utf-8")))
        rec("PASS", "P0", "项目状态/分镜表 结构校验通过")
    except Exception as e:
        rec("FAIL", "P0", f"契约结构校验失败：{str(e)[:160]}")
    mp4, srt, txt = Path(args.mp4), Path(args.srt), Path(args.txt)
    state = json.loads(Path(args.state).read_text(encoding="utf-8-sig"))
    tl = json.loads(Path(args.timeline).read_text(encoding="utf-8"))
    info = probe(mp4)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"]["duration"])
    width, height = int(v["width"]), int(v["height"])
    num, den = v["r_frame_rate"].split("/")
    fps = float(num) / float(den)

    # P1 时长
    target = args.target or float(state.get("duration") or tl.get("target") or dur)
    if abs(dur - target) <= 0.3:
        rec("PASS", "P1", f"时长 {dur:.3f}s（目标 {target:.3f}s）")
    else:
        rec("FAIL", "P1", f"时长 {dur:.3f}s 偏离目标 {target:.3f}s 达 {dur-target:+.2f}s")

    # P2 规格
    ok = width == 1920 and height == 1080 and abs(fps - 30) < 0.01 and v["codec_name"] == "h264"
    rec("PASS" if ok else "FAIL", "P2",
        f"{width}x{height} / {fps:g}fps / {v['codec_name']}" + (f" + {a['codec_name']}" if a else " 无音轨"))

    # P3 字幕
    cues = parse_srt(srt)
    body = txt.read_text(encoding="utf-8-sig")
    srt_chars, txt_chars = sum(len(cjk(t)) for _, _, t in cues), len(cjk(body))
    mline = max((len(t) for _, _, t in cues), default=0)
    overlaps = sum(1 for i in range(len(cues) - 1) if cues[i][1] > cues[i + 1][0] + 1e-6)
    bad = []
    if srt_chars != txt_chars:
        bad.append(f"字数 {srt_chars}≠口播 {txt_chars}")
    if mline > 18:
        bad.append(f"最长行 {mline}")
    if overlaps:
        bad.append(f"重叠 {overlaps} 处")
    if cues and cues[-1][1] > dur + 0.3:
        bad.append(f"末条 {cues[-1][1]:.2f}s 超出成片")
    rec("PASS" if not bad else "FAIL", "P3",
        f"{len(cues)} 条 / {srt_chars} 字 / 最长行 {mline}" + ("" if not bad else "；" + "；".join(bad)))

    # P4 镜头覆盖 + 切点与音轨句读对齐
    shots = None
    if args.scene_plan and Path(args.scene_plan).exists():
        sp = json.loads(Path(args.scene_plan).read_text(encoding="utf-8-sig"))
        shots = []
        for sc in sp.get("scenes", []):
            for sh in sc.get("shots", []):
                shots.append({"id": sh.get("id"), "start": sh.get("start_s"), "end": sh.get("end_s"),
                              "duration": sh.get("duration", (sh.get("end_s", 0) - sh.get("start_s", 0))),
                              "visual_type": sc.get("beat", ""), "picture": sh.get("picture", ""),
                              "line": sh.get("line", ""), "texts": sh.get("texts") or [],
                              "viz": [sh["viz"]] if sh.get("viz") else [], "slot": sh.get("slot", "")})
    elif args.shots and Path(args.shots).exists():
        shots = json.loads(Path(args.shots).read_text(encoding="utf-8-sig"))["shots"]
    if shots:
        gaps = []
        for i in range(len(shots) - 1):
            g = shots[i + 1]["start"] - shots[i]["end"]
            if g > 0.3:
                gaps.append(round(g, 2))
        cover_ok = abs(shots[0]["start"]) < 0.01 and abs(shots[-1]["end"] - dur) <= 0.35
        rec("PASS" if (cover_ok and not gaps) else "FAIL", "P4",
            f"{len(shots)} 镜覆盖 0–{shots[-1]['end']:.2f}s" + ("" if cover_ok else "（首尾未对齐成片）")
            + ("" if not gaps else f"；空洞 {gaps}"))
        # 切点 vs 配音句末：切点从**成片**里检测（不信分镜表，防止"计划已重排、成片还是旧版"）
        # 参考点：字幕里的句末时间（真句读）；不足 5 个再退回配音块尾
        sent_ends = [e for (s0, e, t) in cues if t and t.rstrip().endswith(("。", "？", "！", "；"))]
        chunk_ends = np.array(sent_ends if len(sent_ends) >= 5 else [c["end"] for c in tl["chunks"]])
        sc_out = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-an",
                      "-vf", "fps=4,scale=480:-2,select='gt(scene,0.30)',showinfo", "-f", "null", "NUL"])
        cut_pts = sorted(float(x) for x in re.findall(r"pts_time:\s*([0-9.]+)", sc_out))
        bnd = np.array([p for p in cut_pts if 0.5 < p < dur - 0.5])
        if len(bnd):
            d = np.array([float(np.min(np.abs(chunk_ends - b))) for b in bnd])
            med, p90 = float(np.median(d)), float(np.percentile(d, 90))
            METRICS_EXTRA["shot_cut_median_dev_s"] = med
            METRICS_EXTRA["video_cuts"] = len(bnd)
            lvl = "PASS" if med <= 0.5 else ("WARN" if med <= 1.0 else "FAIL")
            rec(lvl, "P4b", f"镜切点距配音句末 中位 {med:.2f}s / p90 {p90:.2f}s"
                            + ("（画面切点未按当前配音重排）" if med > 0.5 else ""))
    else:
        rec("WARN", "P4", "未提供分镜表，跳过镜头覆盖检查")

    # P5 镜长
    if shots:
        durs = [s["duration"] for s in shots]
        avg = sum(durs) / len(durs)
        short = [s["id"] for s in shots if s["duration"] < 2.0]
        rec("PASS" if not short else "WARN", "P5",
            f"{len(shots)} 镜，平均 {avg:.1f}s" + ("" if not short else f"；<2s 镜 {short}"))

    # P6 静态画面占比（防 PPT）
    st_ratio, st_long = static_ratio(mp4)
    lvl = "PASS" if st_ratio <= 0.25 else ("WARN" if st_ratio <= 0.40 else "FAIL")
    rec(lvl, "P6", f"静态画面占比 {st_ratio*100:.0f}%，**最长连续静态 {st_long:.1f}s**（建议 ≤8s）")

    # P7 黑帧
    out = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(mp4), "-vf",
               "blackdetect=d=0.1:pix_th=0.02", "-an", "-f", "null", "NUL"])
    bl = [float(m.group(1)) for m in re.finditer(r"black_duration:([0-9.]+)", out)]
    total_black = sum(bl)
    METRICS_EXTRA["max_black_seconds"] = round(max(bl), 2) if bl else 0.0
    lvl = "PASS" if total_black <= 1.0 else ("WARN" if total_black <= 5.0 else "FAIL")
    rec(lvl, "P7", f"黑帧 {len(bl)} 段，合计 {total_black:.1f}s" + (f"，最长 {max(bl):.1f}s" if bl else ""))

    # P8 响度
    out = run(["ffmpeg", "-hide_banner", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "NUL"])
    integ = re.findall(r"I:\s+(-?[0-9.]+)\s+LUFS", out)
    peak = re.findall(r"Peak:\s+(-?[0-9.]+)\s+dBFS", out)
    lufs = float(integ[-1]) if integ else float("nan")
    tp = float(peak[-1]) if peak else float("nan")
    lvl = "PASS" if (-15.5 <= lufs <= -12.5 and tp <= -1.5) else ("WARN" if lufs == lufs else "FAIL")
    rec(lvl, "P8", f"{lufs:.1f} LUFS / 真峰值 {tp:.1f} dBFS")

    # P3b 分块 CER（若有逐块日志）
    if args.blocks and Path(args.blocks).exists():
        import csv as _csv
        rows = list(_csv.DictReader(Path(args.blocks).read_text(encoding="utf-8-sig").splitlines()))
        cers = [float(r["CER"].rstrip("%")) / 100 for r in rows if r.get("CER")]
        if cers:
            mx = max(cers)
            METRICS_EXTRA["max_block_cer"] = mx
            lvl = "PASS" if mx <= 0.25 else ("WARN" if mx <= 0.30 else "FAIL")
            rec(lvl, "P3b", f"逐块最大 CER {mx*100:.1f}%（{len(cers)} 块）")

    # P9 delivery promise
    sh_durs = [x["duration"] for x in shots] if shots else []
    metrics = {
        "duration_seconds": round(dur, 3),
        "subtitle_cues": len(cues),
        "static_frame_ratio": round(st_ratio, 4),
        "static_longest_s": round(st_long, 2),
        "mean_shot_seconds": round(sum(sh_durs) / len(sh_durs), 2) if sh_durs else 0.0,
        "shot_count": len(sh_durs),
        "lufs_integrated": round(lufs, 2),
        "true_peak_dbfs": round(tp, 2),
        "black_total_s": round(total_black, 2),
        "max_black_seconds": METRICS_EXTRA.get("max_black_seconds", 0.0),
        "srt_overlaps": overlaps,
        "srt_chars": srt_chars,
        "prose_chars": txt_chars,
    }
    metrics.update(METRICS_EXTRA)
    promise = state.get("delivery_promise") or {}
    for chk in promise.get("checks", []):
        val = metrics.get(chk["metric"])
        if val is None:
            rec("WARN", "P9", f"承诺项 {chk['name']} 的指标 {chk['metric']} 无法取值")
            continue
        ok = eval_op(val, chk["op"], chk["threshold"])
        rec("PASS" if ok else "FAIL", "P9",
            f"承诺「{chk['name']}」{chk['metric']} {val:.3f} {chk['op']} {chk['threshold']} → {'达标' if ok else '未达标'}")

    # P10 签收门
    stages = state.get("stages") or {}
    approvals = state.get("approvals") or []
    gate_names = {a.get("gate") for a in approvals if a.get("approved_by")}
    missing = []
    for k, v in stages.items():
        if v.get("status") != "completed":
            continue
        by_stage = bool(v.get("signed_by") and v.get("signed_at"))
        by_approval = (k in gate_names) or (f"{k}_delivery" in gate_names) or ("video_delivery" in gate_names and k == "video")
        if not (by_stage or by_approval):
            missing.append(k)
    if missing:
        rec("FAIL", "P10", f"标 completed 但无签收记录（stage 或 approvals）：{missing}")
    else:
        video = stages.get("video") or {}
        if video.get("status") == "completed":
            rec("PASS", "P10", f"视频环 completed 且签收人 {video.get('signed_by')}")
        else:
            rec("PASS", "P10", f"视频环状态 {video.get('status', '未标')}，未标完成，符合未签收语义")

    levels = [r["level"] for r in RESULTS]
    verdict = "FAIL" if "FAIL" in levels else ("WARN" if "WARN" in levels else "PASS")
    rep = {"mp4": str(mp4), "srt": str(srt), "verdict": verdict,
           "summary": {"pass": levels.count("PASS"), "warn": levels.count("WARN"), "fail": levels.count("FAIL")},
           "metrics": metrics, "results": RESULTS}
    Path(args.out).write_text(json.dumps(rep, ensure_ascii=False, indent=2), encoding="utf-8")

    # 预检记录（交 Chief 闸门 0.4）
    record = {
        "project": state.get("project", ""),
        "version": state.get("version", ""),
        "checked_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        "inputs": {"mp4": str(mp4), "srt": str(srt), "txt": str(txt),
                   "timeline": args.timeline, "state": args.state,
                   "shots": args.shots or "", "blocks": args.blocks or ""},
        "verdict": verdict,
        "summary": rep["summary"],
        "items": [{"code": r["code"], "level": r["level"], "detail": r["msg"]} for r in RESULTS],
        "metrics": metrics,
    }
    rec_path = Path(args.record) if args.record else Path(args.out).with_name("预检记录.json")
    rec_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"预检记录：{rec_path}")
    for r in RESULTS:
        print(f"[{r['level']}] {r['code']} {r['msg']}")
    print(f"结论：{verdict}　通过 {rep['summary']['pass']} / 建议 {rep['summary']['warn']} / 阻断 {rep['summary']['fail']}")
    return 0 if verdict != "FAIL" else 1


def eval_op(val, op, thr):
    return {">=": val >= thr, "<=": val <= thr, "==": abs(val - thr) < 1e-9,
            ">": val > thr, "<": val < thr}.get(op, False)


if __name__ == "__main__":
    raise SystemExit(main())



