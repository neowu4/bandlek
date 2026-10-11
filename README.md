# Bandlek

Ett Bandle-inspirerat musikspel på svenska. Gissa låten medan bandet spelar ett instrument i taget: trummor, bas, piano, gitarr, synt och sist sång.

Precis som i Bandle är låtarna omgjorda och inte originalinspelningarna. iTunes 30-sekundersklipp delas upp i instrument med [Demucs](https://github.com/facebookresearch/demucs). Varje instrument görs sedan om till noter med Spotifys [Basic Pitch](https://github.com/spotify/basic-pitch), och trummorna görs om till slag. Webbläsaren spelar noterna med egna syntar. Repot innehåller bara noter (`public/notes/`) och inget originalljud. Originalet strömmas från iTunes efter rundan.

## Kom igång

Kräver Python 3.11 och ffmpeg (`brew install python@3.11 ffmpeg`).

```bash
python3.11 -m venv .venv
.venv/bin/pip install demucs soundfile torchaudio
.venv/bin/python build.py          # hämtar och delar upp låtarna i songs.txt
python3 -m http.server 5178 --directory public
```

Spelet går att köra direkt med noterna som finns i repot. Stegen nedan behövs bara för att lägga till låtar.

```bash
python3.11 -m venv .venv-bp
.venv-bp/bin/pip install basic-pitch librosa "setuptools<81"
.venv-bp/bin/python transcribe.py   # stems -> noter (public/notes/*.json)
```

Öppna http://localhost:5178.

## Lägga till låtar

Skriv `Artist - Titel` på en ny rad i `songs.txt` och kör `build.py` och sedan `transcribe.py`. Låtar som redan är klara hoppas över, och `--force` gör om allt.

## Filer

- `build.py` söker på iTunes, laddar ner klippen, kör Demucs och skriver `public/catalog.json` och `public/stems/`
- `transcribe.py` gör om stems till noter och slag
- `public/index.html` innehåller hela spelet: dagens låt, träningsläge, statistik och resultat att dela
