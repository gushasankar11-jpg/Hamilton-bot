import os, sys, json, re, base64, requests
from fpdf import FPDF
import ai_client
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

PROMPT = """
You are an expert JEE Mathematics professor and typesetter.
Analyze this image of handwritten short notes. Your task is to transcribe it into a highly structured, beautifully formatted HTML document.

RULES:
1. Use LaTeX for all mathematical formulas (e.g., \\( m = \\tan \\theta \\)).
2. Use strict bullet points for conditions and properties.
3. For every diagram, do NOT attempt to draw it. Instead, insert a clear text description in this format: 
   [FIGURE: Describe the diagram in 10 words or less, mentioning the axes, curves, and labels]
4. Organize the notes into clean sections (e.g., "1. Slope", "2. Forms of Lines", "3. Distance").
5. Keep the explanations extremely concise (1 line max per point).
6. Output ONLY valid HTML (using <h1>, <h2>, <ul>, <li>, <p>). No markdown blocks like ```html.

Return the HTML.
"""

def clean_math_for_pdf(text):
    """Converts basic LaTeX to Unicode for fpdf"""
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\frac{", "").replace("}{", "/").replace("}", "")
    text = text.replace("\\sqrt{", "√(").replace("\\tan", "tan").replace("\\theta", "θ")
    text = text.replace("\\infty", "∞").replace("\\leq", "≤").replace("\\geq", "≥")
    text = text.replace("\\cdot", "·").replace("\\left|", "|").replace("\\right|", "|")
    text = text.replace("\\alpha", "α").replace("\\beta", "β").replace("\\pi", "π")
    text = re.sub(r'\^(\d+)', r'^\1', text) # Keep superscripts simple
    return text

class NotePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 14)
        self.cell(0, 10, 'Hamilton - JEE Short Notes', align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

def create_pdf(html_content, filename="JEE_Short_Notes.pdf"):
    pdf = NotePDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    lines = html_content.split('\n')
    for line in lines:
        line = line.strip()
        if not line: continue
        
        clean_line = clean_math_for_pdf(line)
        clean_line = re.sub(r'<[^>]+>', '', clean_line) # Remove HTML tags
        
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
    return filename

def process_image_and_send(image_path):
    if not os.path.exists(image_path):
        print(f"❌ Image not found: {image_path}")
        return

    print("👁️ Sending image to AI for OCR and formatting...")
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode('utf-8')

    gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
    if not gemini_keys:
        print("❌ No Gemini keys found.")
        return

    key = gemini_keys[0]
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [{"parts": [{"text": PROMPT}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}],
        "generationConfig": {"temperature": 0.2}
    }

    try:
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=40)
        data = res.json()
        if "error" in data:
            print(f"❌ AI Error: {data['error']['message']}")
            return
            
        html_content = data["candidates"][0]["content"]["parts"][0]["text"]
        
        # Clean up markdown if AI added it
        html_content = re.sub(r'^```html\s*', '', html_content)
        html_content = re.sub(r'```$', '', html_content)
        
        print("✅ AI Formatting Complete. Generating PDF...")
        pdf_filename = create_pdf(html_content)
        
        print("📤 Sending PDF to Telegram...")
        with open(pdf_filename, "rb") as pdf_file:
            bot.send_document(ADMIN_ID, pdf_file, caption="📚 Here are your typed and formatted Short Notes!")
            
        print("🎉 Done! Check Telegram.")
        
    except Exception as e:
        print(f"❌ Failed: {e}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        process_image_and_send(sys.argv[1])
    else:
        print("Usage: python3 auto_notes_generator.py <path_to_image.jpg>")
