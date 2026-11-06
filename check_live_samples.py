import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

def send_recent(subj, book_folder_name, limit=4):
    # Search for the exact book folder
    search_path = f"pyq_images/books/{subj}/*/{book_folder_name}/*/*.png"
    files = glob.glob(search_path)
    if not files:
        print(f"❌ No images yet for {book_folder_name}")
        return
        
    files.sort(key=os.path.getmtime, reverse=True)
    print(f"Found {len(files)} images for {book_folder_name}. Sending newest...")
    
    for f in files[:limit]:
        try:
            section = f.split("/")[-2]  # theory, exercise, illustration
            caption = f"Live Check: {book_folder_name[:20]}\nSection: {section.upper()}\nPage: {os.path.basename(f)}"
            bot.send_photo(ADMIN_ID, open(f, "rb"), caption=caption)
        except Exception as e:
            print(f"Failed to send {f}: {e}")

# Check B.M. Sharma Mechanics
send_recent("Physics", "B.M_Sharma_-_Physics_For_IIT-JEE_2012-2013___Mechanics_-_I-Cengage_(2012)")

# Check Cengage Trigonometry (This one should be Cols: 2)
send_recent("Maths", "Cengage_Trigonometry_G_Tewani")

print("Check Telegram!")
