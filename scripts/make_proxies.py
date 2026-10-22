"""素材代理：4K → 1080p30 密关键帧，供逐段裁剪（低内存、裁剪准）。"""
import subprocess, sys
from pathlib import Path
SRC = Path(r"C:\Users\24795\.dsh\bot\workspace\董仲舒_素材包\实拍素材")
OUT = Path(r"C:\Users\24795\.dsh\bot\workspace\产线A_样本_v3\proxy")
OUT.mkdir(parents=True, exist_ok=True)
for f in sorted(SRC.glob("*.mp4")):
    dst = OUT / f.name
    if dst.exists() and dst.stat().st_size > 10000:
        continue
    cmd = ["ffmpeg","-hide_banner","-loglevel","error","-y","-threads","2","-i",str(f),"-an",
           "-vf","scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps=30,format=yuv420p",
           "-c:v","libx264","-preset","veryfast","-crf","20","-g","8","-threads","2",str(dst)]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(("OK " if p.returncode==0 else "FAIL ")+f.name, flush=True)
    if p.returncode != 0:
        print(p.stderr[-300:])
print("代理完成", len(list(OUT.glob('*.mp4'))), "个")
