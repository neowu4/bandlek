"""Låser vilken låt som är dagens låt för varje dag (public/daily.json).

Dagar som redan varit (och i dag) ändras aldrig. Nya dagar fylls på med slumpade låtar
utan upprepning inom REPEAT_GAP dagar. Kör efter att nya låtar lagts till:
    python3 schedule.py
"""
import json, random, subprocess
from datetime import date
from pathlib import Path

ROOT = Path(__file__).parent
EPOCH = date(2026, 10, 1)          # dag 1 (samma som i spelet)
AHEAD = 400                        # så många dagar framåt som schemaläggs
REPEAT_GAP = 60


def playable(cat):
    return [s for s in cat if s.get("tracks") and all(t in s["tracks"] for t in ("drums", "bass", "vocals"))]


def legacy_ids(ids, days):
    """Låtarna som spelets gamla ordning gav dag 1..days (för att inte ändra redan visade dagar)."""
    js = f"""
    const n={len(ids)}; let s=20261011; const r=()=>((s=(s*1103515245+12345)%2147483648)/2147483648);
    const a=[...Array(n).keys()]; for(let i=n-1;i>0;i--){{ const j=Math.floor(r()*(i+1)); [a[i],a[j]]=[a[j],a[i]]; }}
    console.log(JSON.stringify(Array.from({{length:{days}}},(_,d)=>a[d%n])));"""
    order = json.loads(subprocess.run(["node", "-e", js], capture_output=True, text=True, check=True).stdout)
    return [ids[i] for i in order]


def main():
    cat = json.loads((ROOT / "public" / "catalog.json").read_text())
    ids = [s["id"] for s in playable(cat)]
    path = ROOT / "public" / "daily.json"
    today = (date.today() - EPOCH).days + 1
    if path.exists():
        sched = json.loads(path.read_text())["ids"]
    else:
        sched = legacy_ids(ids, today)
    # Dagar till och med i dag ändras aldrig; framtiden slumpas om så att nya låtar kommer med
    sched = sched[:today]
    rnd = random.Random(f"{today}-{len(ids)}")
    while len(sched) < today + AHEAD:
        recent = set(sched[-REPEAT_GAP:])
        sched.append(rnd.choice([x for x in ids if x not in recent] or ids))
    path.write_text(json.dumps({"start": EPOCH.isoformat(), "ids": sched}, separators=(",", ":")))
    print(f"Schema: {len(sched)} dagar, i dag (dag {today}) = {sched[today - 1]}")


if __name__ == "__main__":
    main()
