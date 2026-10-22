"""产线 A 样本片：按 measured scene_plan 的 32 个镜头槽，用本地素材 + 字卡拼成画面，
烧字幕、配 v5（杰哥说）配音，产出 443.433s 成片。

流程：镜头槽 →(CLIP 检索/字卡)→ 每槽一或多段 1080p30 片段 → concat → 烧字幕 → 混音 → mp4
"""
from __future__ import annotations

import json
import math
import re
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

WS = Path(r"C:\Users\24795\.dsh\bot\workspace")
LAB = WS / "tts-lab"
CLIP = LAB / ".clip"
FOOT = WS / "董仲舒_素材包" / "实拍素材"
OUT = WS / "产线A_样本"
PLAN = WS / "董仲舒_拿了大的别再拿小的_scene_plan.measured.json"
VOICE = LAB / "配音_443_v5.wav"
SRT = WS / "董仲舒_拿了大的别再拿小的_字幕.srt"
INDEX = LAB / "clip_index.npz"

sys.path.insert(0, str(CLIP))
sys.path.insert(0, str(LAB / ".pylibs"))
import onnxruntime as ort
from tokenizers import Tokenizer

MEAN = np.array([0.48145466, 0.4578275, 0.40821073], dtype=np.float32)
STD = np.array([0.26862954, 0.26130258, 0.27577711], dtype=np.float32)
PAD = 49407
W, H, FPS = 1920, 1080, 30

# 镜头槽 → 英文视觉短语（名词+形容词，给 CLIP 用；字卡槽不查）
EN = {
    "S01-01": "night subway station, empty convenience store, city street at night",
    "S02-01": "ancient stone carving, weathered stone relief, museum close-up",
    "S04-03": "vegetable garden, green fields, early morning light",
    "S06-02": "crowd of people walking, historical street, moody",
    "S08-02": "busy vegetable market stalls in the early morning, crowds, no faces",
    "S08-03": "warehouse conveyor belt, packages moving, industrial",
    "S11-01": "closed market with rolling shutters, empty stalls, city skyline at night",
}
CARD_KEYS = ["书影", "竹简", "石刻", "织机", "耕织图", "古画", "画像砖", "图形", "饼图", "天平",
             "柱状", "阵列", "数字滚动", "APP", "后台", "截屏", "版面", "界面", "遗址", "球场",
             "刑具", "牢房", "签约", "地图", "手册", "竖排", "极简"]
FONT = r"C:\Windows\Fonts\msyh.ttc"


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-800:]}")
    return (p.stdout or "") + (p.stderr or "")


def probe_dur(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(path)])
    return float(out.strip().splitlines()[0])


class ClipSearch:
    def __init__(self):
        self.sess = ort.InferenceSession(str(CLIP / "model_quantized.onnx"), providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(CLIP / "tokenizer.json"))
        d = np.load(INDEX, allow_pickle=True)
        self.V = d["vecs"]
        self.meta = json.loads(str(d["meta"]))
        self.dummy_img = np.zeros((1, 3, 224, 224), dtype=np.float32)

    def query(self, text: str, top: int = 4):
        ids = self.tok.encode(text).ids[:77]
        n = len(ids)
        ids = ids + [PAD] * (77 - n)
        mask = [1] * n + [0] * (77 - n)
        tv = self.sess.run(["text_embeds"], {"pixel_values": self.dummy_img,
                                             "input_ids": np.array([ids], dtype=np.int64),
                                             "attention_mask": np.array([mask], dtype=np.int64)})[0]
        tv = np.asarray(tv, dtype=np.float32).reshape(1, -1)[0]
        tv /= max(float(np.linalg.norm(tv)), 1e-8)
        sims = self.V @ tv
        best = {}
        for i, s in enumerate(sims):
            f = self.meta[i]["file"]
            if f not in best or s > best[f][0]:
                best[f] = (float(s), self.meta[i]["t"])
        return sorted(best.items(), key=lambda kv: -kv[1][0])[:top]


