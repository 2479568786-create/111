#!/usr/bin/env python3
"""剪映交付包生成器：把成片按 SRT 逐句切成「一句一段」的无声画面片段。

用法：
  python jianying_delivery.py --mp4 成片.mp4 --srt 字幕.srt --out 交付_剪映 [--limit 30]

产出（全部落在 --out 目录）：
  clips/s001_<首句>.mp4 ...   一句一段、无声、H.264、30fps
  分镜表.csv                  段号/起止时间/时长/台词/文件名
  字幕.srt                    原字幕（剪映「导入字幕」用）
  口播.txt                    纯口播（剪映「智能朗读」用，若让它念）
  说明_怎么用.md               三步操作

为什么切段而不是给一整条：
  剪映里「识别字幕/导入 SRT」后，字幕块自带时间码；画面按句切成独立片段，
  用户只需把每段拖到对应字幕块下面，天然对齐，不用手动对时间。
"""
import argparse
import csv
import os
import re
import subprocess
import sys


def parse_srt(path):
    with open(path, encoding="utf-8-sig") as f:
        raw = f.read().replace("\r\n", "\n")
    blocks = [b for b in re.split(r"\n{2,}", raw.strip()) if b.strip()]
    cues = []
    for b in blocks:
        lines = [l for l in b.split("\n") if l.strip()]
        if len(lines) < 2:
            continue
        m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[1] if "-->" in lines[1] else lines[0])
        if not m:
            m = re.match(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)", lines[0])
            text_idx = 1
        else:
            text_idx = 2
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = [int(x) for x in m.groups()]
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
        text = " ".join(lines[text_idx:]).strip()
        cues.append({"start": start, "end": end, "text": text})
    return cues


def safe_name(text, maxlen=18):
    t = re.sub(r"[\\/:*?\"<>|，。、！？；：,.!?;:（）()《》【】\s]+", "", text)
    return t[:maxlen] or "seg"


def run(cmd):
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        sys.stderr.write(p.stderr.decode("utf-8", "ignore")[:800] + "\n")
        raise SystemExit("ffmpeg failed")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mp4", required=True)
    ap.add_argument("--srt", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=float, default=0, help="只处理前 N 秒（调试用）")
    ap.add_argument("--crf", default="18")
    ap.add_argument("--fps", default="30")
    a = ap.parse_args()

    os.makedirs(os.path.join(a.out, "clips"), exist_ok=True)
    cues = parse_srt(a.srt)
    if not cues:
        raise SystemExit("SRT 解析失败：没有读到任何字幕块")
    if a.limit:
        cues = [c for c in cues if c["start"] < a.limit]

    rows = []
    for i, c in enumerate(cues, 1):
        name = f"s{i:03d}_{safe_name(c['text'])}.mp4"
        dst = os.path.join(a.out, "clips", name)
        dur = max(0.2, c["end"] - c["start"])
        run(["ffmpeg", "-y", "-v", "error",
             "-ss", f"{c['start']:.3f}", "-t", f"{dur:.3f}",
             "-i", a.mp4, "-an",
             "-r", a.fps, "-c:v", "libx264", "-crf", a.crf, "-preset", "veryfast",
             "-pix_fmt", "yuv420p", dst])
        rows.append({"段号": f"s{i:03d}", "起": f"{c['start']:.2f}", "止": f"{c['end']:.2f}",
                     "时长": f"{dur:.2f}", "台词": c["text"], "文件名": name})

    with open(os.path.join(a.out, "分镜表.csv"), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["段号", "起", "止", "时长", "台词", "文件名"])
        w.writeheader()
        w.writerows(rows)

    # 原样带过去的素材
    with open(a.srt, encoding="utf-8-sig") as f:
        srt_text = f.read()
    with open(os.path.join(a.out, "字幕.srt"), "w", encoding="utf-8") as f:
        f.write(srt_text)

    readme = """# 剪映交付包 · 怎么用（三步）

1. **配音**
   - 想让它念：剪映「文本 → 智能朗读」，把 `口播.txt` 贴进去，选音色、生成。
   - 想自己念：直接「录音」，对着 `口播.txt` 念。
2. **字幕精准卡点**
   - 配音完成后点「文本 → 识别字幕」（让剪映自己转，贴得最准）。
   - 如果识别有错字：把 `字幕.srt` 用「文本 → 导入字幕」覆盖，再校对一遍。
   - 这一步之后，字幕块的起止时间就是全片的时间基准。
3. **画面跟字幕对齐**
   - 把 `clips/` 里的小片段逐个拖到视频轨，**一段对一块字幕**：先点字幕块让它被选中，
     再把画面片段拖到播放头位置，或者拖动片段边缘让它吸到字幕块端点。
   - 顺序按 `分镜表.csv` 的段号；画面比字幕短就够用，长了就把尾部拉短。
   - 全片对完，导出 1080p30。

## 为什么切成小段
一句一段，字幕块和画面片段一一对应，不用手动算时间码；
改某一句只换那一段，不用重排全片。
"""
    with open(os.path.join(a.out, "说明_怎么用.md"), "w", encoding="utf-8") as f:
        f.write(readme)

    print(f"ok cues={len(rows)} out={a.out}")


if __name__ == "__main__":
    main()
