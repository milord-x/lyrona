from __future__ import annotations
import argparse
from contextlib import nullcontext
import json
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from mutagen import File as MutagenFile
except ImportError:
    MutagenFile = None

from display import TerminalKaraokeDisplay, TerminalSongSelector, _RawTerminal
from paths import DATA_DIR, METADATA_CACHE_PATH, SONGS_DIR, ensure_data_dirs
from timing import build_payload, build_word_timings, group_words_by_line, parse_lrc_lines

SONG_METADATA_FILENAME = "metadata.json"
CACHE_VERSION = 1

TIMED_LINE_PATTERN = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")
META_PATTERN = re.compile(r"^\[([a-zA-Z]+):(.*)\]$")
INVALID_FOLDER_CHARS = re.compile(r'[<>:"/\\|?*\x00-\x1f]+')

AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac"}
LYRICS_EXTENSIONS = {".lrc"}


@dataclass(slots=True)
class LyricLine:
    time_sec: float
    text: str


@dataclass(slots=True)
class Song:
    title: str
    artist: str
    folder_name: str
    folder_path: Path
    audio_path: Path
    lyrics_path: Optional[Path]


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")


def normalize_query(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def find_audio_files(folder: Path) -> List[Path]:
    files: List[Path] = []

    for file_path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if file_path.is_file() and file_path.suffix.lower() in AUDIO_EXTENSIONS:
            files.append(file_path)

    return files


def find_lyrics_files(folder: Path) -> List[Path]:
    files: List[Path] = []

    for file_path in sorted(folder.iterdir(), key=lambda p: p.name.lower()):
        if file_path.is_file() and file_path.suffix.lower() in LYRICS_EXTENSIONS:
            files.append(file_path)

    return files


def first_non_empty(*values: str) -> str:
    for value in values:
        if value.strip():
            return value.strip()
    return ""


def sanitize_folder_name(value: str) -> str:
    normalized = INVALID_FOLDER_CHARS.sub(" ", value).strip()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized or "Untitled Song"


def file_signature(path: Optional[Path]) -> Optional[Dict[str, Any]]:
    if path is None or not path.exists():
        return None

    try:
        stat = path.stat()
    except OSError:
        return None

    return {
        "name": path.name,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def load_metadata_cache() -> Dict[str, Any]:
    if not METADATA_CACHE_PATH.exists():
        return {}

    try:
        with METADATA_CACHE_PATH.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict) or payload.get("version") != CACHE_VERSION:
        return {}

    songs = payload.get("songs", {})
    if not isinstance(songs, dict):
        return {}

    return songs


def save_metadata_cache(entries: Dict[str, Any]) -> None:
    payload = {
        "version": CACHE_VERSION,
        "songs": entries,
    }

    try:
        ensure_data_dirs()
        temp_path = METADATA_CACHE_PATH.with_suffix(".tmp")
        with temp_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        temp_path.replace(METADATA_CACHE_PATH)
    except OSError:
        return


def invalidate_metadata_cache() -> None:
    try:
        METADATA_CACHE_PATH.unlink()
    except FileNotFoundError:
        return
    except OSError:
        return


def read_song_metadata_file(path: Path) -> Dict[str, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}

    if not isinstance(payload, dict):
        return {}

    title = str(payload.get("title", "")).strip()
    artist = str(payload.get("artist", "")).strip()
    metadata: Dict[str, str] = {}

    if title:
        metadata["title"] = title
    if artist:
        metadata["artist"] = artist

    return metadata


def write_song_metadata_file(
    song_folder: Path,
    title: Optional[str] = None,
    artist: Optional[str] = None,
) -> None:
    metadata_path = song_folder / SONG_METADATA_FILENAME
    payload = read_song_metadata_file(metadata_path) if metadata_path.exists() else {}

    if title is not None:
        payload["title"] = title.strip()
    if artist is not None:
        payload["artist"] = artist.strip()

    payload = {
        key: value
        for key, value in payload.items()
        if isinstance(value, str) and value.strip()
    }

    if not payload:
        try:
            metadata_path.unlink()
        except FileNotFoundError:
            pass
        except OSError:
            pass
        return

    with metadata_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)


