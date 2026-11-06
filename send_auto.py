import os, glob
from bot_chunks.c01 import bot
ADMIN_ID = 8857708587

files = glob.glob("pyq_images/books/Maths/Cengage/Cengage_Trigonometry_G_Tewani/*/*.png")
if not files:
    print("❌ No images generated.")
else:
    files.sort()
    for f in files:
        sec = f.split("/")[-2].upper()
        caption = f"🧪 <b>10-Page Test: {sec}</b>\n📄 {os.path.basename(f)}"
        bot.send_photo(ADMIN_ID, open(f, "rb"), caption=caption, parse_mode="HTML")
    print(f"✅ Sent {len(files)} images to Telegram!")
