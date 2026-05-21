"""Generate the KenoStudio watermark PNG used as video overlay."""
import os
import sys
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    print("Pillow не установлен: pip install Pillow")
    sys.exit(1)


def generate_sticker(output_path: str = "assets/sticker.png", size: int = 120) -> None:
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    m = 5
    draw.ellipse([m, m, size - m - 1, size - m - 1], fill=(255, 255, 255, 200))
    draw.ellipse([m + 3, m + 3, size - m - 4, size - m - 4], outline=(40, 40, 40, 80), width=2)

    font_size = size // 2
    font = None
    for font_path in [
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/Arial.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]:
        if os.path.exists(font_path):
            try:
                font = ImageFont.truetype(font_path, font_size)
                break
            except Exception:
                continue

    if font is None:
        font = ImageFont.load_default()

    text = "K"
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = (size - tw) // 2 - bbox[0]
    y = (size - th) // 2 - bbox[1]
    draw.text((x, y), text, fill=(20, 20, 20, 230), font=font)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(output_path, "PNG")
    print(f"Стикер создан: {output_path} ({size}×{size}px)")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "assets/sticker.png"
    generate_sticker(out)
