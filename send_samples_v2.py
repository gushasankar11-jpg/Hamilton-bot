import os, glob
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

def send_latest_sample(subj, book_name, section, label):
    # Find the newest image in that folder
    pattern = f"pyq_images/books/{subj}/{book_name}/*/{section}/*.png"
    files = glob.glob(pattern)
    if not files:
        print(f"❌ No {section} images found for {book_name}")
        return
    
    # Sort by creation time to get a page further in
    files.sort(key=os.path.getmtime)
    sample = files[-1] if len(files) > 1 else files[0]
    
    try:
        bot.send_photo(ADMIN_ID, open(sample, "rb"), caption=f"📘 {label}\nBook: {book_name}\nPath: {sample}")
        print(f"✅ Sent {label}")
    except Exception as e:
        print(f"Error: {e}")

# Try to send samples from a Cengage book and Black Book
send_latest_sample("Maths", "Cengage_Trigonometry_G_Tewani", "theory", "THEORY Sample")
send_latest_sample("Maths", "Cengage_Trigonometry_G_Tewani", "illustration", "ILLUSTRATION Sample")
send_latest_sample("Maths", "Cengage_Trigonometry_G_Tewani", "exercise", "EXERCISE Sample")
send_latest_sample("Maths", "Cengage_Trigonometry_G_Tewani", "solution", "SOLUTION Sample")

send_latest_sample("Maths", "Advanced_Problem_in_Mathematic", "exercise", "BLACKBOOK EXERCISE Sample")

print("Check Telegram!")
