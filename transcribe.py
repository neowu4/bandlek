"""Gör om Demucs-stems till noter (Bandle-stil: låten spelas om av syntar i webbläsaren).

Kräver att build.py har körts (stems i cache/sep). Kör med den andra miljön:
    .venv-bp/bin/python transcribe.py            (bara nya låtar)
    .venv-bp/bin/python transcribe.py --force

Skriver public/notes/<id>.json och lägger till "tracks" och "p" (iTunes-klippets URL) i catalog.json.
"""
import json, sys, time, urllib.parse, urllib.request, warnings
from pathlib import Path

import numpy as np
import librosa

warnings.filterwarnings("ignore")
from basic_pitch import ICASSP_2022_MODEL_PATH
from basic_pitch.inference import predict

ROOT = Path(__file__).parent
SEP = ROOT / "cache" / "sep" / "htdemucs_6s"
NOTES = ROOT / "public" / "notes"
ORDER = ["drums", "bass", "piano", "guitar", "other", "vocals"]
# min/max frekvens (Hz), enstämmigt?, lägsta styrka
MELODIC = {
    "bass":   dict(lo=30, hi=420, mono=True, amp=0.22, minlen=90),
    "vocals": dict(lo=80, hi=1100, mono=True, amp=0.25, minlen=90),
    "piano":  dict(lo=55, hi=2500, mono=False, amp=0.30, minlen=70),
    "guitar": dict(lo=70, hi=2000, mono=False, amp=0.30, minlen=70),
    "other":  dict(lo=55, hi=3000, mono=False, amp=0.30, minlen=90),
}
MIN_NOTES = 6


def monophonic(notes):
    out = []
    for n in sorted(notes, key=lambda n: n[0]):
        if out and n[0] < out[-1][1]:
            prev = out[-1]
            if n[3] >= prev[3] * 0.6:
                prev[1] = n[0]
                if prev[1] - prev[0] < 0.05:
                    out.pop()
            else:
                continue
        out.append(list(n))
    return out


def melodic(path, cfg):
    _, _, ev = predict(str(path), ICASSP_2022_MODEL_PATH, onset_threshold=0.5, frame_threshold=0.3,
                       minimum_note_length=cfg["minlen"], minimum_frequency=cfg["lo"], maximum_frequency=cfg["hi"])
    notes = [[float(s), float(e), int(p), float(a)] for s, e, p, a, *_ in ev if a >= cfg["amp"]]
    if cfg["mono"]:
        notes = monophonic(notes)
    notes.sort(key=lambda n: n[0])
    # [start, längd, midi, styrka 0-1]
    return [[round(s, 3), round(e - s, 3), p, round(min(1.0, a), 2)] for s, e, p, a in notes]


def drums(path):
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    hop = 256
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    bands = {"k": (f >= 30) & (f < 150), "s": (f >= 1000) & (f < 4500), "h": (f >= 7000)}
    env = {k: S[m].sum(0) for k, m in bands.items()}
    ref = {k: np.percentile(v, 97) + 1e-9 for k, v in env.items()}
    onsets = librosa.onset.onset_detect(y=y, sr=sr, hop_length=hop, backtrack=False, units="frames", delta=0.06)
    hits = []
    for fr in onsets:
        w = slice(fr, fr + 4)
        t = round(float(fr * hop / sr), 3)
        r = {k: float(env[k][w].max() / ref[k]) for k in env}
        # bastrumma och virvel läcker in i diskanten; kräv tydlig diskant för hi-hat
        if r["k"] > 0.45: hits.append([t, "k", round(min(1, r["k"]), 2)])
        if r["s"] > 0.5 and r["s"] > r["h"] * 0.8: hits.append([t, "s", round(min(1, r["s"]), 2)])
        elif r["h"] > 0.35: hits.append([t, "h", round(min(1, r["h"]), 2)])
    return hits


def itunes_preview(artist, title):
    q = urllib.parse.urlencode({"term": f"{artist} {title}", "entity": "song", "limit": 10, "country": "se"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(f"https://itunes.apple.com/search?{q}", timeout=20) as r:
                res = json.load(r)["results"]
            for x in res:
                if x.get("artistName") == artist and title.lower() in x.get("trackName", "").lower() and x.get("previewUrl"):
                    return x["previewUrl"]
            return next((x["previewUrl"] for x in res if x.get("previewUrl")), None)
        except Exception:
            time.sleep(8 * (attempt + 1))
    return None


def main():
    force = "--force" in sys.argv
    cat_path = ROOT / "public" / "catalog.json"
    catalog = json.loads(cat_path.read_text())
    NOTES.mkdir(parents=True, exist_ok=True)
    for s in catalog:
        out = NOTES / f"{s['id']}.json"
        if out.exists() and not force and s.get("tracks"):
            print(f"✓ {s['t']} (klar sedan tidigare)"); continue
        d = SEP / s["id"]
        if not d.exists():
            print(f"✗ {s['t']}: inga stems, kör build.py först"); continue
        print(f"→ {s['t']} – {s['a']}")
        tracks = {}
        for name in ORDER:
            wav = d / f"{name}.wav"
            if name not in s["stems"] or not wav.exists():
                continue
            ev = drums(wav) if name == "drums" else melodic(wav, MELODIC[name])
            if len(ev) >= MIN_NOTES:
                tracks[name] = ev
            print(f"   {name}: {len(ev)} {'slag' if name == 'drums' else 'noter'}")
        dur = round(float(librosa.get_duration(path=str(d / 'vocals.wav'))), 2)
        out.write_text(json.dumps({"dur": dur, "tracks": tracks}, separators=(",", ":")))
        s["tracks"] = list(tracks)
        if not s.get("p"):
            s["p"] = itunes_preview(s["a"], s["t"])
        cat_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=1))
    print("Klart.")


if __name__ == "__main__":
    main()
