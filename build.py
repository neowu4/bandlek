"""Hämtar iTunes-förhandslyssningar för låtarna i songs.txt, delar upp dem i
instrument med Demucs (htdemucs_6s) och skriver public/catalog.json.

Kör: .venv/bin/python build.py            (bara nya låtar)
     .venv/bin/python build.py --force    (gör om allt)
"""
import json, re, subprocess, sys, time, unicodedata, urllib.parse, urllib.request
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).parent
CACHE = ROOT / "cache"
OUT = ROOT / "public"
STEMS_DIR = OUT / "stems"
MODEL = "htdemucs_6s"
# Spelordning: första steget är trummor, sista är sång.
ORDER = ["drums", "bass", "piano", "guitar", "other", "vocals"]
SILENT_RMS = 0.01  # stems tystare än så hoppas över


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def norm(s):
    return re.sub(r"[^a-z0-9]", "", unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower())


def itunes(artist, title):
    q = urllib.parse.urlencode({"term": f"{artist} {title}", "entity": "song", "limit": 50, "country": "se"})
    for attempt in range(5):  # iTunes stryper vid många anrop i rad
        try:
            with urllib.request.urlopen(f"https://itunes.apple.com/search?{q}", timeout=20) as r:
                res = json.load(r)["results"]
            break
        except Exception as e:
            print(f"   iTunes svarade inte ({e}), försöker igen…"); time.sleep(10 * (attempt + 1))
    else:
        return None
    res = [x for x in res if x.get("previewUrl")]
    bad = re.compile(r"remix|remake|re-recorded|\b2k\d|taylor's version|instrumental|\blive\b|karaoke|acoustic|\bcover\b|long-lost|mix\)|\bdemo\b|remaster.*\d{4}.*version", re.I)

    def score(x):
        s = 0
        if norm(artist) in norm(x["artistName"]): s += 4
        if norm(title) == norm(clean_title(x["trackName"])): s += 4
        elif norm(title) in norm(x["trackName"]): s += 2
        if bad.search(x["trackName"]) or bad.search(x.get("collectionName", "")): s -= 5
        return s
    return max(res, key=score) if res else None


def clean_title(t):
    """'Get Lucky (feat. X) [Radio Edit]' -> 'Get Lucky'"""
    return re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", "", t).strip() or t


def separate(src, workdir):
    for dev in ("mps", "cpu"):
        r = subprocess.run([sys.executable, "-m", "demucs", "-n", MODEL, "-d", dev, "-o", str(workdir), str(src)],
                           capture_output=True, text=True)
        if r.returncode == 0:
            return workdir / MODEL / src.stem
        print(f"   demucs på {dev} misslyckades: {r.stderr.strip().splitlines()[-1:]}")
    raise RuntimeError("demucs misslyckades")


def main():
    force = "--force" in sys.argv
    lines = [l.strip() for l in (ROOT / (sys.argv[1] if len(sys.argv)>1 and not sys.argv[1].startswith("--") else "songs.txt")).read_text().splitlines() if l.strip() and not l.startswith("#")]
    catalog_path = OUT / "catalog.json"
    old = {s["id"]: s for s in json.loads(catalog_path.read_text())} if catalog_path.exists() else {}
    catalog = []
    CACHE.mkdir(exist_ok=True); STEMS_DIR.mkdir(parents=True, exist_ok=True)

    for line in lines:
        line, _, tagstr = line.partition(" | ")
        tags = [t.strip() for t in tagstr.split(",") if t.strip()]
        artist, _, title = line.partition(" - ")
        sid = slug(f"{artist}-{title}")
        if sid in old and not force and (STEMS_DIR / sid).exists():
            old[sid]["tags"] = tags
            catalog.append(old[sid]); print(f"✓ {line} (klar sedan tidigare)"); continue
        print(f"→ {line}")
        hit = itunes(artist, title)
        if not hit:
            print("   hittades inte på iTunes, hoppar över"); continue
        src = CACHE / f"{sid}.m4a"
        if not src.exists():
            urllib.request.urlretrieve(hit["previewUrl"], src)
        stem_dir = separate(src, CACHE / "sep")
        dest = STEMS_DIR / sid; dest.mkdir(exist_ok=True)
        stems = []
        for name in ORDER:
            wav = stem_dir / f"{name}.wav"
            audio, sr = sf.read(wav)
            rms = float(np.sqrt(np.mean(audio ** 2)))
            if rms < SILENT_RMS:
                print(f"   {name}: tyst ({rms:.4f}), hoppar över"); continue
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "libmp3lame", "-b:a", "128k",
                            str(dest / f"{name}.mp3")], check=True)
            stems.append(name)
        catalog.append({
            "id": sid, "t": clean_title(hit["trackName"]), "a": hit["artistName"],
            "y": int(hit.get("releaseDate", "0000")[:4]), "al": hit.get("collectionName", ""),
            "c": hit.get("artworkUrl100", "").replace("100x100bb", "600x600bb"),
            "stems": stems, "tags": tags,
        })
        print(f"   stems: {', '.join(stems)}")
        catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=1))

    catalog_path.write_text(json.dumps(catalog, ensure_ascii=False, indent=1))
    print(f"\nKlart: {len(catalog)} låtar i {catalog_path}")


if __name__ == "__main__":
    main()
