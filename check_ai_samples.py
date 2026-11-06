import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587
BOOK_PATH = "pyq_images/books/Maths/Cengage/Cengage_Trigonometry_G_Tewani"

def send_samples(section, limit=3):
    files = glob.glob(f"{BOOK_PATH}/{section}/*.png")
    if not files:
        print(f"❌ No {section} images found.")
        return
    
    files.sort()
    print(f"Found {len(files)} {section} images. Sending {limit} samples...")
    
    for f in files[:limit]:
        try:
            caption = f"🤖 <b>AI Extracted: {section.upper()}</b>\nFile: {os.path.basename(f)}"
            bot.send_photo(ADMIN_ID, open(f, "rb"), caption=caption, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to send {f}: {e}")

send_samples("theory")
send_samples("illustration")
send_samples("exercise")

print("Check Telegram!")
