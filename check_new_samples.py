import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

# Find all extracted PNGs, excluding temp files
all_images = []
for root, dirs, files in os.walk("pyq_images/books"):
    for f in files:
        if f.endswith(".png") and not f.startswith("tmp_"):
            all_images.append(os.path.join(root, f))

# Sort by newest first
all_images.sort(key=os.path.getmtime, reverse=True)

print(f"Found {len(all_images)} total images extracted so far.")

if not all_images:
    print("❌ No images found yet. The workers are probably still on the first 15 pages (Preface/Index). Give it 2-3 minutes.")
else:
    sent = 0
    # We want a mix of sections (theory, illustration, exercise)
    seen_sections = set()
    
    for img in all_images:
        if sent >= 6: break
        
        # Get section name from path (e.g., .../exercise/...)
        path_parts = img.split("/")
        if len(path_parts) >= 2:
            section = path_parts[-2]
            book = path_parts[-3]
            
            # Send a max of 2 images per section to show variety
            sec_count = sum(1 for s in seen_sections if s.startswith(section))
            if sec_count >= 2: continue
            
            seen_sections.add(section)
            
            try:
                caption = f"📸 <b>New Extractor Test</b>\n📚 Book: {book}\n📂 Section: <b>{section.upper()}</b>\n📄 File: {os.path.basename(img)}"
                bot.send_photo(ADMIN_ID, open(img, "rb"), caption=caption, parse_mode="HTML")
                print(f"✅ Sent {section} from {book}")
                sent += 1
            except Exception as e:
                print(f"Failed to send {img}: {e}")

print("Check your Telegram!")
