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
    "piano":  dict(lo=55, hi=2500, mono=False, amp=0.38, minlen=80),
    "guitar": dict(lo=70, hi=2000, mono=False, amp=0.36, minlen=80),
    "other":  dict(lo=55, hi=3000, mono=False, amp=0.38, minlen=90),
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


def merge_fragments(notes, gap):
    """En utdragen ton som Basic Pitch hackat upp i bitar blir en ton igen."""
    out = []
    for n in sorted(notes, key=lambda n: (n[2], n[0])):
        if out and out[-1][2] == n[2] and n[0] - out[-1][1] < gap:
            out[-1][1] = max(out[-1][1], n[1]); out[-1][3] = max(out[-1][3], n[3])
        else:
            out.append(list(n))
    return out


def legato(notes, gap):
    """Fyll små luckor i en melodi så att fraserna hänger ihop."""
    notes = sorted(notes, key=lambda n: n[0])
    for a, b in zip(notes, notes[1:]):
        if 0 < b[0] - a[1] < gap:
            a[1] = b[0]
    return notes


def cap_polyphony(notes, k):
    """Högst k toner samtidigt; de svagaste tonerna (oftast spöktoner) stryks."""
    keep = []
    for n in sorted(notes, key=lambda n: -n[3]):
        if sum(1 for m in keep if m[0] < n[1] and n[0] < m[1]) < k:
            keep.append(n)
    return keep


def melodic(path, cfg):
    _, _, ev = predict(str(path), ICASSP_2022_MODEL_PATH, onset_threshold=0.5, frame_threshold=0.3,
                       minimum_note_length=cfg["minlen"], minimum_frequency=cfg["lo"], maximum_frequency=cfg["hi"])
    notes = [[float(s), float(e), int(p), float(a)] for s, e, p, a, *_ in ev if a >= cfg["amp"]]
    if not cfg["mono"]:
        notes = merge_fragments(notes, 0.03)  # i sång är tätt följande toner egna stavelser
    if cfg["mono"]:
        notes = legato(monophonic(notes), 0.14)
    else:
        notes = cap_polyphony(notes, 4)
    notes.sort(key=lambda n: n[0])
    # [start, längd, midi, styrka 0-1]
    return [[round(s, 3), round(e - s, 3), p, round(min(1.0, a), 2)] for s, e, p, a in notes]


def drums(path):
    """Slag per frekvensband: k=bastrumma, s=virvel, h=stängd hi-hat, o=öppen hi-hat, c=cymbal."""
    y, sr = librosa.load(str(path), sr=22050, mono=True)
    hop = 256
    fps = sr / hop
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=hop))
    f = librosa.fft_frequencies(sr=sr, n_fft=1024)
    bands = {"k": (f >= 30) & (f < 130), "b": (f >= 150) & (f < 350), "s": (f >= 1200) & (f < 5000), "h": (f >= 7000)}
    env = {k: S[m].sum(0) for k, m in bands.items()}
    ref = {k: np.percentile(v, 98) + 1e-9 for k, v in env.items()}

    def peaks(k, delta, wait):
        e = env[k] / ref[k]
        flux = np.maximum(0, np.diff(e, prepend=e[0]))
        flux /= np.percentile(flux, 99.5) + 1e-9
        return librosa.util.peak_pick(flux, pre_max=3, post_max=3, pre_avg=8, post_avg=8, delta=delta, wait=wait)

    def level(k, fr, off=0):
        return float(env[k][fr + off: fr + off + 4].max(initial=0) / ref[k])

    hits = []
    for fr in peaks("k", 0.12, int(0.08 * fps)):
        if level("k", fr) > 0.3:
            hits.append([fr, "k", level("k", fr)])
    # Virvel och hi-hat överlappar i mellanregistret. Dela upp kandidaterna i två grupper
    # efter förhållandet mitt/diskant (1D k-means): gruppen med mest mitt är virveln.
    # Virveln känns igen på sin "kropp" (150-350 Hz), som hi-hatten saknar.
    # Bastrumman läcker också dit, så kroppen måste vara stark i förhållande till bastrumman.
    snares = []
    for fr in peaks("b", 0.12, int(0.08 * fps)):
        rb, rk = level("b", fr), level("k", fr)
        if rb > 0.45 and rb > rk * 0.9:
            hits.append([fr, "s", max(rb, level("s", fr))]); snares.append(fr)
    for fr in peaks("h", 0.08, int(0.05 * fps)):
        if any(abs(fr - s) <= 2 for s in snares):
            continue  # virvelns brus i diskanten
        rh = level("h", fr)
        if rh < 0.2 or level("b", fr) > 0.5:
            continue  # för svagt, eller ett virvel-/bastrummeslag
        tail = level("h", fr, int(0.3 * fps)) / max(rh, 1e-9)
        kind = "c" if rh > 0.8 and tail > 0.55 else "o" if level("h", fr, int(0.12 * fps)) / max(rh, 1e-9) > 0.5 else "h"
        hits.append([fr, kind, rh])
    hits.sort()
    return [[round(fr / fps, 3), k, round(min(1.0, v), 2)] for fr, k, v in hits]


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
