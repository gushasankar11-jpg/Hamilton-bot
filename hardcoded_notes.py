import os
from fpdf import FPDF
import telebot

# Initialize the bot (using your token from c01.py)
from bot_chunks.c01 import bot
ADMIN_ID = 8857708587

class NotePDF(FPDF):
    def header(self):
        self.set_font('Helvetica', 'B', 12)
        self.cell(0, 10, 'Hamilton - JEE Short Notes (Typed)', align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('Helvetica', 'I', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def add_title(self, text):
        self.set_font('Helvetica', 'B', 16)
        self.multi_cell(0, 8, text)
        self.ln(4)

    def add_heading(self, text):
        self.set_font('Helvetica', 'B', 14)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_point(self, text):
        self.set_font('Helvetica', '', 11)
        self.multi_cell(0, 6, "• " + text)
        self.ln(1)

    def add_formula(self, text):
        self.set_font('Courier', 'B', 11)
        self.multi_cell(0, 6, "   " + text)
        self.ln(1)

    def add_figure(self, text):
        self.set_font('Helvetica', 'I', 10)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 6, "   [FIGURE: " + text + "]")
        self.set_text_color(0, 0, 0)
        self.ln(2)

def create_notes():
    pdf = NotePDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- PAGE 1: STRAIGHT LINES ---
    pdf.add_page()
    pdf.add_title("STRAIGHT LINES")
    
    pdf.add_heading("1. Slope of a Line")
    pdf.add_point("Slope m = tan(θ), where 0 ≤ θ ≤ 180°")
    pdf.add_point("Slope of x-axis (horizontal line) m = 0")
    pdf.add_point("Slope of y-axis (vertical line) m = ∞ (undefined)")
    pdf.add_point("Angle between two lines:")
    pdf.add_formula("tan(θ) = |(m1 - m2) / (1 + m1*m2)|")
    pdf.add_point("Condition for Parallel lines: m1 = m2")
    pdf.add_point("Condition for Perpendicular lines: m1 * m2 = -1")
    pdf.add_figure("A line passing through origin making angle θ with x-axis")

    pdf.add_heading("2. Different Forms of Lines")
    pdf.add_point("Slope-intercept form: y = mx + c")
    pdf.add_point("x-intercept form: y = m(x - a)")
    pdf.add_point("One-point form: (y - y1) = m(x - x1)")
    pdf.add_point("Two-point form: (y - y1) = [(y2 - y1)/(x2 - x1)] * (x - x1)")
    pdf.add_point("Intercept form: x/a + y/b = 1")
    pdf.add_point("Normal form: x*cos(α) + y*sin(α) = p")
    pdf.add_figure("A line intersecting x-axis at 'a' and y-axis at 'b'")

    # --- PAGE 2: PARAMETRIC FORMS & GENERAL EQUATION ---
    pdf.add_page()
    pdf.add_title("PARAMETRIC & GENERAL FORMS")
    
    pdf.add_heading("3. Parametric Equations")
    pdf.add_point("Symmetric form: (x - x1)/cos(θ) = (y - y1)/sin(θ) = r")
    pdf.add_point("Parametric equations: x = x1 + r*cos(θ), y = y1 + r*sin(θ)")
    
    pdf.add_heading("4. Parametric Equations of Conics")
    pdf.add_point("Circle: x = h + r*cos(θ), y = k + r*sin(θ)")
    pdf.add_point("Parabola (y² = 4ax): x = a*t², y = 2a*t")
    pdf.add_point("Ellipse (x²/a² + y²/b² = 1): x = a*cos(θ), y = b*sin(θ)")
    pdf.add_point("Hyperbola (x²/a² - y²/b² = 1): x = a*sec(θ), y = b*tan(θ)")

    pdf.add_heading("5. General Form of Line")
    pdf.add_point("Equation: ax + by + c = 0")
    pdf.add_point("Slope m = -a/b")
    pdf.add_point("x-intercept = -c/a, y-intercept = -c/b")
    pdf.add_formula("cos(θ) = (a1*a2 + b1*b2) / (√(a1²+b1²) * √(a2²+b2²))")
    pdf.add_point("Condition for perpendicularity: a1*a2 + b1*b2 = 0")
    pdf.add_point("Condition for parallelism: a1/a2 = b1/b2")

    # --- PAGE 3: DISTANCE & ANGLES ---
    pdf.add_page()
    pdf.add_title("DISTANCE, ANGLES & BISECTORS")
    
    pdf.add_heading("6. Distance Formulas")
    pdf.add_point("Distance from point P(x1, y1) to line ax + by + c = 0:")
    pdf.add_formula("d = |ax1 + by1 + c| / √(a² + b²)")
    pdf.add_point("Distance between parallel lines ax + by + c1 = 0 and ax + by + c2 = 0:")
    pdf.add_formula("d = |c1 - c2| / √(a² + b²)")
    pdf.add_point("Foot of perpendicular and Image:")
    pdf.add_formula("(h - x1)/a = (k - y1)/b = -(ax1 + by1 + c) / (a² + b²)")
    
    pdf.add_heading("7. Angular Bisectors")
    pdf.add_point("Equation of bisector of angle between L1 and L2:")
    pdf.add_formula("(a1x + b1y + c1) / √(a1² + b1²) = ± (a2x + b2y + c2) / √(a2² + b2²)")
    pdf.add_figure("Two intersecting lines with acute and obtuse angle bisectors")

    # --- PAGE 4: CONICS - CIRCLE ---
    pdf.add_page()
    pdf.add_title("CONICS - CIRCLE")
    
    pdf.add_heading("1. Standard Equation")
    pdf.add_point("Standard form: x² + y² + 2gx + 2fy + c = 0")
    pdf.add_point("Centre = (-g, -f), Radius = √(g² + f² - c)")
    pdf.add_point("Power of a point P(x1, y1): S1 = x1² + y1² + 2gx1 + 2fy1 + c")
    pdf.add_point("If S1 > 0, point is outside. If S1 < 0, point is inside.")
    
    pdf.add_heading("2. Tangents & Normals")
    pdf.add_point("Tangent at (x1, y1) to x² + y² = a²: xx1 + yy1 = a²")
    pdf.add_point("Condition for line y = mx + c to touch circle: c² = a²(1 + m²)")
    pdf.add_point("Length of tangent from P(x1, y1): √S1")
    pdf.add_figure("A circle with a tangent line, radius, and point of contact")

    # --- PAGE 5: CONICS - PARABOLA ---
    pdf.add_page()
    pdf.add_title("CONICS - PARABOLA")
    
    pdf.add_heading("1. Standard Equation")
    pdf.add_point("Equation: y² = 4ax (a > 0)")
    pdf.add_point("Vertex = (0,0), Focus = (a,0), Directrix = x = -a")
    pdf.add_point("Length of Latus Rectum = 4a")
    pdf.add_point("Parametric point: P(t) = (at², 2at)")
    
    pdf.add_heading("2. Tangents & Normals")
    pdf.add_point("Tangent at P(t): t*y = x + a*t²")
    pdf.add_point("Normal at P(t): y = m*x - 2am - am³ (where m = -t)")
    pdf.add_point("Condition for y = mx + c to touch: c = a/m")
    pdf.add_point("Condition for y = mx + c to be normal: c = -2am - am³")
    pdf.add_figure("A parabola opening rightwards with focus, directrix, and latus rectum")

    # --- PAGE 6: CONICS - ELLIPSE & HYPERBOLA ---
    pdf.add_page()
    pdf.add_title("CONICS - ELLIPSE & HYPERBOLA")
    
    pdf.add_heading("1. Ellipse (x²/a² + y²/b² = 1, a > b)")
    pdf.add_point("Eccentricity: e = √(1 - b²/a²) (e < 1)")
    pdf.add_point("Foci = (±ae, 0), Directrix = x = ±a/e")
    pdf.add_point("Latus Rectum = 2b²/a")
    
    pdf.add_heading("2. Hyperbola (x²/a² - y²/b² = 1)")
    pdf.add_point("Eccentricity: e = √(1 + b²/a²) (e > 1)")
    pdf.add_point("Foci = (±ae, 0), Directrix = x = ±a/e")
    pdf.add_point("Latus Rectum = 2b²/a")
    pdf.add_point("Asymptotes: y = ±(b/a)x")
    pdf.add_figure("An ellipse with major/minor axes and a hyperbola with asymptotes")

    # --- PAGE 7: TRIGONOMETRY ---
    pdf.add_page()
    pdf.add_title("TRIGONOMETRY - FORMULAS")
    
    pdf.add_heading("1. Fundamental Identities")
    pdf.add_point("sin²(θ) + cos²(θ) = 1")
    pdf.add_point("1 + tan²(θ) = sec²(θ)")
    pdf.add_point("1 + cot²(θ) = cosec²(θ)")
    
    pdf.add_heading("2. Compound Angles")
    pdf.add_point("sin(A + B) = sinA*cosB + cosA*sinB")
    pdf.add_point("sin(A - B) = sinA*cosB - cosA*sinB")
    pdf.add_point("cos(A + B) = cosA*cosB - sinA*sinB")
    pdf.add_point("cos(A - B) = cosA*cosB + sinA*sinB")
    pdf.add_point("tan(A + B) = (tanA + tanB) / (1 - tanA*tanB)")
    pdf.add_point("tan(A - B) = (tanA - tanB) / (1 + tanA*tanB)")
    
    pdf.add_heading("3. Transformation Formulas")
    pdf.add_point("sinC + sinD = 2*sin((C+D)/2)*cos((C-D)/2)")
    pdf.add_point("sinC - sinD = 2*cos((C+D)/2)*sin((C-D)/2)")
    pdf.add_point("cosC + cosD = 2*cos((C+D)/2)*cos((C-D)/2)")
    pdf.add_point("cosC - cosD = -2*sin((C+D)/2)*sin((C-D)/2)")

    # --- PAGE 8: INVERSE TRIGONOMETRY ---
    pdf.add_page()
    pdf.add_title("INVERSE TRIGONOMETRY")
    
    pdf.add_heading("1. Domain & Range")
    pdf.add_point("sin⁻¹(x): Domain = [-1, 1], Range = [-π/2, π/2]")
    pdf.add_point("cos⁻¹(x): Domain = [-1, 1], Range = [0, π]")
    pdf.add_point("tan⁻¹(x): Domain = R, Range = (-π/2, π/2)")
    pdf.add_point("cot⁻¹(x): Domain = R, Range = (0, π)")
    pdf.add_point("sec⁻¹(x): Domain = R - (-1, 1), Range = [0, π] - {π/2}")
    pdf.add_point("cosec⁻¹(x): Domain = R - (-1, 1), Range = [-π/2, π/2] - {0}")
    
    pdf.add_heading("2. Important Identities")
    pdf.add_point("sin⁻¹(x) + cos⁻¹(x) = π/2")
    pdf.add_point("tan⁻¹(x) + cot⁻¹(x) = π/2")
    pdf.add_point("sec⁻¹(x) + cosec⁻¹(x) = π/2")
    pdf.add_point("tan⁻¹(x) + tan⁻¹(y) = tan⁻¹((x + y) / (1 - xy))")

    # Save PDF
    pdf_filename = "JEE_Short_Notes_Hardcoded.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

if __name__ == "__main__":
    print("📄 Generating PDF...")
    file = create_notes()
    print(f"✅ PDF Generated: {file}")
    
    print("📤 Sending to Telegram...")
    try:
        with open(file, "rb") as f:
            bot.send_document(ADMIN_ID, f, caption="📚 <b>Your JEE Short Notes</b>\nAll formulas and concepts typed out perfectly.", parse_mode="HTML")
        print("🎉 Sent successfully! Check your Telegram.")
    except Exception as e:
        print(f"❌ Failed to send: {e}")
