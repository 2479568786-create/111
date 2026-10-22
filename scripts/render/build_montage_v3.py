"""产线A 样本 v3：切点按句末对齐（P4b）、字卡加强动效（P6）、响度走 finalize。"""
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
OUT = WS / "产线A_样本_v3"
SEG = OUT / "seg"
PROXY = OUT / "proxy"
PLAN = WS / "董仲舒_拿了大的别再拿小的_scene_plan.measured.json"
SRT = WS / "董仲舒_拿了大的别再拿小的_字幕.srt"
INDEX = LAB / "clip_index.npz"
FONT = r"C:\Windows\Fonts\msyh.ttc"
W, H, FPS = 1920, 1080, 30

EN = {
    "S01-01": "night subway station, empty convenience store, city street at night",
    "S02-01": "ancient stone carving, weathered stone relief",
    "S04-03": "vegetable garden, green fields, early morning",
    "S06-02": "crowd of people walking, historical street, moody",
    "S08-02": "busy vegetable market stalls in the early morning, crowds",
    "S08-03": "warehouse conveyor belt, packages moving, industrial",
    "S11-01": "closed market with rolling shutters, empty stalls, city skyline at night",
}
CARD_KEYS = ["书影", "竹简", "织机", "古画", "画像砖", "APP", "后台", "截屏", "版面", "界面", "地图",
             "手册", "刑具", "牢房", "遗址", "签约"]


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-600:]}")
    return (p.stdout or "") + (p.stderr or "")


def probe(p: Path) -> float:
    o = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)])
    return float(o.strip().splitlines()[0])


def sentence_ends(srt: Path) -> list[float]:
    raw = srt.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    ends = []
    for b in raw.split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
        if not m:
            continue
        g = list(map(int, m.groups()))
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        txt = "".join(x for x in b.split("\n") if "-->" not in x and not x.strip().isdigit()).strip()
        if txt.endswith(("。", "？", "！", "；")):
            ends.append(round(e, 3))
    return ends


class Search:
    def __init__(self):
        sys.path.insert(0, str(CLIP))
        sys.path.insert(0, str(LAB / ".pylibs"))
        import onnxruntime as ort
        from tokenizers import Tokenizer
        self.sess = ort.InferenceSession(str(CLIP / "model_quantized.onnx"), providers=["CPUExecutionProvider"])
        self.tok = Tokenizer.from_file(str(CLIP / "tokenizer.json"))
        d = np.load(INDEX, allow_pickle=True)
        self.V, self.meta = d["vecs"], json.loads(str(d["meta"]))
        self.dummy = np.zeros((1, 3, 224, 224), dtype=np.float32)

    def top(self, text: str, k: int = 6):
        PAD = 49407
        ids = self.tok.encode(text).ids[:77]
        n = len(ids)
        ids = ids + [PAD] * (77 - n)
        mask = [1] * n + [0] * (77 - n)
        tv = self.sess.run(["text_embeds"], {"pixel_values": self.dummy,
                                             "input_ids": np.array([ids], np.int64),
                                             "attention_mask": np.array([mask], np.int64)})[0]
        tv = np.asarray(tv, np.float32).reshape(1, -1)[0]
        tv /= max(float(np.linalg.norm(tv)), 1e-8)
        sims = self.V @ tv
        best = {}
        for i, s in enumerate(sims):
            f = self.meta[i]["file"]
            if f not in best or s > best[f]:
                best[f] = float(s)
        return sorted(best.items(), key=lambda kv: -kv[1])[:k]