def read_lrc_metadata(path: Path) -> Dict[str, str]:
    metadata: Dict[str, str] = {}

    try:
        with path.open("r", encoding="utf-8") as handle:
            for raw in handle:
                stripped = raw.rstrip("\n").rstrip("\r").strip()
                if not stripped:
                    continue

                meta_match = META_PATTERN.match(stripped)
                if not meta_match:
                    continue

                key = meta_match.group(1).strip().lower()
                value = meta_match.group(2).strip()
                if value:
                    metadata[key] = value
    except (OSError, UnicodeDecodeError):
        return {}

    return metadata


def read_audio_metadata_with_mutagen(audio_path: Path) -> Dict[str, str]:
    if MutagenFile is None:
        return {}

    try:
        audio_file = MutagenFile(str(audio_path), easy=True)
    except Exception:
        return {}

    if audio_file is None:
        return {}

    metadata: Dict[str, str] = {}

    for key in ("title", "artist", "albumartist", "composer"):
        raw_value = audio_file.get(key)
        if not raw_value:
            continue

        if isinstance(raw_value, list):
            value = first_non_empty(*(str(item) for item in raw_value))
        else:
            value = str(raw_value).strip()

        if value:
            metadata[key] = value

    return metadata


def read_audio_metadata_with_ffprobe(audio_path: Path) -> Dict[str, str]:
    command = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format_tags=title,artist,album_artist,albumartist,composer,TPE1,TIT2",
        "-of",
        "json",
        str(audio_path),
    ]

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=2.0,
        )
    except (FileNotFoundError, OSError, subprocess.SubprocessError):
        return {}

    if result.returncode != 0:
        return {}

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return {}

    tags = payload.get("format", {}).get("tags", {})
    if not isinstance(tags, dict):
        return {}

    metadata: Dict[str, str] = {}

    for key, value in tags.items():
        normalized_key = str(key).strip().lower()
        text_value = str(value).strip()
        if text_value:
            metadata[normalized_key] = text_value

    return metadata


def read_audio_metadata(audio_path: Path) -> Dict[str, str]:
    metadata = read_audio_metadata_with_mutagen(audio_path)
    if metadata:
        return metadata
    return read_audio_metadata_with_ffprobe(audio_path)


def resolve_song_identity(
    folder_name: str,
    audio_path: Path,
    lyrics_path: Optional[Path],
    song_metadata_path: Optional[Path] = None,
) -> Tuple[str, str]:
    audio_metadata = read_audio_metadata(audio_path)
    lyrics_metadata = read_lrc_metadata(lyrics_path) if lyrics_path else {}
    manual_metadata = read_song_metadata_file(song_metadata_path) if song_metadata_path else {}

    title = first_non_empty(
        manual_metadata.get("title", ""),
        audio_metadata.get("title", ""),
        audio_metadata.get("tit2", ""),
        lyrics_metadata.get("ti", ""),
        folder_name,
    )
    artist = first_non_empty(
        manual_metadata.get("artist", ""),
        audio_metadata.get("artist", ""),
        audio_metadata.get("album_artist", ""),
        audio_metadata.get("albumartist", ""),
        audio_metadata.get("tpe1", ""),
        audio_metadata.get("composer", ""),
        lyrics_metadata.get("ar", ""),
        "Unknown Artist",
    )

    return title, artist


def discover_songs(songs_dir: Path) -> List[Song]:
    songs: List[Song] = []
    cache_entries = load_metadata_cache() if songs_dir == SONGS_DIR else {}
    cache_changed = False
    seen_entries = set()

    if not songs_dir.exists():
        return songs

    for item in sorted(songs_dir.iterdir(), key=lambda p: p.name.lower()):
        if not item.is_dir():
            continue

        audio_files = find_audio_files(item)
        lyrics_files = find_lyrics_files(item)

        if len(audio_files) != 1:
            continue

        if len(lyrics_files) > 1:
            continue

        lyrics_path = lyrics_files[0] if lyrics_files else None
        song_metadata_path = item / SONG_METADATA_FILENAME
        signature = {
            "audio": file_signature(audio_files[0]),
            "lyrics": file_signature(lyrics_path),
            "metadata": file_signature(song_metadata_path),
        }
        cached_entry = cache_entries.get(item.name, {})

        if (
            isinstance(cached_entry, dict)
            and cached_entry.get("signature") == signature
            and isinstance(cached_entry.get("title"), str)
            and isinstance(cached_entry.get("artist"), str)
            and cached_entry["title"].strip()
            and cached_entry["artist"].strip()
        ):
            title = cached_entry["title"].strip()
            artist = cached_entry["artist"].strip()
        else:
            title, artist = resolve_song_identity(
                folder_name=item.name,
                audio_path=audio_files[0],
                lyrics_path=lyrics_path,
                song_metadata_path=song_metadata_path,
            )
            if songs_dir == SONGS_DIR:
                cache_entries[item.name] = {
                    "signature": signature,
                    "title": title,
                    "artist": artist,
                }
                cache_changed = True

        seen_entries.add(item.name)

        songs.append(
            Song(
                title=title,
                artist=artist,
                folder_name=item.name,
                folder_path=item,
                audio_path=audio_files[0],
                lyrics_path=lyrics_path,
            )
        )

    if songs_dir == SONGS_DIR:
        stale_keys = [key for key in cache_entries if key not in seen_entries]
        if stale_keys:
            for key in stale_keys:
                cache_entries.pop(key, None)
            cache_changed = True

        if cache_changed:
            save_metadata_cache(cache_entries)

    return songs


