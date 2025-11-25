import csv
from PIL import Image, ImageDraw, ImageFont
import math
import requests
from io import BytesIO
import json

tier_colors = {
    "S+": (65, 105, 225),  
    "S": (56, 84, 168), 
    "A": (50, 69, 128),   
    "B": (37, 49, 84), 
    "C": (26, 27, 54), 
    "D": (13, 11, 23),  
    }
def tierlistmake(results,songs):
    with open(songs, "r") as f:
        songs_list = json.load(f)
    width = 1300
    rows = 0
    tiers = {
        "S+":[],
        "S":[],
        "A":[],
        "B":[],
        "C":[],
        "D":[],
    }
    with open(results, "r") as f:
        reader = csv.reader(f)
        next(reader)
        for i in reader:
            tiers[i[0]].append(i[1])
    for tier in tiers:
        rows += 1 if math.ceil(len(tiers[tier])/7) == 0 else math.ceil(len(tiers[tier])/7)
    height = rows*150
    tierlistimage = Image.new("RGB",(width,height), (36, 45, 51))
    draw = ImageDraw.Draw(tierlistimage)
    lowerbound, upperbound = 0,0
    font = ImageFont.truetype("arial.ttf", size=30)
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

