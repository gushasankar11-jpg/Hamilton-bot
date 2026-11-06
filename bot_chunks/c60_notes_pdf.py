import telebot, base64, requests, os, re
from fpdf import FPDF
import ai_client

# The Prompt
PROMPT = """
You are an expert JEE Mathematics professor and typesetter.
Analyze this image of handwritten short notes. Transcribe it into a highly structured HTML document.

RULES:
1. Use LaTeX for all mathematical formulas (e.g., \\( m = \\tan \\theta \\)).
2. Use strict bullet points for conditions and properties.
3. For every diagram, do NOT attempt to draw it. Insert a text description in this format: [FIGURE: Describe the diagram in 10 words or less]
4. Organize the notes into clean sections (e.g., "1. Slope", "2. Forms of Lines").
5. Keep explanations extremely concise.
6. Output ONLY valid HTML (using <h1>, <h2>, <ul>, <li>, <p>). No markdown blocks.

Return the HTML.
"""

def clean_math_for_pdf(text):
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\frac{", "").replace("}{", "/").replace("}", "")
    text = text.replace("\\sqrt{", "√(").replace("\\tan", "tan").replace("\\theta", "θ")
    text = text.replace("\\infty", "∞").replace("\\leq", "≤").replace("\\geq", "≥")
    text = text.replace("\\cdot", "·").replace("\\left|", "|").replace("\\right|", "|")
    text = text.replace("\\alpha", "α").replace("\\beta", "β").replace("\\pi", "π")
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

@bot.message_handler(commands=['notes'])
def handle_notes_command(message):
    bot.reply_to(message, "📸 Please send me the photo of your handwritten notes right now.")

@bot.message_handler(content_types=['photo'])
def handle_notes_photo(message):
    # Only process if the user is replying to the notes prompt or added a specific caption
    # For now, we will just ask them to confirm
    uid = message.chat.id
    msg = bot.reply_to(message, "🧠 Analyzing handwritten notes with Gemini AI... Please wait (this takes 10-15 seconds).")
    
    try:
        # Download the photo
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        
        temp_img = f"temp_notes_{uid}.jpg"
        with open(temp_img, 'wb') as new_file:
            new_file.write(downloaded_file)
            
        with open(temp_img, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode('utf-8')

        gemini_keys = getattr(ai_client, "GEMINI_KEYS", [])
        if not gemini_keys:
            bot.edit_message_text("❌ No Gemini keys found.", chat_id=uid, message_id=msg.message_id)
            return
            
        key = gemini_keys[0]
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
        
        payload = {
            "contents": [{"parts": [{"text": PROMPT}, {"inlineData": {"mimeType": "image/jpeg", "data": img_b64}}]}],
            "generationConfig": {"temperature": 0.2}
        }
        
        res = requests.post(url, headers={"Content-Type": "application/json"}, json=payload, timeout=45)
        data = res.json()
        
        if "error" in data:
            bot.edit_message_text(f"❌ AI Error: {data['error']['message']}", chat_id=uid, message_id=msg.message_id)
            os.remove(temp_img)
            return
            
        html_content = data["candidates"][0]["content"]["parts"][0]["text"]
        html_content = re.sub(r'^```html\s*', '', html_content)
        html_content = re.sub(r'```$', '', html_content)
        
        pdf_filename = f"Short_Notes_{uid}.pdf"
        create_pdf(html_content, pdf_filename)
        
        bot.edit_message_text("✅ PDF Generated! Sending now...", chat_id=uid, message_id=msg.message_id)
        
        with open(pdf_filename, "rb") as pdf_file:
            bot.send_document(uid, pdf_file, caption="📚 Here are your perfectly typed Short Notes!")
            
        os.remove(temp_img)
        os.remove(pdf_filename)
        
    except Exception as e:
        bot.edit_message_text(f"❌ Failed: {e}", chat_id=uid, message_id=msg.message_id)

print("✅ c60_notes_pdf: Handwritten Notes to PDF loaded.")
