import os, glob, random
from bot_chunks.c01 import bot
ADMIN_ID = 8857708587
BASE_DIR = "pyq_images/books"
CATEGORIES = ["theory", "illustration", "exercise", "solution"]
print("📸 Gathering sample images...")
for cat in CATEGORIES:
    files = glob.glob(f"{BASE_DIR}/**/{cat}/*.png", recursive=True)
    if not files:
        print(f"⏭️ No {cat.upper()} images found yet.")
        continue
    print(f"✅ Found {len(files)} {cat.upper()} images. Sending 5 samples...")
    samples = random.sample(files, min(5, len(files)))
    for i, img_path in enumerate(samples, 1):
        try:
            parts = img_path.split("/")
            book_name = parts[-3] if len(parts) >= 3 else "Unknown Book"
            caption = f"<b>Sample {i}/5: {cat.upper()}</b>\n📚 {book_name}\n📄 {os.path.basename(img_path)}"
            bot.send_photo(ADMIN_ID, open(img_path, "rb"), caption=caption, parse_mode="HTML")
        except Exception as e:
            print(f"❌ Failed: {e}")
print("🎉 Done! Check your Telegram.")
