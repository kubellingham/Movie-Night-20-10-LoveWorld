#!/usr/bin/env python3
"""Render the Movie Night video from timeline.json using ffmpeg.

    python3 build.py --media /path/to/media --out movie_night.mp4

The media folder must hold the files named in timeline.json (the videos and
the song). speech.json (made by detect_speech.py) says when people talk, so
the song can dip under dialogue. Only ffmpeg and the Python standard library
are needed here.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
FPS = "24000/1001"
SR = 48000


def ts(v):
    """'2:29.50' -> 149.5 seconds."""
    if isinstance(v, (int, float)):
        return float(v)
    out = 0.0
    for part in str(v).split(":"):
        out = out * 60 + float(part)
    return out


def hms(t):
    m, s = divmod(t, 60)
    return f"{int(m)}:{s:05.2f}"


def lufs(path, start=None, dur=None):
    cmd = ["ffmpeg", "-hide_banner", "-nostats"]
    if start is not None:
        cmd += ["-ss", str(start), "-t", str(dur)]
    cmd += ["-i", path, "-vn", "-af", "ebur128=framelog=quiet", "-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True).stderr
    return float(re.findall(r"I:\s+(-?[\d.]+) LUFS", err)[-1])


def layout(clips):
    """Work out where each clip starts in the finished video."""
    length = 0.0
    for i, c in enumerate(clips):
        c["_in"], c["_out"] = ts(c["in"]), ts(c["out"])
        c["_dur"] = c["_out"] - c["_in"]
        c["_xd"] = c.get("transition", {}).get("duration", 0.0) if i else 0.0
        c["_start"] = length - c["_xd"] if i else 0.0
        length = c["_start"] + c["_dur"]
    return length


def speech_regions(clips, auto, cfg, total):
    """Times (in the finished video) when someone is talking, merged and padded."""
    raw = []
    for c, a in zip(clips, auto):
        if "speech" in c:
            spans = c["speech"]
        else:
            spans = [[w[0], w[1]] for w in a["words"]]
        for s, e in spans:
            s, e = max(0.0, s), min(c["_dur"], e)
            raw.append([c["_start"] + s - cfg["pad_before"], c["_start"] + e + cfg["pad_after"]])
    raw.sort()
    merged = []
    for s, e in raw:
        if merged and s - merged[-1][1] < cfg["merge_gap"]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [[max(0.0, s), min(total, e)] for s, e in merged]


def envelope(regions, on_db, off_db, ramp, total):
    """Gain points (t, dB): on_db while talking, off_db otherwise, with ramps."""
    pts = [(0.0, off_db)]
    for s, e in regions:
        pts += [(max(0.0, s - ramp), off_db), (s, on_db), (e, on_db), (min(total, e + ramp), off_db)]
    pts.append((total, off_db))
    pts.sort(key=lambda p: p[0])
    clean = []
    for t, v in pts:
        if clean and abs(t - clean[-1][0]) < 1e-6:
            clean[-1] = (t, v)
        else:
            clean.append((t, v))
    return clean


def gain_expr(pts):
    """ffmpeg expression for a piecewise-linear gain in dB, as a linear factor."""
    expr = f"{pts[-1][1]:.3f}"
    for (t0, v0), (t1, v1) in reversed(list(zip(pts, pts[1:]))):
        if t1 - t0 < 1e-6:
            continue
        seg = f"{v0:.3f}+({v1 - v0:.3f})*(t-{t0:.3f})/{t1 - t0:.3f}"
        expr = f"if(lt(t,{t1:.3f}),{seg},{expr})"
    return f"pow(10,({expr})/20)"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--media", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--timeline", default=os.path.join(HERE, "timeline.json"))
    ap.add_argument("--speech", default=os.path.join(HERE, "speech.json"))
    ap.add_argument("--crf", default="19")
    ap.add_argument("--preset", default="medium")
    args = ap.parse_args()

    tl = json.load(open(args.timeline))
    clips, music, dia, loud = tl["clips"], tl["music"], tl["dialogue"], tl["loudness"]
    auto = json.load(open(args.speech)) if os.path.exists(args.speech) else [{"words": []}] * len(clips)
    if len(auto) != len(clips) or any(a.get("label") != c["label"] for a, c in zip(auto, clips) if "label" in a):
        sys.exit("speech.json does not match timeline.json - run detect_speech.py again")

    total = layout(clips)
    regions = speech_regions(clips, auto, dia, total)

    # Even out loudness between the source videos (per file, not per clip).
    src_gain = {}
    for f in sorted({c["file"] for c in clips}):
        src_gain[f] = max(-10.0, min(8.0, loud["source_lufs"] - lufs(os.path.join(args.media, f))))
    song_path = os.path.join(args.media, music["file"])
    song_gain = loud["source_lufs"] - lufs(song_path) + music["level_db"]

    # Stretch the song by jumping back once, and line its ending up with the video's.
    J, J2, xf = music["loop"]["jump_from"], music["loop"]["jump_to"], music["loop"]["crossfade"]
    delay = total - music["last_hit_before_end"] - music["last_hit"] - (J - J2)

    print(f"Total length {hms(total)}  |  song starts at {hms(max(delay, 0))}")
    for i, c in enumerate(clips):
        print(f"  {i + 1:2d}. {hms(c['_start']):>8}  {c['label']}  ({c['file']} {c['in']}-{c['out']})")
    print("Song dips under dialogue at: " + ", ".join(f"{hms(s)}-{hms(e)}" for s, e in regions))

    inputs, f = [], []
    for i, c in enumerate(clips):
        inputs += ["-ss", f"{c['_in']:.3f}", "-t", f"{c['_dur'] + 1:.3f}", "-i", os.path.join(args.media, c["file"])]
        d = c["_dur"]
        f.append(f"[{i}:v]fps={FPS},scale=1920:1080:flags=lanczos,setsar=1,format=yuv420p,"
                 f"trim=duration={d:.4f},setpts=PTS-STARTPTS,settb=AVTB[v{i}]")
        f.append(f"[{i}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,"
                 f"asetpts=PTS-STARTPTS,apad=whole_dur={d:.4f},atrim=0:{d:.4f},"
                 f"volume={src_gain[c['file']] + c.get('film_gain_db', 0.0):.2f}dB[a{i}]")
    n = len(clips)
    inputs += ["-i", song_path]

    # Video: chain the clips with dissolves, then fade in from / out to black.
    prev_v, prev_a = "v0", "a0"
    for i in range(1, n):
        c = clips[i]
        kind = c.get("transition", {}).get("type", "fade")
        f.append(f"[{prev_v}][v{i}]xfade=transition={kind}:duration={c['_xd']}:offset={c['_start']:.4f}[vx{i}]")
        f.append(f"[{prev_a}][a{i}]acrossfade=d={c['_xd']}:c1=tri:c2=tri[ax{i}]")
        prev_v, prev_a = f"vx{i}", f"ax{i}"
    fo = tl["fade_out"]
    f.append(f"[{prev_v}]fade=t=in:st=0:d={tl['fade_in']},fade=t=out:st={total - fo:.3f}:d={fo},"
             f"trim=duration={total:.4f}[vout]")

    # Film sound: full while people talk, lower in between so the song carries it.
    dia_env = envelope(regions, dia["level_db"], dia["between_lines_db"], dia["ramp"], total)
    f.append(f"[{prev_a}]volume='{gain_expr(dia_env)}':eval=frame,"
             f"afade=t=in:st=0:d={tl['fade_in']},afade=t=out:st={total - fo:.3f}:d={fo}[film]")

    # Song: loop once, place it, dip under dialogue, fade at the end.
    s = n
    f.append(f"[{s}:a]aresample={SR},aformat=sample_fmts=fltp:channel_layouts=stereo,asplit=2[sa][sb]")
    f.append(f"[sa]atrim=0:{J + xf / 2:.4f},asetpts=PTS-STARTPTS[sa1]")
    f.append(f"[sb]atrim=start={J2 - xf / 2:.4f},asetpts=PTS-STARTPTS[sb1]")
    f.append(f"[sa1][sb1]acrossfade=d={xf}:c1=qsin:c2=qsin[songloop]")
    if delay >= 0:
        place = f"adelay={int(round(delay * 1000))}:all=1"
    else:
        place = f"atrim=start={-delay:.4f},asetpts=PTS-STARTPTS"
    song_env = envelope(regions, music["duck_db"], 0.0, dia["ramp"], total)
    f.append(f"[songloop]{place},apad,atrim=0:{total:.4f},volume={song_gain:.2f}dB,"
             f"volume='{gain_expr(song_env)}':eval=frame,afade=t=out:st={total - fo:.3f}:d={fo}[song]")
    f.append("[film][song]amix=inputs=2:duration=first:normalize=0[mix]")

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with tempfile.TemporaryDirectory(dir=os.path.dirname(os.path.abspath(args.out))) as tmp:
        graph = os.path.join(tmp, "graph.txt")
        open(graph, "w").write(";\n".join(f))
        video, mix = os.path.join(tmp, "video.mp4"), os.path.join(tmp, "mix.wav")
        print("Rendering picture and sound...", flush=True)
        subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", *inputs,
                        "-filter_complex_script", graph,
                        "-map", "[vout]", "-c:v", "libx264", "-preset", args.preset, "-crf", args.crf,
                        "-pix_fmt", "yuv420p", "-r", FPS, "-an", video,
                        "-map", "[mix]", "-c:a", "pcm_f32le", mix], check=True)

        print("Balancing overall loudness...", flush=True)
        target = f"I={loud['target_lufs']}:TP={loud['true_peak']}:LRA=11"
        err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", mix, "-af",
                              f"loudnorm={target}:print_format=json", "-f", "null", "-"],
                             capture_output=True, text=True).stderr
        m = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
        ln = (f"loudnorm={target}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:"
              f"measured_LRA={m['input_lra']}:measured_thresh={m['input_thresh']}:"
              f"offset={m['target_offset']}:linear=true")
        subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", video, "-i", mix,
                        "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", f"{ln},aresample={SR}",
                        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", "-shortest", args.out],
                       check=True)
    print(f"Done: {args.out}")


if __name__ == "__main__":
    main()
