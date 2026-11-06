import os, json, base64, re
import pdfplumber
import requests
import ai_client

BASE = os.getcwd()
OUT_DIR = os.path.join(BASE, "pyq_images", "books", "Vision_Test")
os.makedirs(OUT_DIR, exist_ok=True)

def ask_gemini_vision(img_path, page_num):
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')
        
    prompt = """
    Analyze this textbook page image.
    Identify every individual educational item: "Theory", "Example", or "Exercise".
    Return a JSON object with the exact bounding box for each item.
    
    Format:
    {"items": [
        {"type": "theory", "box": [ymin, xmin, ymax, xmax]}, 
        {"type": "example", "box": [ymin, xmin, ymax, xmax]}
    ]}
    
    IMPORTANT RULES:
    1. The box coordinates must be normalized from 0 to 1000.
    2. "example" must include the header, question, and its solution.
    3. "exercise" must include individual questions separately (if Q1 to Q10, return 10 items).
    4. "theory" is the conceptual text at the top.
    5. DO NOT cut lines in half. Ensure the bounding box covers the full block.
    Return ONLY valid JSON.
    """
    
    # Use Gemini via the ai_client keys
    key = ai_client.GEMINI_KEYS[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
            ]
        }],
        "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"}
    }
    
    # FIX: Use requests instead of curl
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=60)
        data = res.json()
        raw_json = data["candidates"][0]["content"]["parts"][0]["text"]
        # Strip markdown if AI added it
        match = re.search(r'\{.*\}', raw_json, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        return None
    except Exception as e:
        print(f"❌ Vision Error: {e}")
        print(f"Response: {res.text[:200]}")
        return None

def process_page(pdf_path, page_num):
    print(f"🧠 Rendering Page {page_num} for Vision AI...")
    with pdfplumber.open(pdf_path) as pdf:
        page = pdf.pages[page_num - 1]
        # Render page to high-res image
        im = page.to_image(resolution=150).original
        temp_img = "temp_page.jpg"
        im.save(temp_img, "JPEG", quality=90)
        
        w, h = im.size
        
        print("🤖 Asking Gemini Vision for bounding boxes...")
        result = ask_gemini_vision(temp_img, page_num)
        
        if not result or "items" not in result:
            print("❌ AI failed to return boxes.")
            return
            
        print(f"✅ Found {len(result['items'])} items on the page.")
        
        for i, item in enumerate(result["items"]):
            sec = item.get("type", "theory").lower()
            box = item.get("box", [])
            if len(box) != 4: continue
            
            # Convert 0-1000 normalized coords to pixel coords
            ymin, xmin, ymax, xmax = box
            x0 = int((xmin / 1000) * w)
            y0 = int((ymin / 1000) * h)
            x1 = int((xmax / 1000) * w)
            y1 = int((ymax / 1000) * h)
            
            # Add a small safety margin to avoid cutting text
            x0 = max(0, x0 - 10)
            y0 = max(0, y0 - 10)
            x1 = min(w, x1 + 10)
            y1 = min(h, y1 + 10)
            
            # Crop
            crop = im.crop((x0, y0, x1, y1))
            filename = f"{sec}_{i+1}.png"
            filepath = os.path.join(OUT_DIR, filename)
            crop.save(filepath)
            print(f"✂️ Saved {filename} ({sec})")

if __name__ == "__main__":
    pdf_path = os.path.expanduser("~/storage/shared/Hamilton_uploads_abv/books/Maths/Cengage/Cengage Trigonometry G Tewani.pdf")
    process_page(pdf_path, 16)

