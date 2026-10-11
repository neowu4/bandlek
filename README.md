# Bandlek

Ett Bandle-inspirerat musikspel på svenska. Gissa låten medan bandet spelar ett instrument i taget: trummor, bas, piano, gitarr, synt och sist sång.

Precis som i Bandle är låtarna omgjorda och inte originalinspelningarna. iTunes 30-sekundersklipp delas upp i instrument med [Demucs](https://github.com/facebookresearch/demucs). Varje instrument görs sedan om till noter med Spotifys [Basic Pitch](https://github.com/spotify/basic-pitch), och trummorna görs om till slag. Webbläsaren spelar noterna med egna syntar. Repot innehåller bara noter (`public/notes/`) och inget originalljud. Originalet strömmas från iTunes efter rundan.

## Kom igång

Noterna finns redan i repot, så det räcker att starta en server:

```bash
python3 -m http.server 5178 --directory public
```

Öppna http://localhost:5178.

## Verktyg för att bygga låtar

Kräver Python 3.11 och ffmpeg (`brew install python@3.11 ffmpeg`).

```bash
python3.11 -m venv .venv
.venv/bin/pip install demucs soundfile torchaudio
python3.11 -m venv .venv-bp
.venv-bp/bin/pip install basic-pitch librosa "setuptools<81"
```

## Lägga till låtar

Skriv `Artist - Titel` på en ny rad i `songs.txt` och kör `.venv/bin/python build.py` och sedan `.venv-bp/bin/python transcribe.py`. Låtar som redan är klara hoppas över, och `--force` gör om allt.

## Filer

- `build.py` söker på iTunes, laddar ner klippen, kör Demucs och skriver `public/catalog.json` och `public/stems/`
- `transcribe.py` gör om stems till noter och slag
- `public/index.html` innehåller hela spelet: dagens låt, träningsläge, statistik och resultat att dela
