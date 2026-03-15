# <div align="center">Lyrona</div>

<div align="center">Terminal music player with a karaoke typing effect.</div>

<div align="center">
  A real CLI app, installable from GitHub, with a standalone Linux release build.
</div>

<br />

## Overview

Lyrona is for a simple flow:

1. Install the app.
2. Import local music files.
3. Add optional `.lrc` lyrics.
4. Play everything from the terminal.

Lyrona stores your library in your user data directory, not inside the repository.

## Why Lyrona

- Installable as a normal CLI command: `lyrona`
- Linux standalone release archive for machines without a Python setup
- Song library stored in `~/.local/share/lyrona`
- Supports local audio import with optional timed lyrics
- Rebuildable word timing cache for karaoke playback

## Fastest Start

If you want the app without managing Python environments, download the Linux release archive from GitHub Releases.

```bash
tar -xzf lyrona-linux-x86_64.tar.gz
cd lyrona-linux-x86_64
./lyrona --help
```

This build bundles Python, project dependencies, `libvlc`, and VLC plugins.
It still needs a working Linux audio stack on the target machine.

## Install From GitHub

### Option 1: Install as a CLI app

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

After that, the command should be available globally:

```bash
lyrona --help
```

If the command is not found, add `~/.local/bin` to your `PATH`.

### Option 2: Clone the repository first

```bash
git clone https://github.com/milord-x/lyrona.git
cd lyrona
./install.sh
```

### For source-based installs

If you install from source with `uv`, `pipx`, or `pip`, the system should have VLC available.

Arch Linux:

```bash
sudo pacman -S vlc
```

Ubuntu or Debian:

```bash
sudo apt install vlc
```

## First Run

```bash
lyrona list
```

If your library is empty, import a track:

```bash
lyrona import "/path/to/song.mp3"
```

Or import with lyrics in one step:

```bash
lyrona import "/path/to/song.mp3" --lyrics "/path/to/song.lrc"
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

## Add Music

Lyrona imports local files.
It does not stream directly from a GitHub URL.

### Import music already on your machine

```bash
lyrona import "/music/Memory Reboot.mp3"
```

### Import music that lives in another GitHub repository

1. Download or clone the repository that contains the audio files.
2. Point `lyrona import` at the downloaded local file paths.

Example:

```bash
git clone https://github.com/your-name/your-music-repo.git
lyrona import "./your-music-repo/Memory Reboot/audio.mp3" --lyrics "./your-music-repo/Memory Reboot/lyrics.lrc"
```

If you downloaded files manually from GitHub in the browser, use the paths of those downloaded files:

```bash
lyrona import "$HOME/Downloads/song.mp3" --lyrics "$HOME/Downloads/song.lrc"
```

Only import music and lyrics that you are legally allowed to use.

## Lyrics Workflow

If the audio is already imported:

```bash
lyrona add-lyrics "Memory Reboot" "/path/to/song.lrc"
```

If you edited the `.lrc` file and want to rebuild timings:

```bash
lyrona retime "Memory Reboot"
```

If you want to refresh the metadata cache:

```bash
lyrona rebuild-cache
```

## Library Layout

By default Lyrona stores data here:

```text
~/.local/share/lyrona/
  .lyrona_metadata_cache.json
  songs/
    Memory Reboot/
      audio.mp3
      lyrics.lrc
      words.json
      metadata.json
```

You can override the location:

```bash
export LYRONA_HOME="$HOME/Music/lyrona"
```

If `XDG_DATA_HOME` is set, Lyrona uses:

```bash
$XDG_DATA_HOME/lyrona
```

## Standalone Release Build

To build the Linux standalone archive locally:

```bash
python -m pip install ".[build]"
python scripts/build_standalone.py
```

Output:

```bash
dist/lyrona-linux-x86_64.tar.gz
```

## GitHub Release Flow

This repository includes a GitHub Actions workflow that can build a standalone Linux archive.

- `workflow_dispatch` builds the archive manually from the Actions tab
- pushing a tag matching `v*` builds and publishes the release asset

Example:

```bash
git tag v0.1.1
git push origin v0.1.1
```

## Development

If you want to work on the project itself:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Status

Current state:

- installable as `lyrona` from GitHub
- standalone Linux release build is configured
- user library is outside the repository
- release workflow is ready for GitHub Actions

Windows and macOS release packaging are not set up yet.
