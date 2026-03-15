# Lyrona

Terminal music player with a karaoke typing effect.

## Install

Create and activate a virtual environment, then install the project:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

After that you can run:

```bash
lyrona
lyrona "Washing Machine Heart"
```

Or install directly from GitHub after publishing:

```bash
pip install "git+https://github.com/milord-x/lyrona.git"
```

## Commands

```bash
lyrona
lyrona "Song Name"
lyrona list
lyrona import "/path/to/song.mp3"
lyrona import "/path/to/song.mp3" --title "Memory Reboot" --artist "VØJ"
lyrona import "/path/to/song.mp3" --lyrics "/path/to/song.lrc"
lyrona add-lyrics "Memory Reboot" "/path/to/song.lrc"
lyrona retime "Memory Reboot"
lyrona rebuild-cache
```

## Quick Workflow

### Add a track fast

Use a local audio file that you already have the right to use:

```bash
lyrona import "/path/to/song.mp3"
```

If the audio file has bad or missing tags, set title and artist explicitly:

```bash
lyrona import "/path/to/song.mp3" --title "Memory Reboot" --artist "VØJ"
```

### Add lyrics fast

If you already have a timed `.lrc` file:

```bash
lyrona add-lyrics "Memory Reboot" "/path/to/song.lrc"
```

Or do it in one step while importing:

```bash
lyrona import "/path/to/song.mp3" --lyrics "/path/to/song.lrc"
```

Lyrona will generate `words.json` automatically. If you later edit the `.lrc`, rebuild timings with:

```bash
lyrona retime "Memory Reboot"
```

## Song Folder Layout

Each song lives in its own folder inside `songs/`:

```text
songs/
  Memory Reboot/
    audio.mp3
    lyrics.lrc
    words.json
    metadata.json
```

`lyrics.lrc` and `words.json` are optional. `metadata.json` is used only when you want to override missing or bad title/artist tags.

## GitHub Notes

- This repository is set up to ignore local song files by default.
- Keep the code in Git, and keep your personal music library local.
- If you want demo content in GitHub, add only music and lyrics that you are allowed to redistribute.
