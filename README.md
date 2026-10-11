# Bandlek

Ett Bandle-inspirerat musikspel på svenska. Gissa låten medan bandet spelar ett instrument i taget: trummor, bas, piano, gitarr, synt och sist sång.

Ljudet är iTunes 30-sekundersklipp som delas upp i instrument lokalt med [Demucs](https://github.com/facebookresearch/demucs) (`htdemucs_6s`). Ljudfilerna ingår inte i repot och skapas med `build.py`.

## Kom igång

Kräver Python 3.11 och ffmpeg (`brew install python@3.11 ffmpeg`).

```bash
python3.11 -m venv .venv
.venv/bin/pip install demucs soundfile torchaudio
.venv/bin/python build.py          # hämtar och delar upp låtarna i songs.txt
python3 -m http.server 5178 --directory public
```

Öppna http://localhost:5178.

## Lägga till låtar

Skriv `Artist - Titel` på en ny rad i `songs.txt` och kör `build.py` igen. Låtar som redan är klara hoppas över, och `--force` gör om allt.

## Filer

- `build.py` söker på iTunes, laddar ner klippen, kör Demucs och skriver `public/catalog.json` och `public/stems/`
- `public/index.html` innehåller hela spelet: dagens låt, träningsläge, statistik och resultat att dela
