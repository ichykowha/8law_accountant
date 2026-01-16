from PIL import Image, ImageDraw, ImageFont
import platform

# 1. Setup Canvas (Navy Blue Background)
size = (512, 512)
background_color = "#0F172A"  # Professional Navy
text_color = "#FFD700"        # Gold
img = Image.new('RGB', size, color=background_color)
d = ImageDraw.Draw(img)

# 2. Draw the Scales (Using simple geometric shapes since we can't rely on fonts)
# Center Post
d.rectangle([250, 100, 262, 350], fill=text_color)
# Base
d.ellipse([206, 330, 306, 370], fill=text_color)
# Crossbar
d.rectangle([100, 150, 412, 162], fill=text_color)
# Left Pan String
d.line([(100, 162), (60, 250)], fill=text_color, width=3)
d.line([(100, 162), (140, 250)], fill=text_color, width=3)
# Right Pan String
d.line([(412, 162), (372, 250)], fill=text_color, width=3)
d.line([(412, 162), (452, 250)], fill=text_color, width=3)
# Left Pan (Bowl)
d.chord([60, 230, 140, 270], 0, 180, fill=text_color)
# Right Pan (Bowl)
d.chord([372, 230, 452, 270], 0, 180, fill=text_color)

# 3. Draw "8LAW" Text
# We draw it pixel-by-pixel-ish or use default font to ensure it works on any PC
try:
    # Try to load a generic font (size 80)
    font = ImageFont.truetype("arial.ttf", 100)
    text = "8LAW"
    # Calculate text position to center it
    text_bbox = d.textbbox((0, 0), text, font=font)
    text_width = text_bbox[2] - text_bbox[0]
    d.text(((512 - text_width) / 2, 380), text, font=font, fill=text_color)
except IOError:
    # Fallback if arial isn't found (Linux/Mac) - Draw a simple line instead
    d.rectangle([156, 400, 356, 410], fill=text_color)

# 4. Save
img.save('favicon.png')
print("✅ Icon created: favicon.png")