import os, glob
from bot_chunks.c01 import bot
ADMIN_ID = 8857708587

files = glob.glob("pyq_images/books/Maths/Cengage/Cengage_Trigonometry_G_Tewani/*/*.png")
if not files:
    print("❌ No images generated.")
else:
    for f in sorted(files):
        sec = f.split("/")[-2].upper()
        bot.send_photo(ADMIN_ID, open(f, "rb"), caption=f"👁️ <b>Vision AI Test: {sec}</b>\n📄 {os.path.basename(f)}", parse_mode="HTML")
    print(f"✅ Sent {len(files)} images to Telegram!")
