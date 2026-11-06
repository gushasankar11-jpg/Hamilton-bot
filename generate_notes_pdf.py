import os
from fpdf import FPDF
import re

# This is a sample of the text the AI will generate. 
# You will paste the AI's actual output here or have the script read it from a file.
SAMPLE_AI_OUTPUT = """
<h1>Straight Lines - Short Notes</h1>
<h2>1. Slope of a Line</h2>
<ul>
<li>Slope \( m = \tan \theta \) (where \( 0 \leq \theta \leq 180^\circ \))</li>
<li>Slope of x-axis is \( m = 0 \). Slope of y-axis is \( m = \infty \) (undefined).</li>
<li>Angle between two lines: \( \tan \theta = \left| \frac{m_1 - m_2}{1 + m_1 m_2} \right| \)</li>
</ul>
<p><b>[FIGURE:</b> A straight line passing through origin making an angle \(\theta\) with positive x-axis<b>]</b></p>

<h2>2. Different Forms of Lines</h2>
<ul>
<li><b>Slope-Intercept:</b> \( y = mx + c \)</li>
<li><b>Point-Slope:</b> \( y - y_1 = m(x - x_1) \)</li>
<li><b>Two-Point:</b> \( y - y_1 = \frac{y_2 - y_1}{x_2 - x_1} (x - x_1) \)</li>
<li><b>Intercept Form:</b> \( \frac{x}{a} + \frac{y}{b} = 1 \)</li>
</ul>
<p><b>[FIGURE:</b> A line intersecting x-axis at 'a' and y-axis at 'b'<b>]</b></p>

<h2>3. Distance & Conditions</h2>
<ul>
<li><b>Distance between two points:</b> \( |PQ| = \sqrt{(x_2-x_1)^2 + (y_2-y_1)^2} \)</li>
<li><b>Distance from origin:</b> \( P = \frac{|c|}{\sqrt{a^2+b^2}} \)</li>
<li><b>Condition for Parallel lines:</b> \( m_1 = m_2 \)</li>
<li><b>Condition for Perpendicular lines:</b> \( m_1 \cdot m_2 = -1 \)</li>
</ul>
"""

def clean_math_for_pdf(text):
    """Converts basic LaTeX to Unicode for fpdf"""
    text = text.replace("\\(", "").replace("\\)", "")
    text = text.replace("\\frac{", "").replace("}{", "/").replace("}", "")
    text = text.replace("\\sqrt{", "√(").replace("\\tan", "tan").replace("\\theta", "θ")
    text = text.replace("\\infty", "∞").replace("\\leq", "≤").replace("\\geq", "≥")
    text = text.replace("\\cdot", "·").replace("\\left|", "|").replace("\\right|", "|")
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
    
    # Simple HTML parser (for demonstration, we just strip tags and apply styles)
    # In production, use html2text or beautifulsoup to parse properly.
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
    print(f"✅ PDF Generated: {filename}")

if __name__ == "__main__":
    create_pdf(SAMPLE_AI_OUTPUT)
