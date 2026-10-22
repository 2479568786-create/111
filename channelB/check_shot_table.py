#!/usr/bin/env python3
"""分镜表 ↔ 纯口播 逐句对齐校验（视频制作入口检查）。

分工改成「找素材写稿、编剧做编排」之后，两边是不同人交付，
最容易出的事故是：分镜表按「一句一行」排，口播.txt 的断句和它不一致，
于是 SRT、剪映字幕、画面卡点全部错位。

用法：
  python check_shot_table.py --txt 纯口播.txt --csv 分镜表.csv [--col 句子]

判定：
  PASS  行数一致、逐句文字一致（忽略标点/空白）、顺序一致
  FAIL  报出第一处不一致（第几行、两边各是什么）

退出码：0 = PASS，1 = FAIL。
"""
import argparse
import csv
import re
import sys

SENT_SPLIT = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
KEEP = re.compile(r"[\u4e00-\u9fffA-Za-z0-9]")


def norm(s: str) -> str:
    return "".join(KEEP.findall(s or "")).lower()


def split_sentences(text: str):
    out = []
    for line in text.replace("\r\n", "\n").split("\n"):
        line = line.strip()
        if not line:
            continue
        for m in SENT_SPLIT.finditer(line):
            s = m.group(0).strip()
            if norm(s):
                out.append(s)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--txt", required=True, help="纯口播.txt")
    ap.add_argument("--csv", required=True, help="分镜表.csv")
    ap.add_argument("--col", default="句子", help="分镜表里放句子的列名（默认『句子』）")
    a = ap.parse_args()

    with open(a.txt, encoding="utf-8-sig") as f:
        sents = split_sentences(f.read())

    with open(a.csv, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        print("FAIL 分镜表是空的，或者表头没读到")
        return 1
    header = list(rows[0].keys())
    col = a.col if a.col in header else None
    if col is None:
        for cand in ("句子", "台词", "口播", "文本", "内容"):
            if cand in header:
                col = cand
                break
    if col is None:
        print(f"FAIL 分镜表里找不到句子列。现有列：{header}")
        return 1

    csv_sents = [r.get(col, "") for r in rows]
    print(f"口播句数 {len(sents)} ｜ 分镜表行数 {len(rows)} ｜ 用列「{col}」")

    bad = 0
    if len(sents) != len(rows):
        print(f"FAIL 句数不一致：口播 {len(sents)} 句，分镜表 {len(rows)} 行（差 {abs(len(sents)-len(rows))}）")
        bad += 1

    for i, (s, r) in enumerate(zip(sents, csv_sents), 1):
        if norm(s) != norm(r):
            print(f"FAIL 第 {i} 行不一致")
            print(f"     口播：{s}")
            print(f"     分镜：{r}")
            bad += 1
            if bad >= 5:
                print("     …（只列前 5 处）")
                break

    if bad:
        print("结论 FAIL —— 先把两边的断句对齐，再出剪映包，否则字幕和画面必然错位")
        return 1

    total = sum(len(norm(s)) for s in sents)
    print(f"结论 PASS —— {len(sents)} 句逐句一致，共 {total} 个念读字；按 220 字/分约 {total/220:.2f} 分钟")
    return 0


if __name__ == "__main__":
    sys.exit(main())
