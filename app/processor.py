import subprocess
import os
import random
import uuid
from pathlib import Path
from typing import Optional

TMP_DIR = Path(os.getenv("UNICAL_TMP_DIR", "/tmp/unical"))


def random_preset() -> dict:
    return {
        "brightness": round(random.uniform(-0.07, 0.07), 3),
        "contrast": round(random.uniform(0.95, 1.08), 3),
        "saturation": round(random.uniform(0.95, 1.08), 3),
        "zoom": round(random.uniform(1.02, 1.05), 3),
        "fps": random.choice(["29.97", "25", "23.976"]),
        "audio_rate": random.choice([44100, 48000]),
        "audio_bitrate": random.choice(["128k", "160k"]),
        "text_x_ratio": round(random.uniform(0.05, 0.75), 2),
        "text_y_ratio": round(random.uniform(0.05, 0.75), 2),
        "text_opacity": round(random.uniform(0.10, 0.22), 2),
    }


def process_video(
    input_path: str,
    watermark_path: Optional[str] = None,
    preset: Optional[dict] = None,
) -> str:
    """Apply visual + technical uniquification. Returns path to output .mp4."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    output_path = str(TMP_DIR / f"uniq_{uuid.uuid4().hex[:8]}.mp4")

    if preset is None:
        preset = random_preset()

    orig_w, orig_h = _get_dimensions(input_path)
    preset = {**preset, "orig_w": orig_w, "orig_h": orig_h}

    has_wm = watermark_path and os.path.exists(watermark_path)
    cmd = _build_cmd(input_path, output_path, preset, watermark_path if has_wm else None)

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
    if result.returncode != 0:
        raise RuntimeError(f"Ошибка ffmpeg:\n{result.stderr[-2500:]}")

    return output_path


def _get_dimensions(path: str) -> tuple[int, int]:
    cmd = [
        "ffprobe", "-v", "quiet",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "csv=p=0",
        path,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    if result.returncode != 0 or not result.stdout.strip():
        return 1920, 1080
    w, h = map(int, result.stdout.strip().split(","))
    return w, h


def _build_vf(preset: dict) -> str:
    b = preset["brightness"]
    c = preset["contrast"]
    s = preset["saturation"]
    z = preset["zoom"]
    orig_w = preset["orig_w"]
    orig_h = preset["orig_h"]
    tx = preset["text_x_ratio"]
    ty = preset["text_y_ratio"]
    top = preset["text_opacity"]

    # Scaled dimensions (must be even for libx264)
    scaled_w = (int(orig_w * z) // 2) * 2
    scaled_h = (int(orig_h * z) // 2) * 2
    crop_w = (orig_w // 2) * 2
    crop_h = (orig_h // 2) * 2

    # Box size and position in pixels (drawtext requires freetype; drawbox is always available)
    bx = int(crop_w * tx)
    by = int(crop_h * ty)
    bw = random.randint(30, 80)
    bh = random.randint(15, 40)
    opacity = round(top * 0.6, 2)  # keep it very subtle

    return ",".join([
        f"eq=brightness={b}:contrast={c}:saturation={s}",
        f"scale={scaled_w}:{scaled_h}",
        f"crop={crop_w}:{crop_h}",
        "noise=alls=3:allf=a+u",
        f"drawbox=x={bx}:y={by}:w={bw}:h={bh}:color=white@{opacity}:t=fill",
    ])


def _common_encode_args(preset: dict, output_path: str) -> list:
    return [
        "-c:v", "libx264", "-crf", "23", "-preset", "fast",
        "-r", str(preset["fps"]),
        "-c:a", "aac",
        "-ar", str(preset["audio_rate"]),
        "-b:a", preset["audio_bitrate"],
        "-map_metadata", "-1",
        "-metadata", "encoder=",
        "-movflags", "+faststart",
        output_path,
    ]


def _build_cmd(
    input_path: str,
    output_path: str,
    preset: dict,
    watermark_path: Optional[str],
) -> list:
    encode = _common_encode_args(preset, output_path)

    if watermark_path:
        vf_base = _build_vf(preset)
        filter_complex = (
            f"[0:v]{vf_base}[base];"
            f"[1:v]scale=90:90,format=rgba,colorchannelmixer=aa=0.45[wm];"
            f"[base][wm]overlay=W-110:H-110[vout]"
        )
        return [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", watermark_path,
            "-filter_complex", filter_complex,
            "-map", "[vout]",
            "-map", "0:a?",
        ] + encode

    vf = _build_vf(preset)
    return [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", vf,
        "-map", "0:v:0",
        "-map", "0:a?",
    ] + encode
