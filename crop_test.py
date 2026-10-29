import subprocess, re, os, json
from PIL import Image

PDF = "pyq_pdfs/jee_main/practice/Physics/JEE Main Heat and Thermodynamics Previous Year Questions with Answer Key.pdf"
TEST_PAGE = 6
OUT_DIR = "pyq_images/test_crop"
os.makedirs(OUT_DIR, exist_ok=True)

# 1. Render the page to an image at 150 DPI (higher res for math)
img_base = os.path.join(OUT_DIR, "page6")
subprocess.run(["pdftoppm", "-png", "-r", "150", "-f", str(TEST_PAGE), "-l", str(TEST_PAGE), "-singlefile", PDF, img_base], check=True)
img_path = img_base + ".png"
img = Image.open(img_path)
img_w, img_h = img.size
print(f"🖼️ Rendered page {TEST_PAGE} at {img_w}x{img_h} px")

# 2. Extract BBox XML
xml_out = subprocess.run(["pdftotext", "-bbox", "-f", str(TEST_PAGE), "-l", str(TEST_PAGE), PDF, "-"], capture_output=True, text=True).stdout

# 3. Find all Question starts (e.g., "Q17.")
# We use regex to grab the Y-coordinate and the Question Number
pattern = re.compile(r'<word xMin="[\d\.]+" yMin="([\d\.]+)"[^>]*>Q(\d+)\.</word>')
matches = pattern.findall(xml_out)

if not matches:
    print("❌ No questions found on this page. Check if the page is correct.")
    exit()

# Scale factor: PDF is 72 DPI, Image is 150 DPI
scale = 150.0 / 72.0 
questions_found = []

for i, (y_str, q_num) in enumerate(matches):
    y_min = float(y_str) * scale
    # Crop from this question's start, down to the next question (or bottom of page)
    if i + 1 < len(matches):
        y_max = float(matches[i+1][0]) * scale - 15 # 15px padding
    else:
        y_max = img_h - 100 # Leave out the footer
        
    # Add a little padding at the top so it doesn't cut the text
    crop_top = max(0, y_min - 15)
    crop_bottom = min(img_h, y_max)
    
    # Crop and Save
    cropped = img.crop((0, int(crop_top), img_w, int(crop_bottom)))
    out_path = os.path.join(OUT_DIR, f"q{q_num}.png")
    cropped.save(out_path)
    
    questions_found.append({
        "q_num": int(q_num),
        "page": TEST_PAGE,
        "y_top": crop_top,
        "y_bottom": crop_bottom,
        "img_path": out_path
    })
    print(f"✂️ Cropped Q{q_num} -> {out_path}")

# Save blueprint
with open(os.path.join(OUT_DIR, "blueprint.json"), "w") as f:
    json.dump(questions_found, f, indent=2)

print(f"✅ Done! Cropped {len(questions_found)} questions from page {TEST_PAGE}.")
