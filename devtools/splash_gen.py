from PIL import Image, ImageDraw, ImageFont

from fusion_collection.__version__ import VERSION

img = Image.new("RGB", (800, 400), (255, 255, 255))
icon = Image.open("assets/icon.png")
icon = icon.resize((300, 300))
img.paste(icon, (50, 50), icon)
draw = ImageDraw.Draw(img)
font = ImageFont.truetype("arial.ttf", 80)
font2 = ImageFont.truetype("arial.ttf", 40)
draw.text(
    (400, 200),
    f"Fusion\nCollection\nv{VERSION}",
    font=font,
    fill=(0, 0, 0),
    anchor="lm",
)
draw.text((800, 400), "Идет загрузка...", font=font2, fill=(0, 0, 0), anchor="rd")
img.save("fusion_collection/ui/splash.png")
