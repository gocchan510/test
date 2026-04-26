"""Generate per-word MP3s using edge-tts.

For each entry, produce two files in audio/words/:
  <id>_zh.mp3  -- Taiwan Mandarin (female voice)
  <id>_ja.mp3  -- Japanese (male voice)

edge-tts is rate-limited per request, so we serialize requests with a small
async semaphore and skip files already present (idempotent re-runs).
"""
import asyncio
import json
import sys
from pathlib import Path

import edge_tts

ROOT = Path(__file__).resolve().parent.parent
VOCAB = ROOT / "data" / "vocabulary.json"
OUT_DIR = ROOT / "audio" / "words"

ZH_VOICE = "zh-TW-HsiaoChenNeural"   # Taiwan Mandarin female
JA_VOICE = "ja-JP-KeitaNeural"        # Japanese male

CONCURRENCY = 4


async def synth(text: str, voice: str, out: Path) -> None:
    if out.exists() and out.stat().st_size > 0:
        return
    communicate = edge_tts.Communicate(text=text, voice=voice)
    await communicate.save(str(out))


async def synth_one(sem: asyncio.Semaphore, entry: dict) -> tuple[str, bool]:
    async with sem:
        wid = entry["id"]
        zh_out = OUT_DIR / f"{wid}_zh.mp3"
        ja_out = OUT_DIR / f"{wid}_ja.mp3"
        try:
            await synth(entry["tw"], ZH_VOICE, zh_out)
            await synth(entry["ja"], JA_VOICE, ja_out)
            return wid, True
        except Exception as e:
            print(f"[FAIL] {wid} {entry['tw']!r}/{entry['ja']!r}: {e}", file=sys.stderr)
            return wid, False


async def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    vocab = json.loads(VOCAB.read_text(encoding="utf-8"))
    sem = asyncio.Semaphore(CONCURRENCY)
    tasks = [synth_one(sem, e) for e in vocab]
    done = 0
    failed: list[str] = []
    for coro in asyncio.as_completed(tasks):
        wid, ok = await coro
        done += 1
        if not ok:
            failed.append(wid)
        if done % 10 == 0 or done == len(tasks):
            print(f"  progress: {done}/{len(tasks)} (failed so far: {len(failed)})")
    if failed:
        print(f"FAILED ({len(failed)}): {failed}", file=sys.stderr)
        sys.exit(1)
    print(f"OK: {len(vocab)} entries -> {OUT_DIR}")


if __name__ == "__main__":
    asyncio.run(main())
