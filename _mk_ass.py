from pathlib import Path
import re
OUT = Path(r"C:\Users\24795\.dsh\bot\workspace\产线A_样本")
SRT = Path(r"C:\Users\24795\.dsh\bot\workspace\董仲舒_拿了大的别再拿小的_字幕.srt")
raw = SRT.read_text(encoding="utf-8-sig").replace("\r\n","\n").strip()
lines=[]
for b in raw.split("\n\n"):
    m=re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
    if not m: continue
    g=list(map(int,m.groups()))
    txt="".join(x for x in b.split("\n") if "-->" not in x and not x.strip().isdigit()).strip()
    txt=txt.replace("\\","").replace("{","（").replace("}","）")
    lines.append(f"Dialogue: 0,{g[0]}:{g[1]:02d}:{g[2]:02d}.{g[3]:03d},{g[4]}:{g[5]:02d}:{g[6]:02d}.{g[7]:03d},Default,,0,0,0,,{txt}")
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
(OUT/"字幕.ass").write_bytes((header + "\n".join(lines) + "\n").encode("utf-8"))
print("ASS 无 BOM，字幕条数", len(lines))
