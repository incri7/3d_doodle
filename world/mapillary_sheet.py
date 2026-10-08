"""Contact sheet of the Mapillary Ring Road photos + a map of where each was taken."""
import datetime, json, os
from PIL import Image, ImageDraw, ImageFont

from fetch_osm import OUT

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DST = os.path.join(ROOT, "output", "ktm_ringroad")


def main():
    src = os.path.join(OUT, "mapillary")
    meta = json.load(open(os.path.join(src, "index.json")))
    cols, tw, th = 8, 320, 240
    rows = (len(meta) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), (20, 20, 22))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype(os.path.join(ROOT, "assets", "fonts", "Oswald-Bold.ttf"), 15)
    except OSError:
        font = ImageFont.load_default()
    for k, m in enumerate(meta):
        im = Image.open(os.path.join(src, m["file"])).convert("RGB")
        im = im.resize((tw, int(im.height * tw / im.width)))
        im = im.crop((0, (im.height - th) // 2, tw, (im.height - th) // 2 + th))
        x, y = (k % cols) * tw, (k // cols) * th
        sheet.paste(im, (x, y))
        date = datetime.datetime.fromtimestamp(m["date"] / 1000).strftime("%Y-%m")
        label = f"#{m['i']}  {date}  @{m['author']}"
        d.rectangle((x, y + th - 20, x + tw, y + th), fill=(0, 0, 0))
        d.text((x + 6, y + th - 19), label, fill=(240, 220, 160), font=font)
    sheet.save(os.path.join(DST, "mapillary_ringroad_sheet.jpg"), quality=85)
    # where the photos are, on the overview render
    ov = os.path.join(DST, "overview.png")
    if os.path.exists(ov):
        prep = json.load(open(os.path.join(OUT, "prep.json")))
        mp = Image.open(ov).convert("RGB")
        W, H = mp.size
        scale = max(W, H) / 11800.0               # ortho_scale spans the longer side of the overview shot
        dm = ImageDraw.Draw(mp)
        for m in meta:
            x = (m["lon"] - prep["lon0"]) * prep["kx"] * scale + W / 2
            y = H / 2 - (m["lat"] - prep["lat0"]) * prep["ky"] * scale
            dm.ellipse((x - 9, y - 9, x + 9, y + 9), fill=(255, 40, 40), outline=(255, 255, 255), width=2)
        mp.thumbnail((1400, 1600))
        mp.save(os.path.join(DST, "mapillary_ringroad_map.jpg"), quality=88)
    print("sheet", len(meta))


if __name__ == "__main__":
    main()
