"""Lägger till Spotify-streams i public/catalog.json.

- Artistens Spotify-ID: MusicBrainz (öppet API, max 1 anrop/s)
- Streams: kworb.net, som publicerar Spotifys stream-siffror per låt

Kör: python3 stats.py            (bara låtar som saknar streams)
     python3 stats.py --force
"""
import html, json, re, sys, time, unicodedata, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).parent
UA = "Bandlek/1.0 (https://github.com/neowu4/bandlek)"
SKIP = re.compile(r"remix|live|instrumental|acoustic|karaoke|demo|cover|sped up|slowed", re.I)


def get(url, as_json=True):
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=25) as r:
                body = r.read().decode("utf-8")
            time.sleep(1.1)  # MusicBrainz tillåter 1 anrop per sekund
            return json.loads(body) if as_json else body
        except Exception as e:
            print(f"   försöker igen ({e})"); time.sleep(5 * (attempt + 1))
    return None


def norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", s)


def spotify_artist_ids(artist):
    q = urllib.parse.urlencode({"query": f'artist:"{artist}"', "limit": 5, "fmt": "json"})
    res = get(f"https://musicbrainz.org/ws/2/artist?{q}") or {}
    for a in res.get("artists", []):
        if norm(a["name"]) != norm(artist):
            continue
        info = get(f"https://musicbrainz.org/ws/2/artist/{a['id']}?inc=url-rels&fmt=json") or {}
        ids = [m.group(1) for rel in info.get("relations", [])
               if (m := re.search(r"open\.spotify\.com/artist/([A-Za-z0-9]+)", rel.get("url", {}).get("resource", "")))]
        if ids:
            return ids
    return []


def streams(artist_ids, title):
    """Mest streamade versionen vars titel är låtens titel (Radio Edit o.d. räknas, remixer inte)."""
    best = None
    for aid in artist_ids:
        page = get(f"https://kworb.net/spotify/artist/{aid}_songs.html", as_json=False) or ""
        for tid, name, total in re.findall(r'open\.spotify\.com/track/([A-Za-z0-9]+)"[^>]*>([^<]+)</a></div></td><td>([\d,]+)</td>', page):
            name = html.unescape(name)
            base, _, extra = re.split(r" - | \(", name, maxsplit=1)[0], None, name[len(re.split(r' - | \(', name)[0]):]
            if norm(base) == norm(title) and not SKIP.search(extra):
                n = int(total.replace(",", ""))
                if not best or n > best[0]:
                    best = (n, tid)
    return best


def main():
    force = "--force" in sys.argv
    path = ROOT / "public" / "catalog.json"
    cat = json.loads(path.read_text())
    for s in cat:
        if s.get("streams") and not force:
            continue
        ids = spotify_artist_ids(s["a"])
        st = streams(ids, s["t"]) if ids else None
        if st:
            s["streams"], s["sp"] = st
        print(f"{s['t']} – {s['a']}: {f'{st[0]:,}' if st else 'hittades inte'}")
        path.write_text(json.dumps(cat, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
