"""阶段二：按 素材分配_plan.json 逐段渲染（低内存：线程 2），拼成画面再烧字幕混音。"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

WS = Path(r"C:\Users\24795\.dsh\bot\workspace")
FOOT = WS / "董仲舒_素材包" / "实拍素材"
OUT = WS / "产线A_样本"
SEG = OUT / "seg"
VOICE = WS / "tts-lab" / "配音_443_v5.wav"
SRT = WS / "董仲舒_拿了大的别再拿小的_字幕.srt"
FONT = r"C:\Windows\Fonts\msyh.ttc"
W, H, FPS = 1920, 1080, 30


def run(cmd: list[str], check: bool = True) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-600:]}")
    return (p.stdout or "") + (p.stderr or "")


def probe(p: Path) -> float:
    o = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(p)])
    return float(o.strip().splitlines()[0])


def make_card(text: str, dur: float, out: Path) -> None:
    img = Image.new("RGB", (W, H), (16, 18, 22))
    d = ImageDraw.Draw(img)
    for y in range(0, H, 2):
        shade = int(14 + 10 * (y / H))
        d.line([(0, y), (W, y), (W, y + 2), (0, y + 2)], fill=(shade, shade + 2, shade + 6))
    d.rectangle([70, 70, W - 70, H - 70], outline=(120, 110, 90), width=2)
    title = "".join(ch for ch in text if ch not in "。，、；：？！")[:24]
    f_title = ImageFont.truetype(FONT, 76)
    f_tag = ImageFont.truetype(FONT, 32)
    d.text((110, 128), "素材占位 · 待替换", font=f_tag, fill=(150, 140, 120))
    lines, cur = [], ""
    for ch in title:
        cur += ch
        if d.textlength(cur, font=f_title) > W - 260:
            lines.append(cur)
            cur = ch
    if cur:
        lines.append(cur)
    y = H // 2 - len(lines) * 52
    for ln in lines:
        d.text((110, y), ln, font=f_title, fill=(236, 232, 222))
        y += 108
    png = out.with_suffix(".png")
    img.save(png)
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-loop", "1", "-i", str(png),
         "-t", f"{dur:.3f}", "-r", str(FPS), "-threads", "1",
         "-vf", "zoompan=z='min(zoom+0.00030,1.05)':d=1:s=1920x1080:fps=30,format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "21", "-threads", "2", str(out)])


def make_clip(src: Path, start: float, dur: float, out: Path) -> None:
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "2",
         "-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(src), "-an",
         "-vf", f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={FPS},format=yuv420p",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "8", "-threads", "2", str(out)])


def srt_to_ass(srt: Path, ass: Path) -> int:
    raw = srt.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    out = []
    for b in raw.split("\n\n"):
        import re
        tm = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
        if not tm:
            continue
        g = list(map(int, tm.groups()))
        txt = "".join(x for x in b.split("\n") if "-->" not in x and not x.strip().isdigit()).strip()
        txt = txt.replace("\\", "").replace("{", "（").replace("}", "）")
        out.append(f"Dialogue: 0,{g[0]}:{g[1]:02d}:{g[2]:02d}.{g[3]:03d},"
                   f"{g[4]}:{g[5]:02d}:{g[6]:02d}.{g[7]:03d},Default,,0,0,0,,{txt}")
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
    ass.write_text(header + "\n".join(out) + "\n", encoding="utf-8")
    return len(out)


def main() -> int:
    SEG.mkdir(parents=True, exist_ok=True)
    segs = json.loads((OUT / "素材分配_plan.json").read_text(encoding="utf-8"))
    pieces = []
    for n, s in enumerate(segs):
        out = SEG / f"{n:03d}.mp4"
        if out.exists() and out.stat().st_size > 1000:
            pieces.append(out)
            continue
        if s["kind"] == "card":
            make_card(s["picture"], s["dur"], out)
        else:
            make_clip(FOOT / s["pick"], float(s.get("offset", 0)), s["dur"], out)
        pieces.append(out)
        print(f"  [{n+1}/{len(segs)}] {s['slot']} {s['dur']:.1f}s {s['kind']} {s.get('pick','')}", flush=True)

    lst = OUT / "concat.txt"
    lst.write_text("\n".join(f"file '{p.as_posix()}'" for p in pieces), encoding="utf-8")
    pic = OUT / "picture.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0",
         "-i", str(lst), "-c", "copy", "-threads", "2", str(pic)])
    print(f"画面 {probe(pic):.3f}s")

    ass = OUT / "字幕.ass"
    nc = srt_to_ass(SRT, ass)
    final = OUT / "糊塗說_董仲舒_样本_v1.mp4"
    run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-threads", "2",
         "-i", str(pic), "-i", str(VOICE),
         "-vf", f"ass={ass.name}", "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-g", "8", "-threads", "2",
         "-c:a", "aac", "-b:a", "192k", "-t", "443.433", "-movflags", "+faststart", str(final)])
    print(f"OK {final}  {probe(final):.3f}s  字幕 {nc} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

