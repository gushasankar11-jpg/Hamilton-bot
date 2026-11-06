import ast

path = "bot_chunks/c50_planner.py"
content = open(path).read()

# 1. Add a robust helper function before handle_planner_pdf
helper_code = '''
def extract_text_from_pdf(pdf_path):
    import pdfplumber, base64, requests, os
    import ai_client
    
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "\\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
    except: pass

    # If text is too short, it's a scanned PDF. Use Vision AI.
    if len(text.strip()) < 50:
        print("[Planner] Scanned PDF detected. Using Vision AI...")
        try:
            with pdfplumber.open(pdf_path) as pdf:
                img = pdf.pages[0].to_image(resolution=150).original
                img.thumbnail((1024, 1024))
                temp_img = f"temp_pdf_vision.jpg"
                img.save(temp_img, "JPEG")
                with open(temp_img, "rb") as f:
                    img_b64 = base64.b64encode(f.read()).decode()
                os.remove(temp_img)
                
                gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
                if gemini_keys:
                    key = gemini_keys[0]
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.1-flash-lite:generateContent?key={key}"
                    payload = {
                        "contents": [{"parts": [
                            {"text": "Read this image of a schedule. Extract all the timings and days in plain text. Do not explain, just output the schedule."},
                            {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}
                        ]}],
                        "generationConfig": {"temperature": 0.1}
                    }
                    res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=45)
                    data = res.json()
                    if "error" not in data:
                        text = data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            print(f"PDF Vision Error: {e}")
            
    return text

'''

if "def extract_text_from_pdf(pdf_path):" not in content:
    content = content.replace("@bot.message_handler(content_types=['document'])", helper_code + "\n@bot.message_handler(content_types=['document'])")

# 2. Replace the old PDF extraction logic inside handle_planner_pdf
old_logic = '''            with pdfplumber.open(temp_pdf) as pdf:
                text = "\\n".join([p.extract_text() for p in pdf.pages if p.extract_text()])
                
            PLANNER_STATE[uid]["answers"]["schedule_pdf_text"] = text[:2000] # Limit context'''
            
new_logic = '''            text = extract_text_from_pdf(temp_pdf)
                
            PLANNER_STATE[uid]["answers"]["schedule_pdf_text"] = text[:2500] # Limit context'''
            
if old_logic in content:
    content = content.replace(old_logic, new_logic)

try:
    ast.parse(content)
    open(path, "w").write(content)
    print("✅ Planner patched: Now handles both Text & Scanned PDFs.")
except SyntaxError as e:
    print(f"❌ Syntax Error: {e}")
