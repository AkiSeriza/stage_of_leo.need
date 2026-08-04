import os

from PIL import Image, ImageDraw, ImageFont
import re
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(BASE_DIR, "fonts", "arial.ttf")
IMG_SOURCE = r"Databases/Photos/Say"



def draw_text_fit(drawer, area, text, font_path, max_font_size, fill=(0,0,0), min_font_size=8):
    """
    Draw text into rectangular area with automatic line wrapping and font scaling.
    Reduces font size until text fits in rectangle and distributes vertically to fill the area.
    
    Args:
        drawer: PIL ImageDraw object
        area: (x1, y1, x2, y2) bounding box
        text: Text to draw
        font_path: Path to TTF font file
        max_font_size: Starting font size
        fill: Text color
        min_font_size: Minimum allowed font size before giving up
    """
    x1, y1, x2, y2 = area
    max_width = x2 - x1
    max_height = y2 - y1

    def measure_lines(font_size):
        """Helper to measure if text fits at given font size. Returns (fits, lines, y_total)"""
        font = ImageFont.truetype(font_path, font_size)
        lines = []
        line_height = font.getbbox("Hg")[3] - font.getbbox("Hg")[1]
        y_total = 0
        
        for raw_line in text.splitlines():
            tokens = re.findall(r"\S+", raw_line)
            line = ""
            for token in tokens:
                test_line = (line + " " + token) if line else token
                line_width = font.getbbox(test_line)[2] - font.getbbox(test_line)[0]

                if line_width > max_width:
                    if line:
                        lines.append(line)
                        y_total += line_height
                        subtoken = ""
                        subtoken_width = 0
                        for char in token:
                            char_width = font.getbbox(char)[2] - font.getbbox(char)[0]
                            if subtoken_width + char_width > max_width:
                                lines.append(subtoken + "-")
                                y_total += line_height
                                subtoken = char
                                subtoken_width = char_width
                            else:
                                subtoken += char
                                subtoken_width += char_width
                        line = subtoken
                    else:
                        line = token
                else:
                    line = test_line
            if line:
                lines.append(line)
                y_total += line_height
        
        return y_total <= max_height and len(lines) > 0, lines, y_total, line_height
    
    best_font_size = min(max_font_size, 8)
    best_lines = []
    best_y_total = 0
    best_line_height = 0
    

    test_size = min_font_size
    while test_size <= 500:  
        fits, lines, y_total, line_height = measure_lines(test_size)
        
        if fits:
            best_font_size = test_size
            best_lines = lines
            best_y_total = y_total
            best_line_height = line_height
            test_size += 2  
        else:

            if test_size > min_font_size + 2:
                test_size -= 4
                
                while test_size <= 500:
                    fits, lines, y_total, line_height = measure_lines(test_size)
                    if fits:
                        best_font_size = test_size
                        best_lines = lines
                        best_y_total = y_total
                        best_line_height = line_height
                        test_size += 1
                    else:
                        break
            break

    if best_lines:
        font = ImageFont.truetype(font_path, best_font_size)
        line_height = best_line_height
        
        num_lines = len(best_lines)
        remaining_height = max_height - best_y_total
        extra_spacing = remaining_height / max(num_lines - 1, 1) if num_lines > 1 else 0
        
        y = y1
        for l in best_lines:
            drawer.text((x1, y), l, font=font, fill=fill)
            y += line_height + extra_spacing
        return

    font = ImageFont.truetype(font_path, min_font_size)
    line_height = font.getbbox("Hg")[3] - font.getbbox("Hg")[1]
    y = y1
    for l in lines:
        if y + line_height > y2:
            break
        drawer.text((x1, y), l, font=font, fill=fill)
        y += line_height

def generate_say(text, image1):
    base_image = Image.open(f"{IMG_SOURCE}/Base.png").convert("RGBA")
    base_image = base_image.resize((1920, 300))
    image_ = image1.convert("RGBA").resize((750, 750))
    img = Image.new('RGBA', (1920, 1920), color=(255, 255, 255,255))
    img.paste(image_, (585,1200), image_)
    img.paste(base_image, (0, 1000), base_image)
    print(image_)

    print(img)
    draw = ImageDraw.Draw(img)
    draw_text_fit(draw, (0,0, 1920, 1000), text, FONT_PATH, max_font_size=40, fill=(0,0,0))
    from io import BytesIO
    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)
    return buffer