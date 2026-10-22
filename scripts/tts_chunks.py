# -*- coding: utf-8 -*-
"""把纯口播稿切成 TTS 合成分块（12-15 秒/块，约 44-56 有效字）。

规则：
1. 只在整句行边界切，绝不切句子中间；
2. 不跨段（不跨空行分隔的段落），段序与 md 完全一致；
3. 块目标 44-56 有效字（按 218 字/分 ≈ 12.1-15.4 秒）；
4. 单行超 56 字时才在该行的逗号/问号处二次切分。

用法： python tts_chunks.py <纯口播.txt> [语速=218]
输出： 同前缀 _TTS分块.csv （供配音流水线逐块生成 + ASR 验收）
"""
import csv
import re
import sys

PUNCT = "，。、；：“”‘’？！…—－-《》（）()\"'.,;:?!"
COUNT_RE = re.compile(r"[^\s" + re.escape(PUNCT) + r"]")

# 强制断块：这些整句必须收在块尾（后面要留空拍 / 上花字）
FORCE_BREAK = (
    "他把这层意思，压成了六个字。",
)


def eff_len(text: str) -> int:
    return len(COUNT_RE.findall(text))


def split_long_line(line: str, max_len: int):
    """单行超过 max_len 时在该行标点处切分。"""
    if eff_len(line) <= max_len:
        return [line]
    pieces, buf = [], ""
    for ch in line:
        buf += ch
        if ch in "，；：？" and eff_len(buf) >= max_len - 8:
            pieces.append(buf)
            buf = ""
    if buf:
        pieces.append(buf)
    return pieces


def build_chunks(lines, para_id, target_min=44, target_max=56):
    """在一个段落内按行贪心合并。FORCE_BREAK 命中的整句必须落在块尾。"""
    chunks, cur = [], []
    for line in lines:
        for piece in split_long_line(line, target_max):
            if cur and eff_len("".join(cur)) + eff_len(piece) > target_max:
                chunks.append(cur)
                cur = []
            cur.append(piece)
        if line.strip() in FORCE_BREAK and cur:
            chunks.append(cur)
            cur = []
    if cur:
        chunks.append(cur)
    # 尾块过短（<target_min 的一半）且能并入前一块时合并
    if len(chunks) >= 2 and eff_len("".join(chunks[-1])) < target_min // 2:
        merged = eff_len("".join(chunks[-2] + chunks[-1]))
        if merged <= target_max + 2:
            chunks[-2].extend(chunks[-1])
            chunks.pop()
    return [("".join(c), para_id) for c in chunks]


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else "董仲舒_拿了大的别再拿小的_纯口播.txt"
    speed = float(sys.argv[2]) if len(sys.argv) > 2 else 218.0
    with open(src, encoding="utf-8") as f:
        raw = f.read()

    paras, cur = [], []
    for line in raw.splitlines():
        line = line.strip()
        if line:
            cur.append(line)
        elif cur:
            paras.append(cur)
            cur = []
    if cur:
        paras.append(cur)

    rows, total = [], 0
    for i, para in enumerate(paras, 1):
        pid = f"S{i:02d}"
        for j, (text, _) in enumerate(build_chunks(para, pid), 1):
            n = eff_len(text)
            total += n
            rows.append({
                "分块ID": f"{pid}-C{j:02d}",
                "段": pid,
                "有效字数": n,
                "预计秒数": round(n / speed * 60, 1),
                "文本": text,
            })

    out = src.rsplit(".", 1)[0] + "_TTS分块.csv"
    with open(out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["分块ID", "段", "有效字数", "预计秒数", "文本"])
        w.writeheader()
        w.writerows(rows)

    secs = [r["预计秒数"] for r in rows]
    print(f"段落数 {len(paras)} | 分块数 {len(rows)} | 有效字数 {total}")
    print(f"块时长 {min(secs):.1f}s - {max(secs):.1f}s | 合计 {sum(secs)/60:.2f} 分钟")
    bad = [r["分块ID"] for r, s in zip(rows, secs) if s > 16.5 or s < 7.0]
    print("超出 7-16.5 秒的块:", bad if bad else "无")
    print("写出:", out)


if __name__ == "__main__":
    main()
