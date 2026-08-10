import asyncio
import os
import cv2
import numpy as np
import pytesseract
import aiosqlite

from database import Database

IMAGE_FOLDER = r"D:\Code\DiscordBots\test_ocr\ss"
DATABASE = r"D:\Code\DiscordBots\test_ocr\database.db"
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
MAX_HASH_DISTANCE = 70
DIFFICULTY_COLORS = {"Easy": (107, 216, 27), "Normal": (95, 184, 233), "Hard": (255, 169, 0), "Expert": (255, 68, 119), "Master": (204, 51, 255)}
_4_3 = {"jacket": (11.713, 1.75, 6.559, 8.75), "score": (21.646, 33.875, 30.266, 7.5), "perfect": (22.958, 55.25, 7.496, 5.25), "great": (23.332, 60.0, 6.934, 5.0), "good": (21.927, 64.75, 8.621, 4.75), "bad": (23.332, 69.0, 6.466, 4.625), "miss": (23.051, 73.625, 6.653, 4.125), "combo": (41.136, 55.125, 12.088, 8.133), "colourpixel": (24.456808, 10.125)}
_2_2_1 = {"jacket": (18.5, 2.525, 5.417, 11.181), "score": (26.75, 29.035, 25.417, 8.476), "perfect": (27.583, 57.349, 6.417, 6.673), "great": (27.5, 63.12, 6.583, 6.853), "good": (28.0, 69.612, 5.833, 6.132), "bad": (27.75, 75.924, 5.917, 5.591), "miss": (27.333, 82.056, 7.0, 5.41), "combo": (43.083, 56.627, 8.833, 9.558), "colourpixel": (28.0, 13.164957)}
_16_10 = {"jacket": (11.833, 2.133, 6.25, 10.267), "score": (22.083, 30.4, 30.333, 8.533), "perfect": (23.083, 56.8, 7.25, 5.867), "great": (23.333, 62.133, 9.25, 5.6), "good": (22.75, 66.933, 8.583, 7.067), "bad": (21.583, 71.867, 9.333, 7.333), "miss": (23.083, 78.133, 7.0, 6.0), "combo": (41.75, 56.0, 10.583, 8.133), "colourpixel": (24.666667, 11.866667)}

SONG_HASHES = {}

async def connect_database(path=DATABASE):
    conn = await aiosqlite.connect(path)
    await conn.execute("PRAGMA foreign_keys = ON")
    return Database(conn)

def phash(image):
    if image is None or image.size == 0: return None
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, (64, 64), interpolation=cv2.INTER_AREA)
    dct = cv2.dct(np.float32(gray))
    low = dct[:16, :16]
    median = np.median(low[1:, 1:])
    return low > median

def string_to_hash(value):
    if not value or len(value) != 256: return None
    try: return np.array([c == "1" for c in value], dtype=bool).reshape(16, 16)
    except Exception: return None

async def load_hashes(db):
    rows = await db.fetchall("""SELECT "song id", "hash" FROM songdata WHERE "hash" IS NOT NULL AND "hash" != ''""")
    hashes = {}
    for song_id, hash_string in rows:
        parsed_hash = string_to_hash(hash_string)
        if parsed_hash is None:
            print(f"WARNING: Invalid hash for song ID {song_id}")
            continue
        hashes[int(song_id)] = parsed_hash
    print(f"Loaded {len(hashes)} jacket hashes.")
    return hashes

async def ensure_song_hashes(db=None):
    global SONG_HASHES
    if SONG_HASHES:
        return SONG_HASHES
    if db is None:
        db = await connect_database()
    SONG_HASHES = await load_hashes(db)
    return SONG_HASHES

