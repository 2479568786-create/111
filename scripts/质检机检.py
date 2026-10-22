#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Chief 质检机检脚本 v1.2 —— 对应 质检清单_v1.md 的 A/B/C/D 闸门。

v1.2 新增（2026-10-19 配音听诊后）：A1 语速口径改 220 字/分；B5 字幕空洞；
C7 长静音（合成坏块/吞段）；C8 响度一致性（-14 LUFS / LRA / 真峰值）。
v1.2.1 修复：parse_srt 毫秒解析（".085" 旧版误算为 0.85s，导致假重叠报警）。
v1.4 新增：闸门 0「流程状态」——`--state 项目状态.json` 校验签收门 / delivery promise / 挂账 resume_from。

用法:
  python 质检机检.py --mp4 成片.mp4 --srt 字幕.srt --txt 纯口播.txt \
      [--facts 事实核查表.csv] [--target-min 8]

输出 [PASS]/[WARN]/[FAIL] 编号 说明，末尾给结论。人判项（A6-A8/C4-C6/D3-D6）不在此处。
"""
import argparse
import csv
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

RESULTS = []  # (level, code, msg)
METRICS = {}  # 供 delivery promise 实测比对用的机检数值
PREFLIGHT = {}  # 预检报告的 metrics，用于与机检交叉核对口径
WPM = 220.0  # 实测校准语速（2026-10-19：1587 字/443.43s = 215 字/分，取整 220 排期）


def _tool(name: str) -> str:
    """ffmpeg/ffprobe 定位：先 PATH，再 WinGet 安装目录。"""
    w = shutil.which(name)
    if w:
        return w
    root = Path(r"C:\Users\24795\AppData\Local\Microsoft\WinGet\Packages")
    if root.exists():
        for p in root.glob(f"Gyan.FFmpeg*/**/bin/{name}.exe"):
            return str(p)
    return name


def rec(level, code, msg):
    RESULTS.append((level, code, msg))


def cjk_alnum_only(s: str) -> str:
    return re.sub(r"[^\u4e00-\u9fff\u3040-\u30ffA-Za-z0-9]", "", s)


def load_txt(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig")


def parse_srt(path: Path):
    raw = path.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    cues = []
    for block in re.split(r"\n\s*\n", raw):
        lines = [ln for ln in block.split("\n") if ln.strip() != ""]
        if not lines:
            continue
        tline = next((ln for ln in lines if "-->" in ln), None)
        if not tline:
            continue
        m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})", tline)
        if not m:
            continue
        g = m.groups()

        def _ts(hh, mm, ss, ms):
            # v1.2.1 修复：毫秒按字面位数换算，".085" = 85/1000 = 0.085s（旧版误算成 0.85s）
            return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / (10 ** len(ms))

        start = _ts(*g[0:4])
        end = _ts(*g[4:8])
        text = "\n".join(ln for ln in lines if "-->" not in ln and not ln.strip().isdigit())
        cues.append({"start": start, "end": end, "text": text})
    return cues


def ffprobe(path: Path):
    exe = _tool("ffprobe")
    try:
        out = subprocess.run(
            [exe, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120,
        )
    except FileNotFoundError:
        return None, "ffprobe 未找到"
    if out.returncode != 0:
        return None, (out.stderr or "").strip()[:200]
    return json.loads(out.stdout), None


# ---------------- A 脚本 ----------------
def gate_a(txt: str, target_min: float):
    body = txt.strip()
    chars = len(cjk_alnum_only(body))
    est_min = chars / WPM
    est_sec = est_min * 60

    dev = abs(est_min - target_min) / target_min
    if dev <= 0.10:
        rec("PASS", "A1", f"有效字数 {chars}，估算 {est_min:.1f} 分钟（目标 {target_min:g} 分钟）")
    elif dev <= 0.15:
        rec("WARN", "A1", f"有效字数 {chars}，估算 {est_min:.1f} 分钟，偏离目标 {dev*100:.0f}%")
    else:
        rec("FAIL", "A1", f"有效字数 {chars}，估算 {est_min:.1f} 分钟，偏离目标 {dev*100:.0f}%（>15%）")

    ex = body.count("！") + body.count("!")
    rec("PASS" if ex == 0 else "FAIL", "A2", f"感叹号 {ex} 个")

    sents = [s.strip() for s in re.split(r"[。？！?!；;…\n]+", body) if s.strip()]
    longs = [s for s in sents if len(cjk_alnum_only(s)) > 40]
    rec("PASS" if not longs else "FAIL", "A3", f"句数 {len(sents)}，40 字以上长句 {len(longs)} 句"
        + ("" if not longs else "：" + " / ".join(s[:28] + "…" for s in longs[:3])))

    digits = [m.start() for m in re.finditer(r"[0-9０-９]", body)]
    if digits:
        locs = []
        for i in digits[:5]:
            locs.append(body[max(0, i - 8):i + 8].replace("\n", "↵"))
        rec("FAIL", "A4", f"阿拉伯数字 {len(digits)} 处：" + " | ".join(locs))
    else:
        rec("PASS", "A4", "无阿拉伯数字，全部汉字读法")

    paras = [p for p in re.split(r"\n\s*\n", body) if p.strip()]
    if len(paras) < 3 and "\n\n" not in body:
        rec("WARN", "A5", f"未检测到段间空行（段落 {len(paras)} 个）")
    else:
        rec("PASS", "A5", f"段落 {len(paras)} 个，段间空行正常")
    return chars, est_sec


# ---------------- B 字幕 ----------------
def gate_b(cues, txt: str, video_dur):
    if not cues:
        rec("FAIL", "B1", "SRT 解析出 0 条字幕")
        return
    srt_norm = "".join(cjk_alnum_only(c["text"]) for c in cues)
    txt_norm = cjk_alnum_only(txt)
    if srt_norm == txt_norm:
        rec("PASS", "B1", f"字幕与口播逐字一致（{len(srt_norm)} 字 / {len(cues)} 条）")
    else:
        i = 0
        while i < min(len(srt_norm), len(txt_norm)) and srt_norm[i] == txt_norm[i]:
            i += 1
        rec("FAIL", "B1", f"字幕与口播不一致：字幕 {len(srt_norm)} 字 vs 口播 {len(txt_norm)} 字，"
                          f"首个差异在第 {i} 字附近 —— 字幕「{srt_norm[max(0,i-8):i+12]}」/ 口播「{txt_norm[max(0,i-8):i+12]}」")

    over18 = [(n, c) for n, c in enumerate(cues, 1) if any(len(ln) > 18 for ln in c["text"].split("\n"))]
    over20 = [x for x in over18 if any(len(ln) > 20 for ln in x[1]["text"].split("\n"))]
    toomany = [n for n, c in enumerate(cues, 1) if len(c["text"].split("\n")) > 2]
    if over20:
        rec("FAIL", "B2", f"{len(over20)} 条字幕单行 >20 字，首条 #{over20[0][0]}：{over20[0][1]['text'][:30]}")
    elif over18 or toomany:
        rec("WARN", "B2", f"单行 >18 字 {len(over18)} 条，超过 2 行 {len(toomany)} 条")
    else:
        rec("PASS", "B2", "单行 ≤18 字、每屏 ≤2 行")

    bad = []
    prev_end = -1.0
    for n, c in enumerate(cues, 1):
        if c["end"] <= c["start"]:
            bad.append(f"#{n} 负/零时长")
        if c["start"] < prev_end - 0.05:
            bad.append(f"#{n} 与上一条重叠 {prev_end - c['start']:.2f}s")
        prev_end = max(prev_end, c["end"])
    last = cues[-1]["end"]
    if video_dur and last > video_dur + 0.3:
        bad.append(f"末条 {last:.2f}s 超出视频时长 {video_dur:.2f}s")
    rec("PASS" if not bad else "FAIL", "B3", "时间码单调、无重叠"
        + (f"，末条 {last:.2f}s" + (f" / 视频 {video_dur:.2f}s" if video_dur else ""))
        + ("" if not bad else "：问题 " + "；".join(bad[:4])))
    METRICS["srt_overlaps"] = len([b for b in bad if "重叠" in b])

    # B5 字幕空洞：相邻字幕之间长空档 = 漏字幕或字幕与配音脱节
    gaps = [(n + 1, cues[n]["start"] - cues[n - 1]["end"]) for n in range(1, len(cues))
            if cues[n]["start"] - cues[n - 1]["end"] > 3.0]
    if cues[0]["start"] > 3.0:
        gaps.insert(0, (1, cues[0]["start"]))
    rec("PASS" if not gaps else "WARN", "B5",
        "字幕无 >3s 空洞" if not gaps else
        f"{len(gaps)} 处字幕空档 >3s（首处 #{gaps[0][0]} {gaps[0][1]:.1f}s）")

    rates, fast, slow = [], [], []
    for n, c in enumerate(cues, 1):
        n_chars = len(cjk_alnum_only(c["text"]))
        dur = max(c["end"] - c["start"], 0.01)
        r = n_chars / dur
        rates.append(r)
        if r > 8.0:
            fast.append((n, r))
        if r < 1.5:
            slow.append((n, r))
    if rates:
        avg = sum(rates) / len(rates)
    if fast:
        rec("WARN", "B4", f"语速 >8 字/秒 {len(fast)} 条（最快 #{fast[0][0]} {fast[0][1]:.1f}）")
    elif slow:
        rec("WARN", "B4", f"语速 <1.5 字/秒 {len(slow)} 条（最慢 #{slow[0][0]} {slow[0][1]:.1f}）")
    else:
        rec("PASS", "B4", f"语速正常，平均 {avg:.1f} 字/秒")


# ---------------- C 成片 ----------------
def gate_c(info, chars, last_cue_end=None):
    fmt = info.get("format", {})
    video = next((s for s in info.get("streams", []) if s.get("codec_type") == "video"), None)
    audios = [s for s in info.get("streams", []) if s.get("codec_type") == "audio"]
    dur = float(fmt.get("duration") or 0.0)
    if not video:
        rec("FAIL", "C1", "没有视频流")
        return dur, 0.0
    w, h = video.get("width"), video.get("height")
    rate = video.get("avg_frame_rate", "0/1")
    try:
        num, den = rate.split("/")
        fps = float(num) / float(den) if float(den) else 0.0
    except Exception:
        fps = 0.0
    codec = video.get("codec_name")
    ok = (w == 1920 and h == 1080 and fps >= 24 and codec in ("h264", "hevc"))
    rec("PASS" if ok else ("FAIL" if not (w and h) else "WARN"), "C1",
        f"{w}x{h} / {fps:.2f}fps / {codec}"
        + ("" if ok else "（要求 1920x1080 ≥24fps h264）"))

    if last_cue_end is not None:
        gap = dur - last_cue_end
        if -5.0 <= gap <= 0.5:
            rec("PASS", "C2", f"成片 {dur:.2f}s / 字幕末条 {last_cue_end:.2f}s，片尾余量 {gap:+.2f}s")
        else:
            rec("FAIL", "C2", f"成片 {dur:.2f}s 与字幕末条 {last_cue_end:.2f}s 差 {gap:+.2f}s（音画对不齐或片尾过长/过短）")
    else:
        rec("WARN", "C2", f"无字幕参考，成片 {dur:.2f}s 未做音画对齐校验")

    if dur and chars:
        wpm = chars / dur * 60
        rec("PASS" if 180 <= wpm <= 330 else "WARN", "C2b",
            f"实际节奏 {wpm:.0f} 字/分（{chars} 字 / {dur:.0f}s），剧本按 {WPM:.0f} 字/分估算，偏差 {abs(wpm-WPM)/WPM*100:.0f}%")

    if not audios:
        rec("FAIL", "C3", f"无音轨（视频 {dur:.2f}s）")
        return dur, 0.0
    adur = float(audios[0].get("duration") or 0.0)
    if not adur:
        adur = dur
    ok = adur >= dur - 0.5
    rec("PASS" if ok else "FAIL", "C3",
        f"音轨 {audios[0].get('codec_name')} {adur:.2f}s / 视频 {dur:.2f}s"
        + ("" if ok else "（音轨明显短于画面）"))
    return dur, adur


# ---------------- C7/C8 音轨质量（配音听诊后的新判据） ----------------
def _run(cmd, timeout=900):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=timeout)
        return (p.stdout or "") + "\n" + (p.stderr or "")
    except Exception as e:  # noqa: BLE001
        return f"__ERR__{e}"


def gate_c_audio(mp4: Path):
    """C7 坏块（静音/电平塌陷）/ C8 响度一致性 —— 听诊后新增，抓合成崩块与「音质不统一」。"""
    exe = _tool("ffmpeg")
    out = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-af", "ebur128=peak=true", "-f", "null", "-"])
    if out.startswith("__ERR__"):
        rec("WARN", "C7", f"ebur128 跑不了：{out[7:80]}")
        rec("WARN", "C8", "ebur128 未测（ffmpeg 不可用）")
        return

    # 每 100ms 一帧的瞬时响度 M（LUFS）
    frames = []
    for ln in out.splitlines():
        m = re.search(r"t:\s*([\d.]+).*?M:\s*(-?[\d.]+)", ln)
        if m:
            frames.append((float(m.group(1)), float(m.group(2))))
    live = sorted(v for _, v in frames if v > -100)
    base = live[len(live) // 2] if live else -23.0          # 有声段基线（中位数）
    thr = min(base - 18.0, -30.0)                          # 低于基线 18 LU 且低于 -30 = 坏块
    blocks, cur = [], None
    for t, v in frames:
        if v <= thr:
            if cur is None:
                cur = [t, t, v]
            else:
                cur[1], cur[2] = t, min(cur[2], v)
        elif cur is not None:
            blocks.append(tuple(cur))
            cur = None
    if cur is not None:
        blocks.append(tuple(cur))
    blocks = [b for b in blocks if b[1] - b[0] >= 1.2]
    if blocks:
        worst = max(blocks, key=lambda b: b[1] - b[0])
        kind = "静音" if worst[2] <= -55 else "电平塌陷"
        msg = (f"{len(blocks)} 处坏块（最长 {worst[1]-worst[0]:.1f}s 在 {worst[0]:.1f}s 起，最低 M {worst[2]:.0f} LUFS，"
               f"有声基线 {base:.0f}）+ 首处 {blocks[0][0]:.1f}s —— 疑似合成崩块/吞段")
        rec("FAIL" if (worst[1] - worst[0]) >= 2.5 else "WARN", "C7",
            msg if worst[1] - worst[0] >= 2.5 else msg + "（" + kind + "，人听确认）")
    else:
        rec("PASS", "C7", f"无 ≥1.2s 坏块（有声基线 {base:.0f} LUFS）")

    mi = re.search(r"Integrated loudness:\s*\n\s*I:\s*(-?[\d.]+)\s*LUFS", out)
    ml = re.search(r"Loudness range:\s*\n\s*LRA:\s*([\d.]+)\s*LU", out)
    mp = re.search(r"True peak:\s*\n\s*Peak:\s*(-?[\d.]+)\s*dBFS", out)
    if not mi:
        rec("WARN", "C8", "未解析到整体响度（ebur128 输出异常）")
        return
    integ, lra, peak = float(mi.group(1)), (float(ml.group(1)) if ml else None), (float(mp.group(1)) if mp else None)
    tags, lvl = [], "PASS"
    if abs(integ + 14.0) > 4.0:
        lvl, _ = "FAIL", tags.append(f"整体响度 {integ:.1f} LUFS 偏离 -14 超过 4 LU")
    elif abs(integ + 14.0) > 1.5:
        lvl, _ = "WARN", tags.append(f"整体响度 {integ:.1f} LUFS 偏离 -14 超过 1.5 LU")
    if lra is not None:
        if lra > 18:
            lvl, _ = "FAIL", tags.append(f"LRA {lra:.1f} LU 过大（响度忽大忽小）")
        elif lra > 12:
            lvl = "FAIL" if lvl == "FAIL" else "WARN"
            tags.append(f"LRA {lra:.1f} LU 偏大")
    if peak is not None:
        if peak > -1.0:
            lvl, _ = "FAIL", tags.append(f"真峰值 {peak:.1f} dBFS 有削波风险")
        elif peak > -1.5:
            lvl = "FAIL" if lvl == "FAIL" else "WARN"
            tags.append(f"真峰值 {peak:.1f} dBFS，未达 ≤-1.5 目标")
    rec(lvl, "C8", f"响度 {integ:.1f} LUFS / LRA {'n/a' if lra is None else format(lra, '.1f')} LU / "
                   f"真峰值 {'n/a' if peak is None else format(peak, '.1f')} dBFS"
                   + ("" if not tags else "：" + "；".join(tags)))
    METRICS.update(lufs=integ, true_peak=peak, lra=lra)


def gate_c10(mp4: Path, promise=None):
    """C10 画面体检（v1.4，借鉴 OpenMontage）：黑帧 / 静态画面占比 / 镜头时长分布。
    用 fps=4 降采样跑三次 ffmpeg，443 秒片约 20–40 秒。
    """
    exe = _tool("ffmpeg")

    # C10a 黑帧（注意：本频道是深色底 + 白字版式，98% 像素偏暗属正常设计，
    #      故 pix_th 压到 0.02、纯黑帧比例门限提到 0.999，只抓「真的什么都没有」的帧）
    out = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-an",
                "-vf", "fps=4,blackdetect=d=0.3:pix_th=0.02:picture_black_ratio_th=0.999", "-f", "null", "-"])
    if out.startswith("__ERR__"):
        rec("WARN", "C10", f"黑帧检测跑不了：{out[7:80]}")
        return
    blk = [float(x) for x in re.findall(r"black_duration:\s*([\d.]+)", out)]
    total_black = sum(blk)
    if blk:
        worst = max(blk)
        rec("FAIL" if worst >= 1.5 else "WARN", "C10a",
            f"黑帧 {len(blk)} 段，最长 {worst:.1f}s，合计 {total_black:.1f}s")
    else:
        rec("PASS", "C10a", "无 ≥0.3s 黑帧")

    # C10b 静态画面占比（freezedetect 冻结段）
    out2 = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-an",
                 "-vf", "fps=4,freezedetect=n=-60dB:d=0.4", "-f", "null", "-"])
    fz = [float(x) for x in re.findall(r"freeze_duration:\s*([\d.]+)", out2)]
    dur = None
    try:
        out3 = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-f", "null", "-"])
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", out3)
        if m:
            dur = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    except Exception:  # noqa: BLE001
        dur = None
    if dur and fz:
        ratio = sum(fz) / dur
        longest = max(fz)
        METRICS["max_static_run_s"] = round(longest, 2)
        lvl = "FAIL" if ratio > 0.65 else ("WARN" if ratio > 0.45 else "PASS")
        rec(lvl, "C10b", f"静态画面 {ratio*100:.0f}%（冻结 {len(fz)} 段 / {sum(fz):.1f}s / 全片 {dur:.0f}s）"
                         f"，最长连续静态 {longest:.1f}s")
    elif dur:
        METRICS["max_static_run_s"] = 0.0
        rec("PASS", "C10b", "静态画面 0%（无 ≥0.4s 冻结段）")

    # C10c 镜头时长分布（scene 变化点）
    out4 = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-an",
                 "-vf", "fps=4,scale=480:-2,select='gt(scene,0.30)',showinfo", "-f", "null", "-"])
    pts = sorted(float(x) for x in re.findall(r"pts_time:\s*([\d.]+)", out4))
    static_ratio = (sum(fz) / dur) if (dur and fz) else 0.0
    if dur and len(pts) >= 3:
        bounds = [0.0] + pts + [dur]
        shots = [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]
        mean = sum(shots) / len(shots)
        p90 = sorted(shots)[int(0.9 * (len(shots) - 1))]
        lvl = "PASS"
        if mean > 10.0:
            lvl = "FAIL"
        elif mean > 6.0:
            lvl = "WARN"
        rec(lvl, "C10c", f"镜头 {len(shots)} 个，平均镜长 {mean:.1f}s（p90 {p90:.1f}s）"
                         f"{'——平均镜长过长，有 PPT 化倾向' if lvl != 'PASS' else ''}")
    elif dur and static_ratio <= 0.2:
        rec("PASS", "C10c", f"连续长镜头（{len(pts)} 个硬切），画面有运动，非幻灯片")
    else:
        rec("WARN", "C10c", f"仅 {len(pts)} 个镜头切点且静态占比 {static_ratio*100:.0f}%，分不清是长镜头还是静帧堆叠")

    # C10d 黑边（letterbox / pillarbox）：4K、21:9、1.9:1 素材混剪时，裁切策略不到位会出现
    out5 = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-an",
                 "-vf", "fps=1,cropdetect=24:16:0", "-f", "null", "-"])
    crops = [(int(w), int(h)) for w, h, _x, _y in re.findall(r"crop=(\d+):(\d+):(\d+):(\d+)", out5)]
    if crops:
        from collections import Counter
        (cw, ch), cnt = Counter(crops).most_common(1)[0]
        ratio = cw / ch if ch else 0
        share = cnt / len(crops)
        lvl = "PASS"
        if abs(ratio - 16 / 9) > 0.15 and share > 0.3:
            lvl = "FAIL"
        elif abs(ratio - 16 / 9) > 0.03 and share > 0.1:
            lvl = "WARN"
        rec(lvl, "C10d", f"有效画面 {cw}×{ch}（{ratio:.2f}:1，占 {share*100:.0f}% 采样帧）"
                         f"{'——有黑边或非 16:9 填充' if lvl != 'PASS' else '，画幅正常'}")

    # 对着 delivery promise 验：video 负责的指标由预检验，Chief 只验自己名下（owner=chief/未填）的
    if promise:
        for c in (promise.get("checks") or []):
            if c.get("owner") == "video":
                continue
            metric = (c.get("metric") or "").strip()
            op, thr = c.get("op"), c.get("threshold")
            val = None
            if metric in ("static_frame_ratio", "static_ratio") and dur:
                val = sum(fz) / dur if fz else 0.0
            elif metric in ("max_black_seconds", "black_seconds", "black_total_s"):
                val = total_black
            elif metric in ("max_static_run_s", "static_longest_s", "max_static_run_le_8s"):
                val = METRICS.get("max_static_run_s")
            elif metric in ("mean_shot_seconds",) and dur and len(pts) >= 3:
                val = dur / (len(pts) + 1)
            elif metric in ("lufs", "integrated_lufs", "lufs_integrated"):
                val = METRICS.get("lufs")
            elif metric in ("true_peak", "true_peak_dbfs"):
                val = METRICS.get("true_peak")
            elif metric == "srt_overlaps":
                val = METRICS.get("srt_overlaps")
            elif metric in ("max_block_cer", "max_cer"):
                val = METRICS.get("max_block_cer")
            if val is None or thr is None:
                rec("WARN", "C10p", f"承诺「{c.get('name')}」的 metric `{metric}` 机检没有对应数值，未验")
                continue
            ok = {">=": val >= thr, "<=": val <= thr, ">": val > thr, "<": val < thr,
                  "==": abs(val - thr) < 1e-9}.get(op, True)
            rec("PASS" if ok else "FAIL", "C10p",
                f"交付承诺「{c.get('name')}」：实测 {val:.2f} {op} {thr} → {'通过' if ok else '违反，不许呈现'}")


# ---------------- 闸门 0 · 流程状态 / 签收门（v1.4） ----------------
def gate_state(path: Path | None):
    """机读 项目状态.json：签收门、delivery promise、挂账项。
    对齐 SOP 8.1 / schemas/project_state.schema.json：completed 阶段必须带 signed_by + signed_at。
    """
    if path is None:
        rec("WARN", "0.1", "未提供 --state 项目状态.json，签收门无法机检（旧片可跳过）")
        return
    if not path.exists():
        rec("FAIL", "0.1", f"项目状态文件不存在：{path}")
        return
    try:
        st = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        rec("FAIL", "0.1", f"项目状态文件解析失败：{e}")
        return
    need = ["project", "version", "status", "stages", "delivery_promise"]
    missing = [k for k in need if k not in st]
    if missing:
        rec("FAIL", "0.1", f"项目状态缺字段：{', '.join(missing)}")
        return

    stages = st.get("stages") or {}
    done = [k for k, v in stages.items() if (v or {}).get("status") == "completed"]
    unsigned = [k for k in done
                if not ((stages[k].get("signed_by") or "").strip() and (stages[k].get("signed_at") or "").strip())]
    if unsigned:
        rec("FAIL", "0.1", f"completed 无签收人/签收时间：{', '.join(unsigned)}（SOP 8.1：没签收不许标 completed）")
    else:
        rec("PASS", "0.1", f"签收门完整：{len(done)} 个阶段 completed，均有 signed_by+signed_at")
    waiting = [k for k, v in stages.items() if (v or {}).get("status") == "awaiting_human"]
    if waiting:
        rec("PASS", "0.1b", f"等待人工签收：{', '.join(waiting)}")

    dp = st.get("delivery_promise") or {}
    checks = dp.get("checks") or []
    bad = [c for c in checks
           if any(c.get(k) in (None, "") for k in ("name", "metric", "op", "threshold"))]
    bad_owner = [c for c in checks if c.get("owner") not in (None, "video", "chief")]
    if not (dp.get("statement") or "").strip():
        rec("WARN", "0.2", "delivery_promise.statement 为空：没有可验证的交付承诺")
    elif bad or bad_owner:
        rec("WARN", "0.2", f"delivery_promise 有 {len(bad)+len(bad_owner)} 条不合规（缺字段或 owner 非法）")
    else:
        own = {}
        for c in checks:
            own[c.get("owner") or "未分派"] = own.get(c.get("owner") or "未分派", 0) + 1
        rec("PASS", "0.2", f"交付承诺：{dp['statement'][:36]}（{len(checks)} 条 check / "
                          + " / ".join(f"{k}×{v}" for k, v in own.items()) + "）")

    hanging = st.get("hanging") or []
    broken = [h.get("item") for h in hanging if not (h.get("resume_from") or "").strip()]
    if broken:
        rec("FAIL", "0.3", f"挂账项缺 resume_from：{', '.join(map(str, broken[:4]))}（恢复参数必须落文件）")
    elif hanging:
        rec("PASS", "0.3", f"挂账 {len(hanging)} 项，均有 resume_from")
    else:
        rec("PASS", "0.3", "无挂账项")
    return st


def gate_preflight(path: Path | None, state: dict | None):
    """0.4 预检验收：渲染前预检记录必须存在、可解析、含 P1–P10；预检 FAIL 时 video 阶段不许标 completed。"""
    if path is None:
        rec("WARN", "0.4", "未提供 --preflight 预检报告.json（视频制作渲染前必交）")
        return
    if not path.exists():
        rec("FAIL", "0.4", f"预检报告不存在：{path}")
        return
    try:
        pf = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as e:  # noqa: BLE001
        rec("FAIL", "0.4", f"预检报告解析失败：{e}")
        return
    results = pf.get("results") or pf.get("items") or []
    codes = {r.get("code") for r in results}
    need = {"P1", "P2", "P3", "P4", "P5", "P6", "P7", "P8", "P9", "P10"}
    miss = sorted(need - codes)
    if miss:
        rec("FAIL", "0.4", f"预检缺检查项：{', '.join(miss)}（预检清单至少 P1–P10）")
        return
    fails = [r for r in results if r.get("level") == "FAIL"]
    PREFLIGHT.update(pf.get("metrics") or {})
    summary = pf.get("summary") or {}
    rec("PASS" if not fails else "WARN", "0.4",
        f"预检报告 {len(results)} 项：PASS {summary.get('pass', '?')} / WARN {summary.get('warn', '?')} / "
        f"FAIL {summary.get('fail', '?')}；verdict {pf.get('verdict')}")
    if fails:
        detail = "；".join(f"{r.get('code')} {str(r.get('msg') or r.get('detail') or '')[:40]}" for r in fails[:4])
        rec("PASS", "0.4a", f"预检 FAIL {len(fails)} 项（待办证据）：{detail}")
    video_status = ((state or {}).get("stages") or {}).get("video", {}).get("status")
    if fails and video_status == "completed":
        rec("FAIL", "0.4b", f"预检 verdict={pf.get('verdict')} 但 video 阶段已标 completed —— 预检不过不许交付")
    elif fails:
        rec("PASS", "0.4b", f"预检 FAIL 与项目状态一致：video={video_status or '未知'}（未当完成交付）")


def gate_c9(log: Path | None):
    """C9 分块 ASR 日志：五列 + 文本类型列、正文块 CER ≤25%、无重复串、判定全 PASS。"""
    if log is None:
        rec("WARN", "C9", "未提供 --asr-log 逐块 ASR 日志（视频制作必交）")
        return
    if not log.exists():
        rec("FAIL", "C9", f"逐块 ASR 日志不存在：{log}")
        return
    with log.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        rec("FAIL", "C9", "逐块 ASR 日志为空")
        return
    keys = {_norm_key(k) for k in rows[0].keys() if k}
    need = {"块号": "块号", "文本类型": "文本类型", "起止秒": "起止秒", "CER": "CER",
            "重试次数": "重试次数", "判定": "判定"}
    miss = [v for k, v in need.items() if _norm_key(k) not in keys]
    if miss:
        rec("FAIL", "C9", f"ASR 日志缺列：{', '.join(miss)}")
        return

    def num(v):
        v = re.sub(r"[^\d.]", "", (v or ""))
        try:
            f = float(v)
        except ValueError:
            return 0.0
        return f / 100 if f > 1.0 else f

    def col(name):
        return next(k for k in rows[0].keys() if _norm_key(k) == _norm_key(name))

    cer_c, txt_c, jd_c = col("CER"), col("文本类型"), col("判定")
    cers = [(r.get(col("块号")), num(r.get(cer_c)), (r.get(txt_c) or "")) for r in rows]
    over = [x for x in cers if x[1] > 0.25 and "文" not in x[2] and "名" not in x[2]]
    over_soft = [x for x in cers if x[1] > 0.30]
    max_cer = max((x[1] for x in cers), default=0.0)
    METRICS["max_block_cer"] = round(max_cer, 4)
    if over_soft:
        rec("FAIL", "C9", f"{len(over_soft)} 块 CER >30%（最高 {max_cer*100:.1f}%），超保守上限")
    elif over:
        rec("FAIL", "C9", f"{len(over)} 块正文 CER >25%：块 {', '.join(map(str, [x[0] for x in over[:4]]))}")
    else:
        rec("PASS", "C9", f"{len(rows)} 块全部 PASS（最高 CER {max_cer*100:.1f}%，无 >25%）")
    dup = [r.get(col("ASR回读")) for r in rows if r.get(col("ASR回读")) and re.search(r"(.{2,6})\1{2,}", r.get(col("ASR回读")) or "")]
    if dup:
        rec("WARN", "C9b", f"{len(dup)} 块 ASR 回读含重复串，人听确认")


def gate_cross():
    """0.5 口径交叉核对：预检与机检对同名指标的算法可能不同，差太多说明有一边在骗人。"""
    if not PREFLIGHT:
        return
    pairs = [
        ("static_longest_s", METRICS.get("max_static_run_s"), "最长连续静态"),
        ("max_block_cer", METRICS.get("max_block_cer"), "分块最大 CER"),
    ]
    for key, mine, label in pairs:
        theirs = PREFLIGHT.get(key)
        if theirs is None or mine is None:
            continue
        hi, lo = max(float(theirs), float(mine)), min(float(theirs), float(mine))
        if lo > 0 and hi / lo > 2.0:
            rec("WARN", "0.5", f"「{label}」两个口径差 {hi/lo:.1f} 倍：预检 {theirs} vs 机检 {mine}（须统一算法后再判承诺）")
        else:
            rec("PASS", "0.5", f"「{label}」口径一致：预检 {theirs} / 机检 {round(float(mine), 2)}")


# ---------------- D 事实口径（版权审核已于 2026-10-20 按用户要求停用） ----------------
def _norm_key(k: str) -> str:
    return re.sub(r"[\s_\-]", "", k.lower())


def gate_facts(facts: Path | None):
    """只查事实核查表：有「依据/出处」列、有数据行。素材来源/授权/白名单/红线一律不判。"""
    if not facts:
        rec("WARN", "D4", "未提供事实核查表.csv，事实口径无法机检")
        return
    with facts.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        rec("FAIL", "D4", "事实核查表为空")
        return
    keys = {_norm_key(k) for k in rows[0].keys() if k}
    has = any(k in keys for k in ("依据", "出处", "来源", "source"))
    rec("PASS" if has else "WARN", "D4", f"事实核查表 {len(rows)} 条"
        + ("" if has else "，未见「依据/出处」列"))


SENT_SPLIT = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_KEEP = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def _sentences(text: str):
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        for m in SENT_SPLIT.finditer(line):
            seg = m.group(0).strip()
            if _KEEP.search(seg):
                out.append(seg)
    return out


def gate_shot(txt: str, path: Path | None):
    """A10：纯口播与分镜表逐句一致（新分工下两个作者，断句不一致=字幕画面全错位）。"""
    if path is None:
        rec("WARN", "A10", "未提供 --shot-table 分镜表，口播与分镜对齐无法机检")
        return
    if not path.exists():
        rec("FAIL", "A10", f"分镜表不存在：{path}")
        return
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        rec("FAIL", "A10", "分镜表为空")
        return
    col = next((k for k in rows[0].keys() if _norm_key(k) in ("句子", "台词", "口播", "文本")), None)
    if col is None:
        rec("FAIL", "A10", f"分镜表缺「句子/台词」列（现有：{', '.join(rows[0].keys())}）")
        return
    sents = _sentences(txt)
    norm = lambda x: re.sub(r"[^\u4e00-\u9fffA-Za-z0-9]", "", x or "").lower()
    if len(sents) != len(rows):
        rec("FAIL", "A10", f"句数不一致：口播 {len(sents)} 句 / 分镜表 {len(rows)} 行"
                           f"（差 {abs(len(sents)-len(rows))}）——断句不对齐，字幕与画面必然错位")
        return
    for i, (a, b) in enumerate(zip(sents, rows), 1):
        if norm(a) != norm(b.get(col)):
            rec("FAIL", "A10", f"第 {i} 句不一致：口播「{a[:24]}」/ 分镜「{str(b.get(col))[:24]}」")
            return
    rec("PASS", "A10", f"{len(sents)} 句与分镜表逐句一致")

    # A11：分镜表结构化校验（类型四值 / 要点数据 / 连续录屏 / 未核数字）
    need_cols = ["句序", "句子", "镜号", "画面", "预计秒", "类型", "要点数据"]
    have = {_norm_key(k): k for k in rows[0].keys() if k}
    miss = [c for c in need_cols if _norm_key(c) not in have]
    if miss:
        rec("FAIL", "A11", f"分镜表缺列：{', '.join(miss)}（需 7 列：句序/句子/镜号/画面/预计秒/类型/要点数据）")
        return
    type_col, data_col = have[_norm_key("类型")], have[_norm_key("要点数据")]
    ok_types = {"录屏", "字卡", "动效", "图形"}
    bad_type, missing_data, pending, long_copy = [], [], [], []
    dist = {}
    for i, r in enumerate(rows, 1):
        t = (r.get(type_col) or "").strip()
        d = (r.get(data_col) or "").strip()
        dist[t] = dist.get(t, 0) + 1
        if t not in ok_types:
            bad_type.append(f"第{i}行「{t or '空'}」")
        if t and t != "录屏" and not d:
            missing_data.append(f"第{i}行({t})")
        if "待补" in d or "未核" in d:
            pending.append(f"第{i}行")
        if t == "字卡" and d:
            m = re.search(r"文案[=＝]([^;；]+)", d)
            if m and len(_KEEP.findall(m.group(1))) > 12:
                long_copy.append(f"第{i}行 {len(_KEEP.findall(m.group(1)))} 字")
    if bad_type:
        rec("FAIL", "A11", f"类型不在四值内：{'、'.join(bad_type[:4])}（只认 录屏/字卡/动效/图形）")
    elif missing_data:
        rec("FAIL", "A11", f"{len(missing_data)} 行非录屏却没填要点数据：{'、'.join(missing_data[:4])}")
    else:
        rec("PASS", "A11", "分镜表 7 列齐全，类型全在四值内：" +
            " / ".join(f"{k}×{v}" for k, v in sorted(dist.items(), key=lambda x: -x[1])))

    run, worst = 0, 0
    for r in rows:
        if (r.get(type_col) or "").strip() == "录屏":
            run += 1
            worst = max(worst, run)
        else:
            run = 0
    if worst > 3:
        rec("WARN", "A11b", f"连续 {worst} 行都是录屏——确认期间有叠加/放大等变化（规则：≤3 句须有一次变化）")
    else:
        rec("PASS", "A11b", f"连续录屏最长 {worst} 行（≤3）")

    if pending:
        rec("WARN", "A11c", f"{len(pending)} 行要点数据标「待补/未核」：{'、'.join(pending[:4])}"
                           "——不得渲染数字，等核实后再渲")
    if long_copy:
        rec("WARN", "A11d", f"字卡文案超 12 字：{'、'.join(long_copy[:3])}（需拆卡）")


def gate_b6(mp4: Path, cues, n_sents: int = 0):
    """B6：字幕卡点误差——每条字幕起点 vs 实际语音起点。
    仅适用于「一句一条字幕」（剪映流程）；若字幕比句子更碎，本项不适用，只提示。
    """
    if not cues:
        return
    if n_sents and len(cues) != n_sents:
        rec("WARN", "B6", f"字幕 {len(cues)} 条 / 句子 {n_sents} 句——不是一句一条，B6 卡点误差不适用"
                          "（剪映流程应一句一条，导入后请核对）")
        return
    exe = _tool("ffmpeg")
    out = _run([exe, "-hide_banner", "-nostats", "-i", str(mp4), "-vn",
                "-af", "silencedetect=noise=-38dB:d=0.18", "-f", "null", "-"])
    if out.startswith("__ERR__"):
        rec("WARN", "B6", f"语音起点检测失败：{out[7:80]}")
        return
    starts = [float(x) for x in re.findall(r"silence_start:\s*(-?[\d.]+)", out)]
    ends = [float(x) for x in re.findall(r"silence_end:\s*([\d.]+)", out)]
    onsets = [0.0] + ends
    onsets = sorted(set(v for v in onsets if v >= 0))
    if not onsets:
        rec("WARN", "B6", "没有检测到语音段")
        return
    devs = []
    for c in cues:
        near = min(onsets, key=lambda x: abs(x - c["start"]))
        devs.append(abs(near - c["start"]))
    devs_sorted = sorted(devs)
    med = devs_sorted[len(devs_sorted) // 2]
    p90 = devs_sorted[int(0.9 * (len(devs_sorted) - 1))]
    bad = sum(1 for d in devs if d > 0.30)
    lvl = "PASS"
    if med > 0.15 or bad > 0:
        lvl = "FAIL"
    elif p90 > 0.25:
        lvl = "WARN"
    rec(lvl, "B6", f"卡点误差：中位 {med:.2f}s / p90 {p90:.2f}s / 最大 {max(devs):.2f}s"
                   f"，超 0.30s 的 {bad} 条（{len(cues)} 条字幕）"
                   + ("" if lvl == "PASS" else "——剪映里重新识别或手动对齐字幕"))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mp4")
    ap.add_argument("--srt")
    ap.add_argument("--txt", required=True)
    ap.add_argument("--facts")
    ap.add_argument("--state", help="项目状态.json（签收门 / delivery promise / 挂账项）")
    ap.add_argument("--preflight", help="预检报告.json（视频制作渲染前预检记录）")
    ap.add_argument("--asr-log", help="逐块 ASR 日志 csv（C9：CER 分档 / 文本类型 / 重复串）")
    ap.add_argument("--shot-table", help="分镜表 csv（A10：与纯口播逐句一致）")
    ap.add_argument("--mode", choices=["auto", "delivery", "test"], default="auto",
                    help="auto=读 项目状态.release_channel（test 降级/否则 delivery）；"
                         "delivery=交付/发布版（红线阻断）；test=测试版（红线 WARN，仅限内部预览）")
    ap.add_argument("--target-min", type=float, default=8.0)
    a = ap.parse_args()

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    RESULTS.clear()
    METRICS.clear()

    txt = load_txt(Path(a.txt))
    st = gate_state(Path(a.state) if a.state else None)
    channel = (st or {}).get("release_channel")
    mode = a.mode if a.mode != "auto" else ("test" if str(channel).strip().lower() == "test" else "delivery")
    if mode == "test":
        rec("WARN", "1.0", f"测试版模式（{'release_channel=test' if a.mode == 'auto' else '--mode test'}）："
                           "本结论仅对内部预览有效，不得对外发布；红线素材按 WARN 记，"
                           "发布前须改为 delivery 并清零（改 release_channel 或加 --mode delivery）")
    elif channel and str(channel).strip().lower() not in ("delivery", "publish", "release"):
        rec("WARN", "0.1c", f"release_channel='{channel}' 不是 test/delivery，按交付版从严判（红线阻断）")
    gate_preflight(Path(a.preflight) if a.preflight else None, st)
    chars, est_sec = gate_a(txt, a.target_min)
    gate_shot(txt, Path(a.shot_table) if a.shot_table else None)

    cues, video_dur = [], None
    if a.srt:
        cues = parse_srt(Path(a.srt))
    else:
        rec("WARN", "B0", "未提供 srt，跳过字幕闸门")

    if a.mp4:
        info, err = ffprobe(Path(a.mp4))
        if err:
            rec("WARN", "C0", f"ffprobe 读取失败：{err}")
        else:
            video_dur, _ = gate_c(info, chars, cues[-1]["end"] if cues else None)
            gate_c_audio(Path(a.mp4))
    else:
        rec("WARN", "C0", "未提供 mp4，跳过成片闸门")

    if cues:
        gate_b(cues, txt, video_dur)
        if a.mp4:
            gate_b6(Path(a.mp4), cues, len(_sentences(txt)))

    gate_c9(Path(a.asr_log) if a.asr_log else None)

    # C10 放在 B / C9 之后跑：promise 里 chief 名下的 srt_overlaps / max_block_cer 才有数可对
    if a.mp4:
        promise = None
        if st:
            dp = st.get("delivery_promise") or {}
            promise = {"statement": dp.get("statement"),
                       "checks": [c for c in (dp.get("checks") or []) if c.get("owner") != "video"]}
        gate_c10(Path(a.mp4), promise)
        gate_cross()

    gate_facts(Path(a.facts) if a.facts else None)

    fails = [r for r in RESULTS if r[0] == "FAIL"]
    warns = [r for r in RESULTS if r[0] == "WARN"]
    RESULTS.sort(key=lambda r: r[1])
    for level, code, msg in RESULTS:
        mark = {"PASS": "[PASS]", "WARN": "[WARN]", "FAIL": "[FAIL]"}[level]
        print(f"{mark} {code} {msg}")
    print()
    print(f"结论：{'放行' if not fails else '退回（阻断 %d 项）' % len(fails)}"
          f"　阻断 {len(fails)} / 建议 {len(warns)} / 通过 {len(RESULTS)-len(fails)-len(warns)}")
    return 0 if not fails else 1


if __name__ == "__main__":
    sys.exit(main())