def parse_lrc(path: Path) -> Tuple[Dict[str, str], List[LyricLine]]:
    metadata: Dict[str, str] = {}
    lines: List[LyricLine] = []

    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.rstrip("\n").rstrip("\r").strip()
            if not stripped:
                continue

            timed_match = TIMED_LINE_PATTERN.match(stripped)
            if timed_match:
                minutes = int(timed_match.group(1))
                seconds = float(timed_match.group(2))
                text = timed_match.group(3).strip()
                total_sec = minutes * 60 + seconds
                lines.append(LyricLine(time_sec=total_sec, text=text))
                continue

            meta_match = META_PATTERN.match(stripped)
            if meta_match:
                key = meta_match.group(1).strip().lower()
                value = meta_match.group(2).strip()
                metadata[key] = value

    lines.sort(key=lambda line: line.time_sec)
    return metadata, lines


def resolve_song_from_query(songs: List[Song], query: str) -> Optional[Song]:
    query_normalized = normalize_query(query)
    query_slug = slugify(query)

    exact_title: Dict[str, Song] = {normalize_query(song.title): song for song in songs}
    exact_folder: Dict[str, Song] = {normalize_query(song.folder_name): song for song in songs}
    slug_map: Dict[str, Song] = {slugify(song.title): song for song in songs}

    if query_normalized in exact_title:
        return exact_title[query_normalized]

    if query_normalized in exact_folder:
        return exact_folder[query_normalized]

    if query_slug in slug_map:
        return slug_map[query_slug]

    partial_matches = [
        song
        for song in songs
        if query_normalized in normalize_query(song.title)
        or query_normalized in normalize_query(song.folder_name)
        or query_slug in slugify(song.title)
        or query_slug in slugify(song.folder_name)
    ]

    if len(partial_matches) == 1:
        return partial_matches[0]

    return None


def find_current_line_index(lyrics: List[LyricLine], current_time: float) -> int:
    current_index = -1

    for index, line in enumerate(lyrics):
        if line.time_sec <= current_time:
            current_index = index
        else:
            break

    return current_index


def compute_typed_text(
    lyrics: List[LyricLine],
    current_index: int,
    current_time: float,
) -> str:
    if current_index < 0 or current_index >= len(lyrics):
        return ""

    current_line = lyrics[current_index]
    text = current_line.text

    if not text:
        return ""

    start_time = current_line.time_sec

    if current_index + 1 < len(lyrics):
        end_time = lyrics[current_index + 1].time_sec
    else:
        end_time = start_time + max(2.5, len(text) * 0.09)

    total_window = max(0.05, end_time - start_time)
    typing_duration = max(0.10, total_window * 0.72)
    elapsed = max(0.0, current_time - start_time)

    if elapsed >= typing_duration:
        visible_chars = len(text)
    else:
        progress = elapsed / typing_duration
        eased = progress ** 0.82
        visible_chars = int(eased * len(text))

    visible_chars = max(0, min(len(text), visible_chars))
    typed = text[:visible_chars]

    if visible_chars < len(text):
        blink_on = int(current_time * 3.0) % 2 == 0
        if blink_on:
            typed += "▌"

    return typed


def build_song_info(song: Song, metadata: Dict[str, str]) -> Tuple[str, str]:
    title = song.title
    artist = metadata.get("ar", "").strip() or song.artist
    return title, artist