def make_card(text: str, idx: int, dur: float, out: Path) -> None:
    img = Image.new("RGB", (W, H), (16, 18, 22))
    d = ImageDraw.Draw(img)
    # 水墨感的暗底 + 细边
    for y in range(H):
        shade = int(14 + 10 * (y / H))
        d.line([(0, y), (W, y)], fill=(shade, shade + 2, shade + 6))
    d.rectangle([70, 70, W - 70, H - 70], outline=(120, 110, 90), width=2)
    title = re.sub(r"[。，、；：？！]", "", text)[:26]
    f1 = ImageFont.truetype(FONT, 78)
    f2 = ImageFont.truetype(FONT, 34)
    d.text((110, 130), "素材占位 · 待替换", font=f2, fill=(150, 140, 120))
    # 简易换行
    lines, cur = [], ""
    for ch in title:
        cur += ch
        if d.textlength(cur, font=f1) > W - 260:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    y = H // 2 - len(lines) * 55
    for ln in lines:
        d.text((110, y), ln, font=f1, fill=(236, 232, 222))
        y += 110
    png = out.with_suffix(".png")
    img.save(png)
    # 缓慢推近，避免静态
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(png),
         "-t", f"{dur:.3f}", "-r", str(FPS),
         "-vf", "zoompan=z='min(zoom+0.00035,1.06)':d=1:s=1920x1080:fps=30,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-movflags", "+faststart",
         str(out)])


def make_clip(src: Path, start: float, dur: float, out: Path) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
         "-i", str(src), "-an",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "8", "-movflags", "+faststart",
         str(out)])


def srt_to_ass(srt: Path, ass: Path) -> int:
    raw = srt.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    blocks = re.split(r"\n\s*\n", raw)
    lines_out = []
    for b in blocks:
        tm = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
        if not tm:
            continue
        g = list(map(int, tm.groups()))
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        txt = "".join(x for x in b.split("\n") if "-->" not in x and not x.strip().isdigit()).strip()
        txt = txt.replace("\\", "").replace("{", "（").replace("}", "）")
        lines_out.append(f"Dialogue: 0,{g[0]}:{g[1]:02d}:{g[2]:02d}.{g[3]:03d},{g[4]}:{g[5]:02d}:{g[6]:02d}.{g[7]:03d},Default,,0,0,0,,{txt}")
    header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,52,&H00ECE8DE,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,1,0,1,3,0,2,90,90,90,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    ass.write_text(header + "\n".join(lines_out) + "\n", encoding="utf-8-sig")
    return len(lines_out)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    seg = OUT / "seg"
    seg.mkdir(exist_ok=True)
    plan = json.loads(PLAN.read_text(encoding="utf-8-sig"))
    search = ClipSearch()
    clips = sorted(FOOT.glob("*.mp4"))
    durs = {c.name: probe_dur(c) for c in clips}
    print(f"素材 {len(clips)} 段")

    slots = [(sc["id"], sh) for sc in plan["scenes"] for sh in sc["shots"]]
    used_seq = []
    pieces = []
    report = []
    for n, (sid, sh) in enumerate(slots):
        dur = float(sh["duration"])
        start = float(sh["start_s"])
        is_card = any(k in sh["picture"] for k in CARD_KEYS) and sid not in EN
        # 长槽按 ≤10s 细分，不同起点取不同画面段
        parts = max(1, math.ceil(dur / 10.0))
        sub = dur / parts
        for k in range(parts):
            out = seg / f"{n:03d}_{k}.mp4"
            t0 = start + k * sub
            if is_card:
                make_card(sh["picture"] + (f" {k+1}/{parts}" if parts > 1 else ""), n, sub, out)
                pick = "CARD"
            else:
                cands = search.query(EN.get(sid, "city scene"), top=6)
                pick = None
                for name, (score, _t) in cands:
                    if name in used_seq[-2:]:
                        continue
                    if durs.get(name, 0) < sub * 0.9:
                        continue
                    pick = name
                    break
                if pick is None:
                    pick = cands[0][0]
                used_seq.append(pick)
                dm = durs[pick]
                off = ((n * 7 + k * 11) % max(int((dm - sub) * 10), 1)) / 10 if dm > sub + 1 else 0.0
                make_clip(FOOT / pick, off, sub, out)
            pieces.append(out)
            report.append({"slot": sh["id"], "part": k + 1, "of": parts, "start": round(t0, 3),
                           "dur": round(sub, 3), "kind": "card" if is_card else "footage", "pick": pick})
        print(f"  {sh['id']} {dur:5.1f}s → {parts} 段 {pick if not is_card else 'card'}")

    lst = OUT / "concat.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in pieces), encoding="utf-8")
    pic = OUT / "picture.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", str(pic)])
    pdur = probe_dur(pic)
    print(f"画面拼接完成 {pdur:.3f}s")

    ass = OUT / "字幕.ass"
    ncues = srt_to_ass(SRT, ass)
    final = OUT / "糊塗說_董仲舒_样本_v1.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(pic), "-i", str(VOICE),
         "-vf", f"ass={ass.name}", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "8",
         "-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart", str(final)], )
    (OUT / "素材分配.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK {final}  {probe_dur(final):.3f}s  字幕 {ncues} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
