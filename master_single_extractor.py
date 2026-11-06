import os, sys, json, re
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books")
os.makedirs(OUT_DIR, exist_ok=True)

JEE_KEYWORDS = ["EXAMPLE", "EXERCISE", "THEORY", "FORMULA", "SOLUTION", "Q1", "Q2", "LEVEL", "ILLUSTRATION", "CONCEPT", "JEE", "PHYSICS", "CHEMISTRY", "MATHS"]

def classify_block(text):
    t = text.upper()
    if re.search(r'\b(EXERCISE|LEVEL|PROBLEM)\b', t): return "exercise"
    if re.search(r'\b(EXAMPLE|ILLUSTRATION|SOLVED)\b', t): return "illustration"
    if re.search(r'\b(SOLUTION|ANSWER)\b', t): return "solution"
    return "theory"

def process_pdf(pdf_path):
    parts = pdf_path.split("/")
    subj, book_name, pdf = parts[-3], parts[-2], parts[-1]
    book_id = pdf.replace(".pdf", "").replace(" ", "_")[:30]
    out_book_dir = os.path.join(OUT_DIR, subj, book_name, book_id)
    os.makedirs(out_book_dir, exist_ok=True)
    
    db_entries = {"theory": [], "illustration": [], "exercise": [], "solution": []}
    
    print(f"\n📖 STARTING BOOK: {book_id}")
    try:
        # Render pages at 150 DPI
        pages = convert_from_path(pdf_path, dpi=150)
    except Exception as e:
        print(f"❌ Failed to read PDF: {e}")
        return
        
    for page_num, page_img in enumerate(pages, start=1):
        # WE NOW START FROM PAGE 1
        print(f"  👁️ Scanning Page {page_num}/{len(pages)}...", flush=True, end="")
        
        img = np.array(page_img)
        img = cv2.cvtColor(img, cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # 1. Junk Filter: OCR the page to check keywords
        small_img = cv2.resize(gray, (0,0), fx=0.5, fy=0.5)
        page_text = pytesseract.image_to_string(small_img, config='--psm 3').upper()
        
        if not any(kw in page_text for kw in JEE_KEYWORDS):
            print(" ⏭️ [SKIPPED] No JEE content found (Cover/Index/Ad).", flush=True)
            continue
            
        print(" ✅ [JEE CONTENT FOUND] Extracting blocks...", flush=True)
        
        # 2. OpenCV Layout Detection
        thresh = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)[1]
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (40, 15))
        dilated = cv2.dilate(thresh, kernel, iterations=2)
        
        contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        boxes = [cv2.boundingRect(c) for c in contours]
        boxes = sorted(boxes, key=lambda b: (b[1]//50, b[0]))
        
        counter = 1
        for (x, y, w, h) in boxes:
            if w < 100 or h < 30: continue
            
            # Add safety margin (10px) so text is never cut off
            x0 = max(0, x - 10)
            y0 = max(0, y - 10)
            x1 = min(img.shape[1], x + w + 10)
            y1 = min(img.shape[0], y + h + 10)
            
            crop = img[y0:y1, x0:x1]
            
            block_text = pytesseract.image_to_string(crop, config='--psm 6').strip()
            if len(block_text) < 15: continue
            
            sec = classify_block(block_text)
            
            filename = f"{sec}_{counter}_p{page_num}.png"
            filepath = os.path.join(out_book_dir, sec, filename)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            cv2.imwrite(filepath, crop)
            
            db_entries[sec].append({
                "page": page_num,
                "img": filepath,
                "text": block_text[:200]
            })
            
            print(f"    ✂️ Cropped [{sec.upper()}]: {block_text[:40].replace(chr(10), ' ')}...", flush=True)
            counter += 1
            
        # Save DB
        tmp = os.path.join(out_book_dir, "data.json")
        json.dump(db_entries, open(tmp, "w"), indent=2)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_pdf(sys.argv[1])
