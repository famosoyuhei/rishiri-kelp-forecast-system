from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageFilter
import qrcode


ROOT = Path(__file__).resolve().parents[1]
PHOTO = ROOT / "利尻島写真" / "IMG_2075.JPG"
OUT_DIR = ROOT / "outputs" / "rishiri_launch_assets"
URL = "https://rishiri-kelp-forecast-system.onrender.com/island"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        "C:/Windows/Fonts/YuGothB.ttc" if bold else "C:/Windows/Fonts/YuGothM.ttc",
        "C:/Windows/Fonts/meiryob.ttc" if bold else "C:/Windows/Fonts/meiryo.ttc",
        "C:/Windows/Fonts/msgothic.ttc",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def cover_image(img: Image.Image, size: tuple[int, int], focus_y: float = 0.58) -> Image.Image:
    img = ImageOps.exif_transpose(img).convert("RGB")
    target_w, target_h = size
    scale = max(target_w / img.width, target_h / img.height)
    resized = img.resize((round(img.width * scale), round(img.height * scale)), Image.Resampling.LANCZOS)
    left = (resized.width - target_w) // 2
    top = round((resized.height - target_h) * focus_y)
    top = max(0, min(top, resized.height - target_h))
    return resized.crop((left, top, left + target_w, top + target_h))


def rounded_rectangle_layer(size, radius, fill):
    layer = Image.new("RGBA", size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    draw.rounded_rectangle((0, 0, size[0], size[1]), radius=radius, fill=fill)
    return layer


def paste_panel(base, box, radius=34, fill=(255, 255, 255, 232), shadow=True):
    x1, y1, x2, y2 = box
    w, h = x2 - x1, y2 - y1
    if shadow:
        shadow_layer = rounded_rectangle_layer((w, h), radius, (0, 0, 0, 105)).filter(ImageFilter.GaussianBlur(14))
        base.alpha_composite(shadow_layer, (x1 + 8, y1 + 10))
    panel = rounded_rectangle_layer((w, h), radius, fill)
    base.alpha_composite(panel, (x1, y1))


def draw_wrapped(draw, text, xy, max_width, fnt, fill, line_gap=10):
    x, y = xy
    lines = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            candidate = current + ch
            if draw.textbbox((0, 0), candidate, font=fnt)[2] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = ch
        lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=fnt, fill=fill)
        y += fnt.size + line_gap
    return y


def make_qr(size: int) -> Image.Image:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=3)
    qr.add_data(URL)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#0f172a", back_color="white").convert("RGB")
    return img.resize((size, size), Image.Resampling.NEAREST)


def add_brand_mark(draw, xy, size=20):
    x, y = xy
    draw.rounded_rectangle((x, y, x + size, y + size), radius=5, fill="#0f766e")
    draw.line((x + 5, y + size - 6, x + size // 2, y + 6, x + size - 5, y + size - 8), fill="white", width=3)


def make_square(photo: Image.Image):
    W = H = 1080
    base = cover_image(photo, (W, H), 0.48).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, H), fill=(0, 24, 38, 78))
    od.rectangle((0, 0, W, 460), fill=(0, 20, 30, 96))
    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)

    draw.text((58, 58), "利尻島で昆布を干す方へ", font=font(60, True), fill="white")
    draw.text((60, 142), "干場ごとの7日間乾燥予報", font=font(48, True), fill="#dff7ff")
    draw.text((62, 214), "スマホで確認できます", font=font(44, True), fill="white")

    body = "地図から自分の干場を選んで、明日の段取りの判断材料に。"
    draw_wrapped(draw, body, (64, 300), 760, font(28), "white", 8)

    paste_panel(base, (58, 738, 1022, 1018), radius=34)
    draw = ImageDraw.Draw(base)
    qr = make_qr(210)
    base.paste(qr, (770, 772))
    draw.text((92, 776), "無料公開中", font=font(34, True), fill="#0f766e")
    draw.text((92, 830), "2026年9月末まで", font=font(48, True), fill="#111827")
    draw.text((92, 902), "予報は補助情報です。現地の空・風・海も確認してください。", font=font(24), fill="#374151")
    add_brand_mark(draw, (92, 960), 22)
    draw.text((124, 955), "rishiri-kelp-forecast-system.onrender.com/island", font=font(22), fill="#1f2937")

    out = OUT_DIR / "rishiri_island_qr_post_square.png"
    base.convert("RGB").save(out, quality=95)
    return out


def make_story(photo: Image.Image):
    W, H = 1080, 1920
    base = cover_image(photo, (W, H), 0.46).convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    od.rectangle((0, 0, W, H), fill=(0, 23, 34, 68))
    od.rectangle((0, 0, W, 760), fill=(0, 20, 30, 126))
    od.rectangle((0, 1450, W, H), fill=(0, 20, 30, 104))
    base.alpha_composite(overlay)
    draw = ImageDraw.Draw(base)

    draw.text((70, 92), "利尻島で", font=font(64, True), fill="#dff7ff")
    draw.text((70, 176), "昆布を干す方へ", font=font(78, True), fill="white")
    draw.text((72, 306), "干場ごとの", font=font(50, True), fill="white")
    draw.text((72, 374), "7日間乾燥予報", font=font(74, True), fill="#fef3c7")
    draw.text((76, 490), "スマホで確認できます", font=font(44, True), fill="white")
    draw_wrapped(draw, "地図から自分の干場を選んで、明日の段取りの判断材料にしてください。", (78, 570), 850, font(30), "white", 10)

    paste_panel(base, (80, 1408, 1000, 1808), radius=40)
    draw = ImageDraw.Draw(base)
    qr = make_qr(250)
    base.paste(qr, (700, 1484))
    draw.text((126, 1474), "2026年9月末まで", font=font(42, True), fill="#111827")
    draw.text((126, 1538), "自由に使えます", font=font(52, True), fill="#0f766e")
    draw.text((126, 1626), "予報は作業判断の補助情報です。", font=font(27), fill="#374151")
    draw.text((126, 1668), "現地の空・風・海も確認してください。", font=font(27), fill="#374151")
    draw.text((126, 1744), "QRから開く", font=font(28, True), fill="#111827")

    out = OUT_DIR / "rishiri_island_qr_story.png"
    base.convert("RGB").save(out, quality=95)
    return out


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    photo = Image.open(PHOTO)
    qr = make_qr(720)
    qr_out = OUT_DIR / "rishiri_island_qr_code.png"
    qr.save(qr_out)
    print(qr_out)
    print(make_square(photo))
    print(make_story(photo))


if __name__ == "__main__":
    main()
