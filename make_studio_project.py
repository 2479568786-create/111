"""把产线A样本 v3（116 段 + 配音 + 字幕）落成 OpenFilm Studio 可编辑工程。"""
from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

WS = Path(r"C:\Users\24795\.dsh\bot\workspace")
SRC = WS / "产线A_样本_v3"
PROJ = WS / "openfilm-lab" / "projects" / "dongzhongshu_sample"
VOICE = WS / "tts-lab" / "配音_443_v5.wav"
SRT = WS / "董仲舒_拿了大的别再拿小的_字幕.srt"
FPS = 30


def run(cmd, check=True):
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        raise RuntimeError(f"{cmd[0]} failed: {p.stderr[-500:]}")
    return p.stdout or ""


def main() -> int:
    proj_seg = PROJ / "seg"
    proj_seg.mkdir(parents=True, exist_ok=True)
    tasks = json.loads((SRC / "tasks.json").read_text(encoding="utf-8"))

    # 1) 段文件硬链接进工程（不复制、不重编码）
    clips = []
    t = 0.0
    for i, task in enumerate(tasks):
        src = SRC / "seg" / f"{i:03d}.mp4"
        dst = proj_seg / f"{i:03d}.mp4"
        if not dst.exists():
            try:
                os.link(src, dst)
            except OSError:
                dst.write_bytes(src.read_bytes())
        dur = float(task["dur"])
        clips.append({"i": i, "src": f"seg/{i:03d}.mp4", "at": round(t, 3), "dur": round(dur, 3),
                      "slot": task["slot"], "kind": task["kind"], "pick": task.get("pick", "")})
        t += dur

    # 2) 配音转 m4a（体积小）
    voice = PROJ / "voice.m4a"
    if not voice.exists():
        run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(VOICE),
             "-c:a", "aac", "-b:a", "192k", str(voice)])

    # 3) film.html：一条轨道 = 116 段视频（按句末切点），另一条 = 字幕页，最上层
    lines = ['<meta name="viewport" content="width=1920, height=1080">',
             "<!-- 产线A 样本 v3 · 由 make_studio_project.py 生成；段落切点=句末，116 段 -->",
             "<section>"]
    for c in clips:
        lines.append(
            f'  <video src="{c["src"]}#t=0,{c["dur"]}" at="{c["at"]}" '
            f'style="left:0;top:0;width:1920px;height:1080px"></video>')
    lines.append("</section>")
    lines.append("<section>")
    lines.append('  <iframe src="captions.html#t=0,443.433"></iframe>')
    lines.append("</section>")
    lines.append("<section>")
    lines.append('  <audio src="voice.m4a" at="0"></audio>')
    lines.append("</section>")
    (PROJ / "film.html").write_text("\n".join(lines) + "\n", encoding="utf-8")

    # 4) captions.html：SRT → frame(t) 显示当前句
    raw = SRT.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
    cues = []
    for b in raw.split("\n\n"):
        m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
        if not m:
            continue
        g = list(map(int, m.groups()))
        s = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        e = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        txt = "".join(x for x in b.split("\n") if "-->" not in x and not x.strip().isdigit()).strip()
        cues.append({"s": round(s, 3), "e": round(e, 3), "t": txt})
    cap_html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
  body {{ margin:0; background:transparent; font-family:"Microsoft YaHei","Noto Sans SC",sans-serif; }}
  #c {{ position:absolute; left:0; right:0; bottom:70px; text-align:center;
        font-size:52px; color:#ECE8DE; text-shadow:0 0 8px #000,0 0 16px #000;
        letter-spacing:1px; line-height:1.35; padding:0 90px; }}
</style></head>
<body><div id="c"></div>
<script>
const CUES = {json.dumps(cues, ensure_ascii=False)};
const box = document.getElementById("c");
let last = "";
window.film = {{
  duration: 443.433,
  frame(t) {{
    let txt = "";
    for (const c of CUES) {{
      if (t >= c.s && t < c.e) {{ txt = c.t; break; }}
    }}
    if (txt !== last) {{ box.textContent = txt; last = txt; }}
  }}
}};
</script></body></html>
"""
    (PROJ / "captions.html").write_text(cap_html, encoding="utf-8")

    meta = {"project": "dongzhongshu_sample", "version": "sample_v3", "duration": round(t, 3),
            "segments": len(clips), "fps": FPS,
            "note": "116 段来自 产线A_样本_v3/seg，切点=句末；配音 voice.m4a；字幕 captions.html",
            "clips": clips}
    (PROJ / "timeline.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"工程已生成 {PROJ}  段数 {len(clips)}  总时长 {t:.3f}s  字幕 {len(cues)} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
