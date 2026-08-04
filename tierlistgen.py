
from PIL import Image, ImageDraw, ImageFont
import math
import os
from collections import OrderedDict
import re

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, "Databases", "Tierlist")
SONG_LIST_PATH = os.path.join(DB_DIR, "songslist.json")
tier_colors = {
    "SSS": (65, 105, 225),  
    "S+": (56, 84, 168), 
    "S": (50, 69, 128),   
    "A": (37, 49, 84), 
    "B": (26, 27, 54), 
    "C": (13, 11, 23),  
    "D": (5, 5, 11),  
}
tier_order = ["SSS", "S+", "S", "A", "B", "C", "D"]
def tlm(tiers, entries_dir):
    tiers = OrderedDict((key, tiers[key]) for key in tier_order if key in tiers)
    width = 1300
    rows = 0
    for tier in tiers:
        rows += 1 if math.ceil(len(tiers[tier])/7) == 0 else math.ceil(len(tiers[tier])/7)
        print(f"{tier} has {rows} rows")
    height = rows*150
    tierlistimage = Image.new("RGB",(width,height), (36, 45, 51))
    draw = ImageDraw.Draw(tierlistimage)
    lowerbound, upperbound = 0,0
    font_path = os.path.join(BASE_DIR, "fonts", "DejaVuSans-Bold.ttf")
    font = ImageFont.truetype(font_path, size=40)
    row, column = 0, -1 
    for tier in tiers:
        lowerbound += 1 if math.ceil(len(tiers[tier])/7) == 0 else math.ceil(len(tiers[tier])/7)
        upperbound = lowerbound - (1 if math.ceil(len(tiers[tier])/7) == 0 else math.ceil(len(tiers[tier])/7)) 
        draw.rectangle((0,upperbound*150,250,lowerbound*150),tier_colors[tier])
        textcentre_y, textcentre_x= ((lowerbound+upperbound)/2) * 150, 125
        tierlabel = tier
        bbox = draw.textbbox((0,0), tierlabel, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = textcentre_x - text_width / 2
        y = textcentre_y - text_height / 2
        draw.text((x, y), tierlabel, fill=(255,255,255), font=font)
        print(tier)
        for song in tiers[tier]:
            if column == 6:
                column = 0
                row+=1
            else:
                column += 1
            print(f"{song} being loaded")
            clean_name = re.sub(r'[<>:"/\\|?*]', '_', song)
            image_path = os.path.join(entries_dir, f"{clean_name}.png")
            print(f"loading {image_path} for {song}")
            try:
                icon = Image.open(image_path).convert("RGBA")
                icon = icon.resize((150, 150))
            except Exception as e:
                print(f"Failed to load image for {song}: {e}, using placeholder")
                icon = Image.new("RGBA", (150, 150), (128, 128, 128, 255)) 
            tierlistimage.paste(icon, ((column*150)+250, row*150), mask=icon)

        column = -1
        row +=1
    return tierlistimage
