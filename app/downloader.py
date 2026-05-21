import subprocess
import os
import uuid
from pathlib import Path

TMP_DIR = Path(os.getenv("UNICAL_TMP_DIR", "/tmp/unical"))


def download_video(url: str) -> str:
    """Download video from URL using yt-dlp. Returns path to downloaded .mp4."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    file_id = uuid.uuid4().hex[:8]
    output_template = str(TMP_DIR / f"dl_{file_id}.%(ext)s")

    cmd = [
        "yt-dlp",
        "--no-playlist",
        "--format", "bv*[ext=mp4]+ba/b[ext=mp4]/bv*+ba/b",
        "--merge-output-format", "mp4",
        "--no-warnings",
        "--quiet",
        "--output", output_template,
        url,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    if result.returncode != 0:
        msg = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"Не удалось скачать видео.\n{msg[:500]}")

    mp4_path = str(TMP_DIR / f"dl_{file_id}.mp4")
    if os.path.exists(mp4_path):
        return mp4_path

    candidates = sorted(TMP_DIR.glob(f"dl_{file_id}.*"), key=lambda f: f.stat().st_mtime, reverse=True)
    if candidates:
        return str(candidates[0])

    raise FileNotFoundError("Скачанный файл не найден. Проверьте ссылку и повторите попытку.")
