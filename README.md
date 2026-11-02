# FLAC Library

A local Flask app for scanning a personal FLAC collection, browsing its metadata, and playing files from the machine that holds them.

## What is included

- Flask interface, static assets, and SQL Studio page
- A scanner that reads FLAC tags and creates a local SQLite catalogue
- A sanitized text-only catalog export in [catalog.csv](catalog.csv), with title, artist, album, and release year
- Setup instructions and dependency list

The music files, SQLite database, and generated reports are not included. The CSV export contains 1,451 track records and excludes file paths, play counts, ratings, and audio files. The local SQLite catalogue stores paths to local audio files, so cloning this repository does not give another person access to those tracks.

## Run locally

Python 3.10 or newer is recommended.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:FLAC_MUSIC_DIR = "$HOME\Music"
python scan_library.py
python app.py
```

Then open http://127.0.0.1:5000. On macOS or Linux, activate the environment with `source .venv/bin/activate` and set `FLAC_MUSIC_DIR` to the directory containing your music.

The scanner uses `~/Music` if `FLAC_MUSIC_DIR` is not set. It creates `flac_library.db` in this project folder; Git ignores that database and local audio files.

## Safety and sharing

This is a local development app. Its SQL Studio endpoint accepts arbitrary SQL, and its audio route serves files from the local catalogue. Do not expose the Flask development server to the internet or an untrusted network. Remote sharing needs authentication, a secure hosting setup, and audio files that you have the right to redistribute. GitHub contains the application code only; it does not host the music library.