def generate_words_file(song_folder: Path) -> Tuple[bool, str]:
    lrc_path = song_folder / "lyrics.lrc"
    output_path = song_folder / "words.json"

    if not lrc_path.exists():
        return False, f"lyrics.lrc not found in {song_folder}"

    lines = parse_lrc_lines(lrc_path)
    if not lines:
        return False, f"no timed lyric lines found in {lrc_path}"

    words = build_word_timings(lines)
    if not words:
        return False, "no word timings generated"

    grouped_words = group_words_by_line(words)
    payload = build_payload(song_folder.name, lrc_path, lines, grouped_words)

    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=2)

    return True, str(output_path)


def choose_song_interactively(songs: List[Song]) -> Optional[Song]:
    selector = TerminalSongSelector(app_title="Lyrona")
    return selector.select([song.title for song in songs], songs)


def load_vlc_module() -> Any:
    try:
        import vlc
    except ImportError:
        return None

    return vlc


def create_vlc_player(vlc_module: Any, audio_path: Path) -> Any:
    instance = vlc_module.Instance()
    player = instance.media_player_new()
    media = instance.media_new(str(audio_path))
    player.set_media(media)
    return player


def play_song(song: Song) -> int:
    vlc_module = load_vlc_module()
    if vlc_module is None:
        print("python-vlc is not installed. Run `pip install -r requirements.txt` first.")
        return 1

    metadata: Dict[str, str] = {}
    lyrics: List[LyricLine] = []

    if song.lyrics_path is not None:
        metadata, lyrics = parse_lrc(song.lyrics_path)

    timed_lines = load_timed_lines(song.folder_path)
    if song.lyrics_path is not None and not lyrics:
        print(f"No valid lyric lines found: {song.lyrics_path}")
        return 1

    title, artist = build_song_info(song, metadata)
    player = create_vlc_player(vlc_module, song.audio_path)
    display = TerminalKaraokeDisplay()
    input_context = _RawTerminal() if sys.stdin.isatty() else nullcontext(None)

    try:
        with input_context as terminal:
            display.open()
            player.play()
            time.sleep(0.30)

            while True:
                if terminal is not None and terminal.read_key(timeout=0.0) == "quit":
                    player.stop()
                    break

                state = player.get_state()
                if state in (
                    vlc_module.State.Ended,
                    vlc_module.State.Stopped,
                    vlc_module.State.Error,
                ):
                    break

                current_time_ms = player.get_time()
                if current_time_ms < 0:
                    time.sleep(0.016)
                    continue

                current_time_sec = current_time_ms / 1000.0
                current_index = find_current_line_index(lyrics, current_time_sec)
                if timed_lines:
                    typed_text = compute_word_line(timed_lines, current_time_sec)
                elif lyrics:
                    typed_text = compute_typed_text(lyrics, current_index, current_time_sec)
                else:
                    typed_text = ""

                duration_ms = player.get_length()
                duration_sec = duration_ms / 1000.0 if duration_ms and duration_ms > 0 else 0.0

                display.render(
                    song_title=title,
                    artist_name=artist,
                    current_time=current_time_sec,
                    duration=duration_sec,
                    lyric_text=typed_text,
                )

                time.sleep(0.016)

    except KeyboardInterrupt:
        pass
    finally:
        player.stop()
        display.close()

    return 0


def print_available_songs(songs: List[Song]) -> None:
    print("Available songs:")
    for song in songs:
        print(f"  - {song.title} | {song.artist}")


def print_help() -> None:
    print("Lyrona")
    print()
    print(f"Data directory: {DATA_DIR}")
    print()
    print("Usage:")
    print("  lyrona")
    print("  lyrona <song name>")
    print("  lyrona list")
    print("  lyrona import <audio_path> [--title TITLE] [--artist ARTIST] [--lyrics PATH]")
    print("  lyrona add-lyrics <song name> <lyrics_path>")
    print("  lyrona retime <song name>")
    print("  lyrona rebuild-cache")


