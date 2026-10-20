import sys, json, subprocess, numpy as np
from faster_whisper import WhisperModel
clips = json.load(open(sys.argv[1]))["clips"]
media = sys.argv[2]
def ts(s):
    if isinstance(s,(int,float)): return float(s)
    v=0.0
    for p in str(s).split(":"): v=v*60+float(p)
    return v
model = WhisperModel("small.en", device="cpu", compute_type="int8")
out = []
for c in clips:
    a, b = ts(c["in"]), ts(c["out"])
    raw = subprocess.run(["ffmpeg","-v","error","-ss",str(a),"-i",f"{media}/{c['file']}","-t",str(b-a),"-ac","1","-ar","16000","-f","s16le","-"],capture_output=True,check=True).stdout
    audio = np.frombuffer(raw,np.int16).astype(np.float32)/32768
    segs,_ = model.transcribe(audio, word_timestamps=True, vad_filter=True)
    words = [(round(w.start,2), round(w.end,2), w.word.strip()) for s in segs for w in s.words]
    out.append({"label": c["label"], "words": words})
    print(c["label"], "|", " ".join(f"[{w[0]:.1f}]{w[2]}" for w in words), flush=True)
json.dump(out, open(sys.argv[3],"w"), indent=1)
