from pathlib import Path
import re
OUT = Path(r"C:\Users\24795\.dsh\bot\workspace\产线A_样本")
SRT = Path(r"C:\Users\24795\.dsh\bot\workspace\董仲舒_拿了大的别再拿小的_字幕.srt")

def ass_t(h, m, s, ms):
    total = int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0
    hh = int(total // 3600); mm = int((total % 3600) // 60); ss = total % 60
    cs = int(round((ss - int(ss)) * 100))
    return f"{hh}:{mm:02d}:{int(ss):02d}.{cs:02d}"

raw = SRT.read_text(encoding="utf-8-sig").replace("\r\n", "\n").strip()
lines = []
for b in raw.split("\n\n"):
    m = re.search(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", b)
    if not m:
        continue
    g = m.groups()
    txt = "".join(x for x in b.split("\n") if "-->" not in x and not x.strip().isdigit()).strip()
    txt = txt.replace("\\", "").replace("{", "（").replace("}", "）")
    lines.append(f"Dialogue: 0,{ass_t(*g[:4])},{ass_t(*g[4:])},Default,,0,0,0,,{txt}")

header = """[Script Info]
ScriptType: v4.00+
PlayResX: 1920
PlayResY: 1080
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Microsoft YaHei,54,&H00ECE8DE,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,1,0,1,3,0,2,90,90,80,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
(OUT / "字幕.ass").write_bytes((header + "\n".join(lines) + "\n").encode("utf-8"))
print("ASS 修复:", len(lines), "条；样例:", lines[0])
