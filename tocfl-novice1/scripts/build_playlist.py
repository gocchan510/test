"""Concatenate per-word MP3s into a single full-loop MP3.

Layout per word (id):
  <id>_zh.mp3  silence(GAP_REPEAT)  <id>_zh.mp3  silence(GAP_BETWEEN)  <id>_ja.mp3  silence(GAP_NEXT)

Then all 160 words concatenated in CSV order.

Output:
  audio/playlists/full_1.0x.mp3
  audio/playlists/full_0.7x.mp3   (slower, atempo=0.7)
  audio/playlists/full_1.3x.mp3   (faster, atempo=1.3)
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOCAB = ROOT / "data" / "vocabulary.json"
WORDS = ROOT / "audio" / "words"
PLAY = ROOT / "audio" / "playlists"
SILENCE_DIR = ROOT / "audio" / "_silence"

# Silence intervals (seconds) within a single word block:
GAP_REPEAT = 0.5    # between 1st and 2nd Chinese reading
GAP_BETWEEN = 1.0   # between Chinese (2nd) and Japanese
GAP_NEXT = 2.0      # between this word's Japanese and next word's 1st Chinese

# MP3 encode options for re-encoding so concat works regardless of edge-tts variations.
MP3_BITRATE = "96k"
SAMPLE_RATE = "24000"  # edge-tts default is 24kHz mono
CHANNELS = "1"


def run(cmd: list[str]) -> None:
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        print(" ".join(cmd), file=sys.stderr)
        print(res.stderr, file=sys.stderr)
        raise SystemExit(res.returncode)


def make_silence(seconds: float, out: Path) -> None:
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"anullsrc=r={SAMPLE_RATE}:cl=mono",
        "-t", f"{seconds}",
        "-ar", SAMPLE_RATE, "-ac", CHANNELS, "-b:a", MP3_BITRATE,
        str(out),
    ])


def normalize_to_mp3(src: Path, dst: Path) -> None:
    """Re-encode an MP3 to a uniform format so ffmpeg concat demuxer is happy."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-ar", SAMPLE_RATE, "-ac", CHANNELS, "-b:a", MP3_BITRATE,
        str(dst),
    ])


def build_concat_list(parts: list[Path], list_path: Path) -> None:
    list_path.write_text(
        "".join(f"file '{p.resolve()}'\n" for p in parts),
        encoding="utf-8",
    )


def concat(parts: list[Path], out: Path) -> None:
    """Concatenate same-format MP3s with the concat demuxer (no re-encode)."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        for p in parts:
            f.write(f"file '{p.resolve()}'\n")
        list_path = Path(f.name)
    try:
        run([
            "ffmpeg", "-y", "-f", "concat", "-safe", "0",
            "-i", str(list_path),
            "-c", "copy", str(out),
        ])
    finally:
        list_path.unlink(missing_ok=True)


def speed_variant(src: Path, dst: Path, tempo: float) -> None:
    """Generate a speed-altered copy via atempo (preserves pitch)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y", "-i", str(src),
        "-filter:a", f"atempo={tempo}",
        "-ar", SAMPLE_RATE, "-ac", CHANNELS, "-b:a", MP3_BITRATE,
        str(dst),
    ])


def main() -> None:
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))

    # Validate inputs are present.
    missing: list[str] = []
    for e in vocab:
        for suffix in ("_zh.mp3", "_ja.mp3"):
            p = WORDS / f"{e['id']}{suffix}"
            if not p.exists() or p.stat().st_size == 0:
                missing.append(p.name)
    if missing:
        print(
            f"Missing {len(missing)} per-word audio files. Run generate_audio.py first.\n"
            f"First few missing: {missing[:5]}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    # Build silence files.
    sil_repeat = SILENCE_DIR / f"sil_{GAP_REPEAT}.mp3"
    sil_between = SILENCE_DIR / f"sil_{GAP_BETWEEN}.mp3"
    sil_next = SILENCE_DIR / f"sil_{GAP_NEXT}.mp3"
    make_silence(GAP_REPEAT, sil_repeat)
    make_silence(GAP_BETWEEN, sil_between)
    make_silence(GAP_NEXT, sil_next)

    # Normalize all per-word MP3s to a uniform encoding so concat-demuxer works.
    norm_dir = ROOT / "audio" / "_normalized"
    norm_dir.mkdir(parents=True, exist_ok=True)
    for e in vocab:
        for suffix in ("_zh.mp3", "_ja.mp3"):
            src = WORDS / f"{e['id']}{suffix}"
            dst = norm_dir / f"{e['id']}{suffix}"
            if not dst.exists():
                normalize_to_mp3(src, dst)

    # Assemble parts list per word: zh, sil_repeat, zh, sil_between, ja, sil_next
    parts: list[Path] = []
    for e in vocab:
        zh = norm_dir / f"{e['id']}_zh.mp3"
        ja = norm_dir / f"{e['id']}_ja.mp3"
        parts += [zh, sil_repeat, zh, sil_between, ja, sil_next]

    base = PLAY / "full_1.0x.mp3"
    concat(parts, base)
    print(f"Wrote {base}")

    # Speed variants
    speed_variant(base, PLAY / "full_0.7x.mp3", 0.7)
    speed_variant(base, PLAY / "full_1.3x.mp3", 1.3)
    print(f"Wrote {PLAY/'full_0.7x.mp3'} and {PLAY/'full_1.3x.mp3'}")

    # Optional cleanup: keep the normalized dir for reuse on incremental rebuilds.
    # Comment out the next line if you want to wipe intermediates.
    # shutil.rmtree(norm_dir)


if __name__ == "__main__":
    main()
