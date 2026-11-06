import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

# Find ALL png images recursively, sort by newest first
all_images = []
for root, dirs, files in os.walk("pyq_images/books"):
    for f in files:
        if f.endswith(".png"):
            all_images.append(os.path.join(root, f))

# Sort by time (newest first)
all_images.sort(key=os.path.getmtime, reverse=True)

print(f"Found {len(all_images)} total images extracted so far.")

if not all_images:
    print("❌ Still 0 images. The books might still be on the first 15 pages (Index/Preface) or processing.")
else:
    # Send the top 5 newest images
    sent = 0
    for img in all_images:
        if sent >= 5: break
        try:
            # Determine section from path
            sec = "UNKNOWN"
            if "/theory/" in img: sec = "THEORY"
            elif "/illustration/" in img: sec = "ILLUSTRATION"
            elif "/exercise/" in img: sec = "EXERCISE"
            elif "/solution/" in img: sec = "SOLUTION"
            
            # Get book name (parent folder)
            book = img.split("/")[-3]
            
            caption = f"📸 Latest Sample: <b>{sec}</b>\n📚 Book: {book}\n📄 File: {os.path.basename(img)}"
            bot.send_photo(ADMIN_ID, open(img, "rb"), caption=caption, parse_mode="HTML")
            print(f"✅ Sent {sec} image from {book}")
            sent += 1
        except Exception as e:
            print(f"Failed to send {img}: {e}")

print("Check your Telegram!")
