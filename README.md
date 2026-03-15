# Lyrona

Terminal music player with a karaoke typing effect.

## Install

If you only cloned the repository, the `lyrona` command does not exist yet.
You need to install Lyrona as a CLI application.

### Install as an app from GitHub

Recommended with `uv`:

```bash
uv tool install --from git+https://github.com/milord-x/lyrona.git lyrona
```

Recommended with `pipx`:

```bash
pipx install git+https://github.com/milord-x/lyrona.git
```

Fallback with plain `pip`:

```bash
python3 -m pip install --user "git+https://github.com/milord-x/lyrona.git"
```

All of these install the `lyrona` launcher into your user environment, so it is available from any folder.
Usually that means `~/.local/bin/lyrona`.

If `lyrona` is still not found, add `~/.local/bin` to your `PATH`.

### Install from a local clone

After cloning the repository, install it as an app with:

```bash
cd lyrona
./install.sh
```

Or manually:

```bash
uv tool install --from . lyrona
```

### Development install

If you want to work on the project itself, use a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run the command inside the activated environment:

```bash
lyrona
lyrona "Washing Machine Heart"
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
~/.local/share/lyrona/
  songs/
    Memory Reboot/
      audio.mp3
      lyrics.lrc
      words.json
      metadata.json
```

`lyrics.lrc` and `words.json` are optional. `metadata.json` is used only when you want to override missing or bad title/artist tags.

## Data Directory

By default Lyrona stores songs and cache files in:

```bash
~/.local/share/lyrona
```

If `XDG_DATA_HOME` is set, Lyrona uses:

```bash
$XDG_DATA_HOME/lyrona
```

You can fully override the location with:

```bash
export LYRONA_HOME="$HOME/Music/lyrona"
```

## GitHub Notes

- Keep the code in Git, and keep your personal music library in your user data directory.
- If you want demo content in GitHub, add only music and lyrics that you are allowed to redistribute.
