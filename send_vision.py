import os, glob
from bot_chunks.c01 import bot
ADMIN_ID = 8857708587

files = glob.glob("pyq_images/books/Vision_Test/*.png")
if not files:
    print("❌ No images found.")
else:
    for f in sorted(files):
        sec = f.split("/")[-1].split("_")[0].upper()
        bot.send_photo(ADMIN_ID, open(f, "rb"), caption=f"👁️ <b>Vision AI Test</b>\nType: {sec}", parse_mode="HTML")
    print(f"✅ Sent {len(files)} images to Telegram!")