def parse_import_args(args: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lyrona import")
    parser.add_argument("audio_path")
    parser.add_argument("--title")
    parser.add_argument("--artist")
    parser.add_argument("--lyrics")
    parser.add_argument("--move", action="store_true")
    return parser.parse_args(args)


def parse_add_lyrics_args(args: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lyrona add-lyrics")
    parser.add_argument("song_name")
    parser.add_argument("lyrics_path")
    return parser.parse_args(args)


def parse_retime_args(args: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="lyrona retime")
    parser.add_argument("song_name")
    return parser.parse_args(args)


def import_song(
    source_audio_path: Path,
    title: Optional[str] = None,
    artist: Optional[str] = None,
    lyrics_path: Optional[Path] = None,
    move: bool = False,
) -> int:
    source_audio = source_audio_path.expanduser().resolve()
    if not source_audio.exists() or not source_audio.is_file():
        print(f"Audio file not found: {source_audio}")
        return 1

    if source_audio.suffix.lower() not in AUDIO_EXTENSIONS:
        print(f"Unsupported audio format: {source_audio.suffix}")
        return 1

    lyrics_source: Optional[Path] = None
    if lyrics_path is not None:
        lyrics_source = lyrics_path.expanduser().resolve()
        if not lyrics_source.exists() or not lyrics_source.is_file():
            print(f"Lyrics file not found: {lyrics_source}")
            return 1

    audio_metadata = read_audio_metadata(source_audio)
    resolved_title = first_non_empty(
        title or "",
        audio_metadata.get("title", ""),
        audio_metadata.get("tit2", ""),
        source_audio.stem,
    )
    resolved_artist = first_non_empty(
        artist or "",
        audio_metadata.get("artist", ""),
        audio_metadata.get("album_artist", ""),
        audio_metadata.get("albumartist", ""),
        audio_metadata.get("tpe1", ""),
        audio_metadata.get("composer", ""),
        "Unknown Artist",
    )

    folder_name = sanitize_folder_name(resolved_title)
    target_folder = SONGS_DIR / folder_name
    if target_folder.exists():
        print(f"Song folder already exists: {target_folder}")
        print("Use another title with `--title`, or add lyrics with `lyrona add-lyrics`.")
        return 1

    ensure_data_dirs()
    target_folder.mkdir(parents=True, exist_ok=False)
    target_audio = target_folder / f"audio{source_audio.suffix.lower()}"

    if move:
        shutil.move(str(source_audio), str(target_audio))
    else:
        shutil.copy2(source_audio, target_audio)

    if title or artist:
        write_song_metadata_file(
            target_folder,
            title=resolved_title if title else None,
            artist=resolved_artist if artist else None,
        )

    if lyrics_source is not None:
        shutil.copy2(lyrics_source, target_folder / "lyrics.lrc")
        success, message = generate_words_file(target_folder)
        if not success:
            print(f"Imported audio, but failed to build words.json: {message}")
            invalidate_metadata_cache()
            return 1

    invalidate_metadata_cache()
    print(f"Imported: {resolved_title} | {resolved_artist}")
    print(f"Folder: {target_folder}")
    return 0


def add_lyrics_to_song(song_name: str, lyrics_path: Path) -> int:
    songs = discover_songs(SONGS_DIR)
    song = resolve_song_from_query(songs, song_name)
    if song is None:
        print(f'Song not found: "{song_name}"')
        return 1

    source_lyrics = lyrics_path.expanduser().resolve()
    if not source_lyrics.exists() or not source_lyrics.is_file():
        print(f"Lyrics file not found: {source_lyrics}")
        return 1

    shutil.copy2(source_lyrics, song.folder_path / "lyrics.lrc")
    success, message = generate_words_file(song.folder_path)
    if not success:
        print(f"Failed to build words.json: {message}")
        invalidate_metadata_cache()
        return 1

    invalidate_metadata_cache()
    print(f"Lyrics added for: {song.title}")
    return 0


def retime_song(song_name: str) -> int:
    songs = discover_songs(SONGS_DIR)
    song = resolve_song_from_query(songs, song_name)
    if song is None:
        print(f'Song not found: "{song_name}"')
        return 1

    success, message = generate_words_file(song.folder_path)
    if not success:
        print(f"Failed to build words.json: {message}")
        return 1

    print(f"Rebuilt word timings: {message}")
    return 0


def rebuild_cache() -> int:
    invalidate_metadata_cache()
    songs = discover_songs(SONGS_DIR)
    print(f"Cache rebuilt for {len(songs)} song(s).")
    return 0


def run_interactive_menu(songs: List[Song]) -> int:
    while True:
        selected_song = choose_song_interactively(songs)
        if selected_song is None:
            return 0

        result = play_song(selected_song)
        if result != 0:
            return result


def main() -> int:
    args = sys.argv[1:]

    if not args:
        songs = discover_songs(SONGS_DIR)
        if not songs:
            print(f"No valid songs found in: {SONGS_DIR}")
            print("Use `lyrona import <audio_path>` to add your first track.")
            return 1
        return run_interactive_menu(songs)

    command = args[0]

    if command in {"-h", "--help", "help"}:
        print_help()
        return 0

    if command == "list":
        songs = discover_songs(SONGS_DIR)
        if not songs:
            print(f"No valid songs found in: {SONGS_DIR}")
            return 1
        print_available_songs(songs)
        return 0

    if command == "import":
        try:
            parsed = parse_import_args(args[1:])
        except SystemExit as exc:
            return int(exc.code)

        lyrics_path = Path(parsed.lyrics) if parsed.lyrics else None
        return import_song(
            Path(parsed.audio_path),
            title=parsed.title,
            artist=parsed.artist,
            lyrics_path=lyrics_path,
            move=parsed.move,
        )

    if command == "add-lyrics":
        try:
            parsed = parse_add_lyrics_args(args[1:])
        except SystemExit as exc:
            return int(exc.code)
        return add_lyrics_to_song(parsed.song_name, Path(parsed.lyrics_path))

    if command == "retime":
        try:
            parsed = parse_retime_args(args[1:])
        except SystemExit as exc:
            return int(exc.code)
        return retime_song(parsed.song_name)

    if command == "rebuild-cache":
        return rebuild_cache()

    songs = discover_songs(SONGS_DIR)
    if not songs:
        print(f"No valid songs found in: {SONGS_DIR}")
        print("Use `lyrona import <audio_path>` to add your first track.")
        return 1

    query = " ".join(args).strip()
    selected_song = resolve_song_from_query(songs, query)

    if not selected_song:
        print(f'Song not found: "{query}"')
        print()
        print_available_songs(songs)
        return 1

    return play_song(selected_song)


def load_timed_lines(song_folder: Path) -> Optional[List[dict]]:
    words_file = song_folder / "words.json"

    if not words_file.exists():
        return None

    try:
        with words_file.open("r", encoding="utf-8") as f:
            data = json.load(f)

        lines = data.get("lines", [])
        if not isinstance(lines, list):
            return None

        normalized_lines: List[dict] = []

        for line in lines:
            words = []
            for w in line.get("words", []):
                words.append(
                    {
                        "word": str(w["word"]),
                        "start": float(w["start"]),
                        "end": float(w["end"]),
                    }
                )

            if not words:
                continue

            normalized_lines.append(
                {
                    "text": str(line.get("text", "")),
                    "start": float(line["start"]),
                    "end": float(line["end"]),
                    "words": words,
                }
            )

        normalized_lines.sort(key=lambda x: x["start"])
        return normalized_lines

    except Exception:
        return None

def ease_soft(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x ** 0.85


def compute_word_line(lines: List[dict], current_time: float) -> str:
    if not lines:
        return ""

    active_index = None

    for i, line in enumerate(lines):
        line_start = float(line["start"])

        if i + 1 < len(lines):
            next_start = float(lines[i + 1]["start"])
        else:
            next_start = float(line["end"]) + 2.0

        if line_start <= current_time < next_start:
            active_index = i
            break

    if active_index is None:
        return ""

    active_line = lines[active_index]
    words = active_line["words"]

    if not words:
        return ""

    visible_words: List[str] = []

    for word in words:
        start = float(word["start"])
        end = float(word["end"])
        text = str(word["word"])

        if current_time < start:
            break

        if current_time >= end:
            visible_words.append(text)
            continue

        duration = max(0.18, end - start)
        progress = (current_time - start) / duration
        progress = ease_soft(progress)
        
        chars = int(len(text) * progress)
        chars = max(1, chars)
        chars = min(len(text), chars)
        
        typed = text[:chars]
        
        if chars < len(text):
            typed += "▌"

        visible_words.append(typed)
        return " ".join(visible_words)

    # Если все слова строки уже закончились,
    # держим полную строку до старта следующей строки
    return " ".join(visible_words)


if __name__ == "__main__":
    raise SystemExit(main())