async def match_jacket(jacket, db=None):
    if jacket is None or jacket.size == 0: return "0", None
    query_hash = phash(jacket)
    if query_hash is None: return "Error", None
    hashes = await ensure_song_hashes(db)
    best_song_id, best_distance = None, float("inf")
    for song_id, stored_hash in hashes.items():
        distance = np.count_nonzero(query_hash != stored_hash)
        if distance < best_distance:
            best_distance, best_song_id = distance, song_id
    if best_song_id is None: return 0, None
    print(f"Jacket match: {best_song_id} (distance {best_distance})")
    if best_distance > MAX_HASH_DISTANCE: return 0, best_distance
    return best_song_id, best_distance

def match_closest(rgb, colors, max_distance=80):
    if not colors: return None
    r, g, b = rgb
    best_name, best_distance = None, float("inf")
    for name, (cr, cg, cb) in colors.items():
        distance = (r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2
        if distance < best_distance:
            best_distance, best_name = distance, name
    return "Append" if best_distance > max_distance ** 2 else best_name

def get_regions(image):
    H, W = image.shape[:2]
    ratio = W / H
    layouts = {"4:3": (4 / 3, _4_3), "2.2:1": (2.2, _2_2_1), "16:10": (16 / 10, _16_10)}
    closest_name, (closest_ratio, regions) = min(layouts.items(), key=lambda item: abs(ratio - item[1][0]))
    print(f"Image ratio: {ratio:.4f} | Selected: {closest_name} | Difference: {abs(ratio - closest_ratio):.4f}")
    return closest_name, regions

def crop_region(image, region):
    H, W = image.shape[:2]; x, y, w, h = region
    x = max(0, min(int(W * x / 100), W)); y = max(0, min(int(H * y / 100), H))
    w = max(0, min(int(W * w / 100), W - x)); h = max(0, min(int(H * h / 100), H - y))
    return image[y:y+h, x:x+w]

async def read_image(path, db:Database=None):
    img = cv2.imread(path)
    if img is None:
        print(f"Could not read: {path}")
        return None
    layout, regions = get_regions(img)
    print(f"\n{'=' * 60}\n{os.path.basename(path)}\nLayout: {layout}\n{'=' * 60}")
    result = {}
    for name, region in regions.items():
        if name == "jacket":
            jacket = crop_region(img, region)
            song_id, distance = await match_jacket(jacket, db)
            row = await db.fetchone('SELECT "song name" FROM "songdata" WHERE "song id" = ?', (song_id,)) if song_id != 0 else None
            song_title = row[0] if row is not None else "Unknown Song"
            result["song_title"] = song_title
            result["song_id"], result["jacket_distance"] = song_id, distance
            print(f"{'song_id':12} -> {song_id}")
            print(f"{'hash dist':12} -> {distance}")
            continue
        if name == "colourpixel":
            H, W = img.shape[:2]; px, py = region
            x = int(W * px / 100); y = int(H * py / 100)
            if 0 <= x < W and 0 <= y < H:
                b, g, r = img[y, x]; rgb = (int(r), int(g), int(b))
                difficulty = match_closest(rgb, DIFFICULTY_COLORS)
                result["colourpixel"], result["difficulty"] = rgb, difficulty
                print(f"{'colourpixel':12} -> RGB {rgb} at ({x}, {y})"); print(f"{'difficulty':12} -> {difficulty}")
            else:
                print(f"{'colourpixel':12} -> INVALID POSITION ({x}, {y})")
                result["colourpixel"], result["difficulty"] = None, "Append"
            continue
        crop = crop_region(img, region)
        if crop is None or crop.size == 0:
            result[name] = ""
            print(f"{name:12} -> [EMPTY]")
            continue
        text = pytesseract.image_to_string(crop, config="--psm 7", lang="jpn+eng").strip()
        result[name] = text
        print(f"{name:12} -> {text}")
    print("Finished processing")
    return result

async def process_image(imagefile, db:Database=None):
    print("Req recieved")
    return await read_image(imagefile, db)

def process_image_sync(imagefile, db:Database=None):
    return asyncio.run(process_image(imagefile, db))
