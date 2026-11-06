import os, glob
from bot_chunks.c01 import bot
ADMIN_ID = 8857708587
files = glob.glob("pyq_images/books/Maths/Cengage/Cengage_Trigonometry_G_Tewani/*/*p30*.png")
files.sort()
print(f"Found {len(files)} crops for page 30.")
for f in files[:6]: # Send max 6 to avoid spam
    sec = f.split("/")[-2]
    bot.send_photo(ADMIN_ID, open(f, "rb"), caption=f"Page 30 Crop: {sec.upper()}")
print("Check Telegram!")
