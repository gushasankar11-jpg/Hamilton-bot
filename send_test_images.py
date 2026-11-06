import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587
BOOK_PATH = "pyq_images/books/Maths/Cengage/Cengage_Trigonometry_G_Tewani"

print("🔍 Looking for test images...")

# Find all images in the book folder
all_images = []
for root, dirs, files in os.walk(BOOK_PATH):
    for f in files:
        if f.endswith(".png"):
            all_images.append(os.path.join(root, f))

if not all_images:
    print("❌ No images found. Did the extraction run successfully?")
else:
    print(f"Found {len(all_images)} test images. Sending to Telegram...")
    # Sort them to keep them organized
    all_images.sort()
    
    for img_path in all_images:
        try:
            section = img_path.split("/")[-2].upper()
            filename = os.path.basename(img_path)
            
            caption = f"🧪 <b>Test Crop: {section}</b>\n📄 File: {filename}"
            bot.send_photo(ADMIN_ID, open(img_path, "rb"), caption=caption, parse_mode="HTML")
            print(f"✅ Sent {filename}")
        except Exception as e:
            print(f"❌ Failed to send {filename}: {e}")

print("Check your Telegram!")
