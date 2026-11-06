import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587
BOOK_PATH = "pyq_images/books/Maths/Cengage/Cengage_Trigonometry_G_Tewani"

def send_samples(section, limit=3):
    files = glob.glob(f"{BOOK_PATH}/{section}/*.png")
    if not files:
        print(f"❌ No {section} images found.")
        return
    
    # Sort to get a good variety
    files.sort()
    print(f"Found {len(files)} {section} images. Sending {limit} samples...")
    
    for f in files[:limit]:
        try:
            caption = f"📸 <b>{section.upper()} Sample</b>\nFile: {os.path.basename(f)}"
            bot.send_photo(ADMIN_ID, open(f, "rb"), caption=caption, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to send {f}: {e}")

# Send samples from Theory, Illustration, and Exercise
send_samples("theory")
send_samples("illustration")
send_samples("exercise")

print("Check Telegram!")
