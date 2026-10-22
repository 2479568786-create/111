#!/usr/bin/env python3
"""配音 wav -> 逐帧口型包络 JSON（能量驱动，纯 CPU，本机可行）。

用法：
  python avatar_envelope.py --wav 配音.wav --out envelope.json --fps 30

输出：
  { fps, duration, sr, p95, frames:[0..1], blinks:[秒] }

口径：33ms 窗 RMS -> 按 p95 归一 -> 快起慢落平滑 -> 幂律抬中等音量。
这不是音素级 lip sync（本机无 GPU/torch，跑不动 Wav2Lip/SadTalker），
而是"张嘴幅度跟随人声"的 2D 数字人，7-8 分钟片可实时逐帧渲染。
"""
import argparse
import json
import subprocess

import numpy as np


def decode(wav: str, sr: int = 16000) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-i", wav, "-ac", "1", "-ar", str(sr),
           "-f", "s16le", "-"]
    p = subprocess.run(cmd, capture_output=True)
    if p.returncode != 0:
        raise SystemExit("ffmpeg decode failed: " + p.stderr.decode("utf-8", "ignore")[:400])
    return np.frombuffer(p.stdout, dtype="<i2").astype(np.float32) / 32768.0


def envelope(x: np.ndarray, sr: int, fps: int):
    hop = max(1, int(round(sr / fps)))
    n = max(1, len(x) // hop)
    rms = np.empty(n, dtype=np.float32)
    for i in range(n):
        seg = x[i * hop:(i + 1) * hop]
        rms[i] = float(np.sqrt(np.mean(seg * seg) + 1e-12)) if seg.size else 0.0
    p95 = float(np.percentile(rms, 95)) if n else 1e-6
    p95 = max(p95, 1e-6)
    v = np.clip(rms / (p95 * 0.9), 0.0, 1.0) ** 0.7
    attack = 1.0 - np.exp(-1.0 / (0.040 * fps))
    release = 1.0 - np.exp(-1.0 / (0.120 * fps))
    out = np.empty_like(v)
    prev = 0.0
    for i, val in enumerate(v):
        k = attack if val > prev else release
        prev = prev + (val - prev) * k
        out[i] = prev
    return out, rms, p95


def blink_times(duration: float):
    """确定性眨眼：固定间隔 + 抖动，渲染同一 t 必得同一结果。"""
    out = []
    t = 1.6
    i = 0
    jitter = [0.0, 0.6, -0.4, 0.9, 0.2, -0.7, 0.3, -0.2, 0.8, -0.5]
    while t < duration:
        out.append(round(t, 3))
        t += 3.4 + jitter[i % len(jitter)]
        i += 1
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--sr", type=int, default=16000)
    a = ap.parse_args()

    x = decode(a.wav, a.sr)
    dur = len(x) / a.sr
    env, rms, p95 = envelope(x, a.sr, a.fps)
    data = {
        "fps": a.fps,
        "duration": round(dur, 3),
        "p95": round(p95, 6),
        "frames": [round(float(v), 3) for v in env],
        "blinks": blink_times(dur),
        "source": a.wav,
        "method": "rms-energy-envelope-v1",
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    idx = np.argsort(env)[-5:][::-1] if len(env) else []
    print(f"ok duration={dur:.2f}s frames={len(env)} p95={p95:.4f}")
    if len(idx):
        print("loudest frames at t=", [round(float(i) / a.fps, 2) for i in idx])


if __name__ == "__main__":
    main()
