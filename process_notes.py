import os, sys, re, base64, requests
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
5. Output ONLY valid HTML (using <h1>, <h2>, <ul>, <li>, <p>). No markdown blocks.
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
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Hamilton - JEE Short Notes', align='C')
        self.ln(10)

def create_pdf(html_content, filename):
    pdf = NotePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
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
            pdf.set_font('Helvetica', 'B', 13)
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

    pdf.output(filename)

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("❌ Usage: python3 process_notes.py <image_name.jpg>")
        sys.exit(1)
        
    img_path = sys.argv[1]
    if not os.path.exists(img_path):
        print(f"❌ File not found: {img_path}")
        sys.exit(1)

    print("👁️ Sending image to AI (Gemini) for OCR...")
    
    with open(img_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    if not gemini_keys:
        print("❌ No Gemini keys found.")
        sys.exit(1)
        
    key = gemini_keys[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    
    payload = {
        "contents": [{"parts": [{"text": PROMPT}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}],
        "generationConfig": {"temperature": 0.2}
    }
    
    try:
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=60)
        data = res.json()
        
        if "error" in data:
            print(f"❌ AI Error: {data['error']['message']}")
            sys.exit(1)
            
        html_content = data["candidates"][0]["content"]["parts"][0]["text"]
        html_content = re.sub(r'^```html\s*', '', html_content)
        html_content = re.sub(r'```$', '', html_content)
        
        print("✅ AI Extraction Complete. Generating PDF...")
        pdf_filename = "Handwritten_Notes_Converted.pdf"
        create_pdf(html_content, pdf_filename)
        
        print("📤 Sending PDF to Telegram...")
        with open(pdf_filename, "rb") as pdf_file:
            bot.send_document(ADMIN_ID, pdf_file, caption="📚 Here are your perfectly typed Short Notes!")
            
        print("🎉 Done! Check Telegram.")
        
    except Exception as e:
        print(f"❌ Failed: {e}")
