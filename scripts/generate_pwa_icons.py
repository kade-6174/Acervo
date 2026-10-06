"""既存のPillowで自己配信PWAアイコンを再生成する。"""

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).resolve().parents[1] / "static" / "pwa"


def draw_icon(size: int) -> Image.Image:
    image = Image.new("RGB", (size, size), "#212529")
    draw = ImageDraw.Draw(image)
    scale = size / 512

    def box(left, top, right, bottom, color, radius=0):
        draw.rounded_rectangle(
            tuple(round(value * scale) for value in (left, top, right, bottom)),
            radius=round(radius * scale),
            fill=color,
        )

    box(84, 112, 428, 400, "#ffffff", 34)
    box(105, 138, 407, 216, "#ced4da", 13)
    box(148, 258, 364, 287, "#212529", 8)
    box(191, 309, 321, 336, "#495057", 8)
    return image


if __name__ == "__main__":
    OUTPUT.mkdir(parents=True, exist_ok=True)
    for dimension in (192, 512):
        draw_icon(dimension).save(OUTPUT / f"icon-{dimension}.png", optimize=True)
