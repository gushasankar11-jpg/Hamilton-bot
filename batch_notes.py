import os, re, base64, requests, time, glob
from fpdf import FPDF
import ai_client
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

PROMPT = """
You are an expert JEE professor and typesetter.
Analyze this image of handwritten short notes. Transcribe it into a highly structured HTML document.

RULES:
1. Use simple LaTeX for math (e.g., \\( m = \\tan \\theta \\)). Do not use complex packages.
2. Use strict bullet points for formulas and conditions.
3. For diagrams, do NOT draw. Insert a text description: [FIGURE: Describe the diagram in 10 words]
4. Organize into sections (e.g., "1. Slope", "2. Forms of Lines").
5. Output ONLY valid HTML body tags (using <h1>, <h2>, <ul>, <li>, <p>). No markdown blocks like ```html.
"""

def clean_math_for_pdf(text):
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\frac{", "").replace("}{", "/").replace("}", "")
    text = text.replace("\\sqrt{", "√(").replace("\\tan", "tan").replace("\\theta", "θ")
    text = text.replace("\\infty", "∞").replace("\\leq", "≤").replace("\\geq", "≥")
    text = text.replace("\\cdot", "·").replace("\\left|", "|").replace("\\right|", "|")
    text = text.replace("\\alpha", "α").replace("\\beta", "β").replace("\\pi", "π")
    text = re.sub(r'\^(\d+)', r'^\1', text)
    return text

class NotePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Hamilton - Typed Short Notes', align='C')
        self.ln(10)

def add_html_to_pdf(pdf, html_content):
    lines = html_content.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        clean_line = clean_math_for_pdf(line)
        clean_line = re.sub(r'<[^>]+>', '', clean_line)
        
        if "<h1>" in line:
            pdf.set_font('Helvetica', 'B', 16)
            pdf.multi_cell(0, 8, clean_line)
            pdf.ln(4)
        elif "<h2>" in line:
            pdf.set_font('Helvetica', 'B', 14)
            pdf.multi_cell(0, 6, clean_line)
            pdf.ln(2)
        elif "<li>" in line:
            pdf.set_font('Helvetica', '', 11)
            pdf.multi_cell(0, 6, "• " + clean_line)
        elif "[FIGURE:" in line:
            pdf.set_font('Helvetica', 'I', 10)
            pdf.set_text_color(100, 100, 100)
            pdf.multi_cell(0, 6, clean_line)
            pdf.set_text_color(0, 0, 0)
        else:
            pdf.set_font('Helvetica', '', 11)
            pdf.multi_cell(0, 6, clean_line)

def main():
    print("🔍 Searching for IMG-20261102-WA0018 to WA0033...")
    
    search_dir = os.path.expanduser("~/storage/shared")
    found_images = []
    
    # Exact filter for the 16 images
    for root, dirs, files in os.walk(search_dir):
        for f in files:
            if f.startswith("IMG-20261102-WA00") and f.endswith(".jpg"):
                # Extract the number part (e.g., "18" from "WA0018")
                num_match = re.search(r'WA00(\d+)', f)
                if num_match:
                    num = int(num_match.group(1))
                    if 18 <= num <= 33:
                        found_images.append(os.path.join(root, f))
                
    found_images = sorted(list(set(found_images)))
    
    if not found_images:
        print("❌ Could not find any images between WA0018 and WA0033.")
        return
        
    print(f"✅ Found exactly {len(found_images)} images! Starting extraction...")

    pdf = NotePDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    if not gemini_keys:
        print("❌ No Gemini keys found.")
        return
        
    key = gemini_keys[0]
    
    # Latest Powerful Models
    models = ["gemini-3.1-flash-lite", "gemini-2.5-flash"]
    
    for i, img_path in enumerate(found_images, 1):
        filename = os.path.basename(img_path)
        print(f"  👁️ Processing [{i}/{len(found_images)}] {filename}...", end="", flush=True)
        
        with open(img_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')
            
        payload = {
            "contents": [{"parts": [{"text": PROMPT}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}],
            "generationConfig": {"temperature": 0.2}
        }
        
        success = False
        for model in models:
            if success: break
            
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            
            try:
                res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
                data = res.json()
                
                if "error" in data:
                    continue # Try the next model
                    
                html_content = data["candidates"][0]["content"]["parts"][0]["text"]
                html_content = re.sub(r'^```html\s*', '', html_content)
                html_content = re.sub(r'```$', '', html_content)
                
                pdf.add_page()
                add_html_to_pdf(pdf, html_content)
                print(f" ✅ Done (using {model}).")
                success = True
            except Exception as e:
                continue
                
        if not success:
            print(f" ❌ All models failed for this image.")
            
        time.sleep(2) # Prevent rate limits

    pdf_filename = "Combined_Handwritten_Notes.pdf"
    pdf.output(pdf_filename)
    print(f"\n📄 PDF Generated successfully: {pdf_filename}")
    
    print("📤 Sending PDF to Telegram...")
    with open(pdf_filename, "rb") as pdf_file:
        bot.send_document(ADMIN_ID, pdf_file, caption=f"📚 Your combined typed notes ({len(found_images)} pages)!")
        
    print("🎉 Check Telegram!")

if __name__ == "__main__":
    main()
