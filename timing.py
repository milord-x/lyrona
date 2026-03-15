from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from paths import SONGS_DIR

TIMED_LINE_PATTERN = re.compile(r"^\[(\d+):(\d+(?:\.\d+)?)\](.*)$")
TOKEN_PATTERN = re.compile(r"\S+")


@dataclass(slots=True)
class LyricLine:
    time_sec: float
    text: str


@dataclass(slots=True)
class WordTiming:
    word: str
    start: float
    end: float
    line_index: int
    word_index: int


def normalize_name(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip().lower())


def resolve_song_dir(song_name: str) -> Path:
    direct = SONGS_DIR / song_name
    if direct.exists() and direct.is_dir():
        return direct

    wanted = normalize_name(song_name)

    for item in SONGS_DIR.iterdir():
        if item.is_dir() and normalize_name(item.name) == wanted:
            return item

    raise FileNotFoundError(f"Song folder not found: {song_name}")


def parse_lrc_lines(path: Path) -> List[LyricLine]:
    lines: List[LyricLine] = []

    with path.open("r", encoding="utf-8") as handle:
        for raw in handle:
            stripped = raw.rstrip("\n").rstrip("\r").strip()
            if not stripped:
                continue

            match = TIMED_LINE_PATTERN.match(stripped)
            if not match:
                continue

            minutes = int(match.group(1))
            seconds = float(match.group(2))
            text = match.group(3).strip()

            total_sec = minutes * 60 + seconds
            lines.append(LyricLine(time_sec=total_sec, text=text))

    lines.sort(key=lambda x: x.time_sec)
    return lines


def split_words(text: str) -> List[str]:
    return TOKEN_PATTERN.findall(text)


def clean_word(word: str) -> str:
    return re.sub(r"[^\w']+", "", word, flags=re.UNICODE)


def word_weight(word: str) -> float:
    cleaned = clean_word(word)
    base_len = max(1, len(cleaned))

    weight = 0.70 + base_len * 0.24

    if "," in word:
        weight += 0.20
    if ";" in word or ":" in word:
        weight += 0.26
    if "." in word or "!" in word or "?" in word:
        weight += 0.36

    return weight


def estimate_line_duration(text: str) -> float:
    words = split_words(text)
    if not words:
        return 0.0

    total_weight = sum(word_weight(word) for word in words)

    duration = total_weight * 0.18
    duration = max(1.60, duration)
    duration = min(6.50, duration)

    return duration


def build_word_timings(lines: List[LyricLine]) -> List[WordTiming]:
    all_words: List[WordTiming] = []

    for line_index, line in enumerate(lines):
        words = split_words(line.text)
        if not words:
            continue

        start_time = line.time_sec

        if line_index + 1 < len(lines):
            next_start = lines[line_index + 1].time_sec
        else:
            next_start = start_time + 6.50

        estimated_duration = estimate_line_duration(line.text)
        line_end = min(next_start, start_time + estimated_duration)

        if line_end <= start_time:
            continue

        weights = [word_weight(word) for word in words]
        total_weight = sum(weights)
        total_span = line_end - start_time

        cursor = start_time

        for word_index, (word, weight) in enumerate(zip(words, weights)):
            duration = total_span * (weight / total_weight)
            word_start = cursor
            word_end = cursor + duration

            all_words.append(
                WordTiming(
                    word=word,
                    start=round(word_start, 3),
                    end=round(word_end, 3),
                    line_index=line_index,
                    word_index=word_index,
                )
            )

            cursor = word_end

    return all_words


def group_words_by_line(words: List[WordTiming]) -> List[List[WordTiming]]:
    if not words:
        return []

    grouped: List[List[WordTiming]] = []
    current_group: List[WordTiming] = []
    current_line_index: Optional[int] = None

    for item in words:
        if current_line_index is None or item.line_index != current_line_index:
            if current_group:
                grouped.append(current_group)
            current_group = [item]
            current_line_index = item.line_index
        else:
            current_group.append(item)

    if current_group:
        grouped.append(current_group)

    return grouped


def build_payload(song_name: str, lrc_path: Path, lines: List[LyricLine], grouped_words: List[List[WordTiming]]) -> dict:
    payload_lines = []

    for group in grouped_words:
        line_index = group[0].line_index
        original_line = lines[line_index]

        payload_lines.append(
            {
                "line_index": line_index,
                "text": original_line.text,
                "start": group[0].start,
                "end": group[-1].end,
                "words": [
                    {
                        "word": item.word,
                        "start": item.start,
                        "end": item.end,
                    }
                    for item in group
                ],
            }
        )

    return {
        "title": song_name,
        "source_lrc": str(lrc_path),
        "lines": payload_lines,
    }


def main() -> int:
    if len(sys.argv) < 2:
        print('Usage: python timing.py "Washing Machine Heart"')
        return 1

    song_name = " ".join(sys.argv[1:]).strip()

    try:
        song_dir = resolve_song_dir(song_name)
        lrc_path = song_dir / "lyrics.lrc"
        output_path = song_dir / "words.json"

        if not lrc_path.exists():
            print(f"ERROR: lyrics.lrc not found in {song_dir}")
            return 1

        lines = parse_lrc_lines(lrc_path)
        if not lines:
            print(f"ERROR: no timed lyric lines found in {lrc_path}")
            return 1

        words = build_word_timings(lines)
        if not words:
            print("ERROR: no word timings generated")
            return 1

        grouped_words = group_words_by_line(words)
        payload = build_payload(song_dir.name, lrc_path, lines, grouped_words)

        with output_path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

        print(f"OK: created {output_path}")
        return 0

    except Exception as exc:
        print(f"ERROR: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
