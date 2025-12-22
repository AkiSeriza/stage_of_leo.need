
from PIL import Image, ImageDraw, ImageFont
import math
import requests
from io import BytesIO
import os
import json
from collections import OrderedDict

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
def tlm(tiers, songs):
    tiers = OrderedDict((key, tiers[key]) for key in tier_order if key in tiers)
    with open(songs, "r") as f:
        songs_list = json.load(f)
    width = 1300
    rows = 0
    for tier in tiers:
        rows += 1 if math.ceil(len(tiers[tier])/7) == 0 else math.ceil(len(tiers[tier])/7)
        print(f"{tier} has {rows} rows")
    height = rows*150
    tierlistimage = Image.new("RGB",(width,height), (36, 45, 51))
    draw = ImageDraw.Draw(tierlistimage)
    lowerbound, upperbound = 0,0
    font = ImageFont.truetype("DejaVuSans-Bold.ttf", size=40)
    row, column = 0, 0 
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
            print(f"{song} being downloaded")
            url = songs_list[song]["link"]
            print(f"downloaded {url} for {song}")
            response = requests.get(url)
            icon = Image.open(BytesIO(response.content)).convert("RGBA")
            icon = icon.resize((150, 150))
            tierlistimage.paste(icon, ((column*150)+250, row*150), mask=icon)
            if column == 6:
                column = 0
                row+=1
            else:
                column += 1
        column = 0
        row +=1
    return tierlistimage
