"""阶段一：算素材分配（CLIP 检索），不编码，输出 素材分配_plan.json。"""
import json, math, re, sys
from pathlib import Path
import numpy as np
from PIL import ImageFont  # 只为确认字体可用

WS = Path(r"C:\Users\24795\.dsh\bot\workspace"); LAB = WS / "tts-lab"
CLIP = LAB / ".clip"; FOOT = WS / "董仲舒_素材包" / "实拍素材"
PLAN = WS / "董仲舒_拿了大的别再拿小的_scene_plan.measured.json"
INDEX = LAB / "clip_index.npz"; OUT = WS / "产线A_样本"
sys.path.insert(0, str(CLIP)); sys.path.insert(0, str(LAB / ".pylibs"))
import onnxruntime as ort
from tokenizers import Tokenizer

PAD = 49407
EN = {
    "S01-01": "night subway station, empty convenience store, city street at night",
    "S02-01": "ancient stone carving, weathered stone relief",
    "S04-03": "vegetable garden, green fields, early morning",
    "S06-02": "crowd of people walking, historical street, moody",
    "S08-02": "busy vegetable market stalls in the early morning, crowds, no faces",
    "S08-03": "warehouse conveyor belt, packages moving, industrial",
    "S11-01": "closed market with rolling shutters, empty stalls, city skyline at night",
}
CARD_KEYS = ["书影","竹简","织机","古画","画像砖","APP","后台","截屏","版面","界面","地图","手册","刑具","牢房","遗址","签约"]

def probe(p):
    import subprocess
    o = subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",str(p)],
                       capture_output=True, text=True)
    return float(o.stdout.strip().splitlines()[0])

sess = ort.InferenceSession(str(CLIP / "model_quantized.onnx"), providers=["CPUExecutionProvider"])
tok = Tokenizer.from_file(str(CLIP / "tokenizer.json"))
d = np.load(INDEX, allow_pickle=True); V = d["vecs"]; meta = json.loads(str(d["meta"]))
dummy = np.zeros((1,3,224,224), dtype=np.float32)

def query(text, top=6):
    ids = tok.encode(text).ids[:77]; n = len(ids)
    ids = ids + [PAD]*(77-n); mask = [1]*n + [0]*(77-n)
    tv = sess.run(["text_embeds"], {"pixel_values": dummy,
        "input_ids": np.array([ids], dtype=np.int64),
        "attention_mask": np.array([mask], dtype=np.int64)})[0]
    tv = np.asarray(tv, dtype=np.float32).reshape(1,-1)[0]; tv /= max(float(np.linalg.norm(tv)),1e-8)
    sims = V @ tv; best = {}
    for i,s in enumerate(sims):
        f = meta[i]["file"]
        if f not in best or s > best[f]: best[f] = float(s)
    return sorted(best.items(), key=lambda kv: -kv[1])[:top]

plan = json.loads(PLAN.read_text(encoding="utf-8-sig"))
clips = sorted(FOOT.glob("*.mp4")); durs = {c.name: probe(c) for c in clips}
segs = []; recent = []
for sc in plan["scenes"]:
    for sh in sc["shots"]:
        dur = float(sh["duration"]); parts = max(1, math.ceil(dur/12.0)); sub = dur/parts
        is_card = any(k in sh["picture"] for k in CARD_KEYS) and sh["id"] not in EN
        for k in range(parts):
            rec = {"slot": sh["id"], "part": k+1, "of": parts,
                   "start": round(float(sh["start_s"]) + k*sub, 3), "dur": round(sub, 3),
                   "picture": sh["picture"], "kind": "card" if is_card else "footage"}
            if not is_card:
                for name, score in query(EN.get(sh["id"], "city scene")):
                    if name in recent[-2:] or durs.get(name,0) < sub*0.9: continue
                    rec["pick"] = name; break
                rec.setdefault("pick", query(EN.get(sh["id"], "city scene"))[0][0])
                recent.append(rec["pick"]); dm = durs[rec["pick"]]
                rec["offset"] = round(((len(segs)*7 + k*11) % max(int((dm-sub)*10),1))/10, 1) if dm > sub+1 else 0.0
            segs.append(rec)
OUT.mkdir(parents=True, exist_ok=True)
(OUT / "素材分配_plan.json").write_text(json.dumps(segs, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"分配 {len(segs)} 段：字卡 {sum(1 for s in segs if s['kind']=='card')} / 实拍 {sum(1 for s in segs if s['kind']=='footage')}")
used = {}
for s in segs:
    if s["kind"] == "footage": used[s["pick"]] = used.get(s["pick"], 0) + 1
print("实拍用到的素材:", used)