def card(pic_text: str, dur: float, out: Path, n: int) -> None:
    img = Image.new("RGB", (W, H), (16, 18, 22))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 2):
        sh = int(14 + 12 * (y / H))
        d.line([(0, y), (W, y), (W, y + 2), (0, y + 2)], fill=(sh, sh + 2, sh + 6))
    d.rectangle([70, 70, W - 70, H - 70], outline=(120, 110, 90), width=2)
    title = "".join(ch for ch in pic_text if ch not in "。，、；：？！")[:24]
    f1, f2 = ImageFont.truetype(FONT, 76), ImageFont.truetype(FONT, 32)
    d.text((110, 128), "素材占位 · 待替换", font=f2, fill=(150, 140, 120))
    lines, cur = [], ""
    for ch in title:
        cur += ch
        if d.textlength(cur, font=f1) > W - 260:
            lines.append(cur)
            cur = ""
    if cur:
        lines.append(cur)
    y = H // 2 - len(lines) * 52
    for ln in lines:
        d.text((110, y), ln, font=f1, fill=(236, 232, 222))
        y += 108
    png = out.with_suffix(".png")
    img.save(png)
    zi = "in" if n % 2 == 0 else "out"
    zexpr = ("min(zoom+0.0016,1.18)" if zi == "in" else "max(1.18-0.0016*on,1.0)")
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(png),
         "-t", f"{dur:.3f}", "-r", str(FPS), "-threads", "1",
         "-vf", f"zoompan=z='{zexpr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1920x1080:fps=30,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-threads", "2", str(out)])


def clip(src: Path, start: float, dur: float, out: Path) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "2",
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-an",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "8", "-threads", "2", str(out)])


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', default='assign')
    args = ap.parse_args(argv)
    OUT.mkdir(parents=True, exist_ok=True)
    SEG.mkdir(exist_ok=True)
    plan = json.loads(PLAN.read_text(encoding="utf-8-sig"))
    ends = sentence_ends(SRT)
    search = Search()
    clips = sorted(FOOT.glob("*.mp4"))
    durs = {c.name: probe(c) for c in clips}
    recent: list[str] = []

    tasks = []
    for sc in plan["scenes"]:
        for sh in sc["shots"]:
            a, b = float(sh["start_s"]), float(sh["end_s"])
            cuts = [a] + [t for t in ends if a + 0.4 < t < b - 0.4] + [b]
            cuts = sorted(set(round(x, 3) for x in cuts))
            pieces = [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]
            # 超长片段再等分（≤10s）
            final = []
            for s, e in pieces:
                n = max(1, math.ceil((e - s) / 10.0)) if (e - s) > 10.0 else 1
                step = (e - s) / n
                final += [(s + k * step, s + (k + 1) * step) for k in range(n)]
            for s, e in final:
                tasks.append({"slot": sh["id"], "start": round(s, 3), "dur": round(e - s, 3), "picture": sh["picture"],
                              "kind": "card" if (any(k in sh["picture"] for k in CARD_KEYS) and sh["id"] not in EN) else "footage"})

    print(f"总段数 {len(tasks)}（按句末切点）")
    if args.phase == "assign":
        for t in tasks:
            if t["kind"] == "footage":
                pick = None
                for name, _ in search.top(EN.get(t["slot"], "city at night")):
                    if name in recent[-2:] or durs.get(name, 0) < t["dur"] * 0.9:
                        continue
                    pick = name
                    break
                pick = pick or search.top(EN.get(t["slot"], "city at night"))[0][0]
                recent.append(pick)
                t["pick"] = pick
                t["offset"] = round(((len(tasks) * 7) % max(int((durs[pick] - t["dur"]) * 10), 1)) / 10, 1) if durs[pick] > t["dur"] + 1 else 0.0
        (OUT / "tasks.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
        print("分配完成 →", OUT / "tasks.json")
        return 0
    tasks = json.loads((OUT / "tasks.json").read_text(encoding="utf-8"))
    pieces = []
    for n, t in enumerate(tasks):
        out = SEG / f"{n:03d}.mp4"
        if t["kind"] == "card":
            card(t["picture"], t["dur"], out, n)
            t["pick"] = "CARD"
        else:
            srcp = PROXY / t["pick"] if (PROXY / t["pick"]).exists() else FOOT / t["pick"]
            clip(srcp, float(t.get("offset", 0)), t["dur"], out)
        pieces.append(out)
        print(f"  [{n+1}/{len(tasks)}] {t['slot']} {t['dur']:.1f}s {t['kind']} {t['pick']}", flush=True)

    lst = OUT / "concat.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in pieces), encoding="utf-8")
    pic = OUT / "picture.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", "-threads", "2", str(pic)])
    print(f"画面 {probe(pic):.3f}s")
    (OUT / "素材分配.json").write_text(json.dumps(tasks, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())



