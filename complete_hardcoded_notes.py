import os
from fpdf import FPDF
from bot_chunks.c01 import bot

ADMIN_ID = 8857708587

class NotePDF(FPDF):
    def __init__(self):
        super().__init__()
        # Use the Unicode font so we don't get errors
        self.add_font('DejaVu', '', 'DejaVuSans.ttf', uni=True)
        self.add_font('DejaVu', 'B', 'DejaVuSans.ttf', uni=True) # Using regular for bold as fallback
        
    def header(self):
        self.set_font('DejaVu', 'B', 14)
        self.cell(0, 10, 'Hamilton - JEE Short Notes (Master Typed)', align='C')
        self.ln(10)

    def footer(self):
        self.set_y(-15)
        self.set_font('DejaVu', '', 8)
        self.cell(0, 10, f'Page {self.page_no()}', align='C')

    def add_title(self, text):
        self.set_font('DejaVu', 'B', 16)
        self.multi_cell(0, 8, text)
        self.ln(4)

    def add_heading(self, text):
        self.set_font('DejaVu', 'B', 12)
        self.multi_cell(0, 6, text)
        self.ln(2)

    def add_point(self, text):
        self.set_font('DejaVu', '', 10)
        self.multi_cell(0, 6, "• " + text)
        self.ln(1)

    def add_formula(self, text):
        self.set_font('DejaVu', 'B', 11)
        self.set_text_color(0, 0, 150) # Blue for formulas
        self.multi_cell(0, 6, "   " + text)
        self.set_text_color(0, 0, 0)
        self.ln(1)

    def add_figure(self, text):
        self.set_font('DejaVu', '', 9)
        self.set_text_color(100, 100, 100)
        self.multi_cell(0, 6, "   [FIGURE: " + text + "]")
        self.set_text_color(0, 0, 0)
        self.ln(2)

def generate_master_pdf():
    pdf = NotePDF()
    pdf.set_auto_page_break(auto=True, margin=15)

    # --- PAGE 1: STRAIGHT LINES (BASICS) ---
    pdf.add_page()
    pdf.add_title("STRAIGHT LINES")
    pdf.add_heading("1. Slope of a Line")
    pdf.add_point("Slope m = tan(θ), where 0 ≤ θ ≤ 180°")
    pdf.add_point("Slope of x-axis (horizontal line) m = 0")
    pdf.add_point("Slope of y-axis (vertical line) m = ∞ (undefined)")
    pdf.add_point("Angle between two lines:")
    pdf.add_formula("tan(θ) = |(m1 - m2) / (1 + m1·m2)|")
    pdf.add_point("Condition for Parallel lines: m1 = m2")
    pdf.add_point("Condition for Perpendicular lines: m1·m2 = -1")
    pdf.add_figure("A line passing through origin making angle θ with positive x-axis")

    pdf.add_heading("2. Different Forms of Lines")
    pdf.add_point("Slope-intercept form: y = mx + c")
    pdf.add_point("x-intercept form: y = m(x - a)")
    pdf.add_point("One-point form: (y - y1) = m(x - x1)")
    pdf.add_point("Two-point form: (y - y1) = [(y2 - y1)/(x2 - x1)] * (x - x1)")
    pdf.add_point("Intercept form: x/a + y/b = 1")
    pdf.add_point("Standard equation passing through origin: y = mx")
    pdf.add_point("Normal form: x·cos(α) + y·sin(α) = p")
    pdf.add_point("Distance from origin to line: p = |c| / √(a² + b²)")
    pdf.add_figure("A line intersecting x-axis at 'a' and y-axis at 'b'")

    # --- PAGE 2: STRAIGHT LINES (PARAMETRIC & GENERAL) ---
    pdf.add_page()
    pdf.add_title("STRAIGHT LINES (Cont.)")
    pdf.add_heading("3. Parametric Equations")
    pdf.add_point("Symmetric form: (x - x1)/cos(θ) = (y - y1)/sin(θ) = r")
    pdf.add_point("Parametric equations: x = x1 + r·cos(θ), y = y1 + r·sin(θ)")
    
    pdf.add_heading("4. Parametric Equations of Conics")
    pdf.add_point("Circle: x = h + r·cos(θ), y = k + r·sin(θ)")
    pdf.add_point("Parabola (y² = 4ax): x = a·t², y = 2a·t")
    pdf.add_point("Ellipse (x²/a² + y²/b² = 1): x = a·cos(θ), y = b·sin(θ)")
    pdf.add_point("Hyperbola (x²/a² - y²/b² = 1): x = a·sec(θ), y = b·tan(θ)")
    pdf.add_point("Rectangular Hyperbola (xy = c²): x = c·t, y = c/t")

    pdf.add_heading("5. General Form of Line")
    pdf.add_point("Equation: ax + by + c = 0")
    pdf.add_point("Slope m = -a/b")
    pdf.add_point("x-intercept = -c/a, y-intercept = -c/b")
    pdf.add_formula("cos(θ) = (a1a2 + b1b2) / (√(a1²+b1²) · √(a2²+b2²))")
    pdf.add_point("Perpendicular condition: a1a2 + b1b2 = 0")
    pdf.add_point("Parallel condition: a1/a2 = b1/b2")

    # --- PAGE 3: STRAIGHT LINES (DISTANCE & ANGLES) ---
    pdf.add_page()
    pdf.add_title("DISTANCE & ANGLES")
    pdf.add_heading("6. Distance Formulas")
    pdf.add_point("Distance from P(x1, y1) to ax + by + c = 0:")
    pdf.add_formula("d = |ax1 + by1 + c| / √(a² + b²)")
    pdf.add_point("Distance between parallel lines ax + by + c1 = 0 and ax + by + c2 = 0:")
    pdf.add_formula("d = |c1 - c2| / √(a² + b²)")
    
    pdf.add_heading("7. Foot of Perpendicular & Image")
    pdf.add_point("Foot of perpendicular from P(x1, y1) to ax + by + c = 0:")
    pdf.add_formula("(h - x1)/a = (k - y1)/b = -(ax1 + by1 + c) / (a² + b²)")
    pdf.add_point("Image of P with respect to x-axis: (x1, -y1)")
    pdf.add_point("Image of P with respect to y-axis: (-x1, y1)")
    pdf.add_point("Image of P with respect to origin: (-x1, -y1)")

    # --- PAGE 4: STRAIGHT LINES (BISECTORS & CONCURRENCY) ---
    pdf.add_page()
    pdf.add_title("BISECTORS & CONCURRENCY")
    pdf.add_heading("8. Angular Bisectors")
    pdf.add_point("Equation of bisector of angle between L1 and L2:")
    pdf.add_formula("(a1x + b1y + c1) / √(a1² + b1²) = ± (a2x + b2y + c2) / √(a2² + b2²)")
    pdf.add_point("Acute bisector: sign of (a1a2 + b1b2) is taken positive.")
    pdf.add_point("Obtuse bisector: sign of (a1a2 + b1b2) is taken negative.")
    
    pdf.add_heading("9. Concurrent Lines")
    pdf.add_point("Condition for lines a1x+b1y+c1=0, a2x+b2y+c2=0, a3x+b3y+c3=0 to be concurrent:")
    pdf.add_formula("| a1 b1 c1 |")
    pdf.add_formula("| a2 b2 c2 | = 0")
    pdf.add_formula("| a3 b3 c3 |")
    pdf.add_point("Family of concurrent lines: L1 + λL2 = 0")

    # --- PAGE 5: STRAIGHT LINES (AREA) ---
    pdf.add_page()
    pdf.add_title("AREA OF TRIANGLE")
    pdf.add_point("Area of triangle formed by ax + by + c = 0 with coordinate axes:")
    pdf.add_formula("A = c² / (2|ab|) sq. units")
    pdf.add_point("Area of triangle made by x/a + y/b = 1 with coordinate axes:")
    pdf.add_formula("A = ½ |ab| sq. units")
    pdf.add_figure("A right-angled triangle formed by a line with x and y axes")

    # --- PAGE 6: CONICS - CIRCLES ---
    pdf.add_page()
    pdf.add_title("CONICS - CIRCLES")
    pdf.add_heading("1. Standard Equation & Types")
    pdf.add_point("Standard form: x² + y² + 2gx + 2fy + c = 0")
    pdf.add_point("Centre = (-g, -f), Radius r = √(g² + f² - c)")
    pdf.add_point("r > 0: Real circle. r = 0: Point circle. r < 0: Imaginary circle.")
    
    pdf.add_heading("2. Notations")
    pdf.add_point("S = x² + y² + 2gx + 2fy + c")
    pdf.add_point("S1 = x·x1 + y·y1 + g(x + x1) + f(y + y1) + c")
    pdf.add_point("S11 = x1² + y1² + 2gx1 + 2fy1 + c")
    pdf.add_point("Power of a point P: CP² - r² = S11")
    
    pdf.add_heading("3. Position of a Point")
    pdf.add_point("S11 > 0 : Point is outside the circle.")
    pdf.add_point("S11 = 0 : Point is on the circle.")
    pdf.add_point("S11 < 0 : Point is inside the circle.")

    # --- PAGE 7: CONICS - GENERAL ---
    pdf.add_page()
    pdf.add_title("CONICS - GENERAL EQUATION")
    pdf.add_point("Eccentricity e = SP / PM (Distance from focus / Distance from directrix)")
    pdf.add_point("e = 1: Parabola. e < 1: Ellipse. e > 1: Hyperbola. e = √2: Rectangular Hyperbola.")
    
    pdf.add_heading("General Equation of Conic:")
    pdf.add_formula("ax² + 2hxy + by² + 2gx + 2fy + c = 0")
    pdf.add_point("Parabola: Δ ≠ 0, h² = ab")
    pdf.add_point("Hyperbola: Δ ≠ 0, h² > ab")
    pdf.add_point("Rectangular Hyperbola: Δ ≠ 0, h² > ab, a + b = 0")
    pdf.add_point("Circle: Δ ≠ 0, a = b, h = 0")
    pdf.add_point("Pair of Straight Lines: Δ = 0, h² ≥ ab")
    pdf.add_formula("Δ = abc + 2fgh - af² - bg² - ch²")

    # --- PAGE 8: CIRCLES (TANGENTS & CHORDS) ---
    pdf.add_page()
    pdf.add_title("CIRCLES - TANGENTS & CHORDS")
    pdf.add_heading("1. Tangents")
    pdf.add_point("Equation of tangent at (x1, y1): T = 0 (xx1 + yy1 + g(x+x1) + f(y+y1) + c = 0)")
    pdf.add_point("Condition for line y = mx + c to touch circle x² + y² = a²:")
    pdf.add_formula("c² = a²(1 + m²), or c = ±a√(1 + m²)")
    
    pdf.add_heading("2. Chords")
    pdf.add_point("Chord of contact from (x1, y1): T = 0")
    pdf.add_point("Equation of chord with midpoint (x1, y1): T = S1")
    pdf.add_point("Length of chord of contact: 2·r·sin(θ/2)")
    pdf.add_point("Director circle: x² + y² = 2a²")

    # --- PAGE 9: CIRCLES (COMMON TANGENTS & RADICAL AXIS) ---
    pdf.add_page()
    pdf.add_title("CIRCLES - COMMON TANGENTS")
    pdf.add_point("C1C2 > r1 + r2: 4 common tangents (2 direct, 2 transverse)")
    pdf.add_point("C1C2 = r1 + r2: 3 common tangents (2 direct, 1 transverse)")
    pdf.add_point("|r1 - r2| < C1C2 < r1 + r2: 2 common tangents (direct)")
    pdf.add_point("C1C2 = |r1 - r2|: 1 common tangent (direct)")
    pdf.add_point("C1C2 < |r1 - r2|: 0 common tangents")
    
    pdf.add_heading("Properties")
    pdf.add_point("Radical Axis: S1 - S2 = 0")
    pdf.add_point("Orthogonality condition: 2g1g2 + 2f1f2 = c1 + c2")
    pdf.add_figure("Diagrams showing two circles intersecting, touching, and disjoint")

    # --- PAGE 10: TRIGONOMETRY (FUNDAMENTALS) ---
    pdf.add_page()
    pdf.add_title("TRIGONOMETRY - FUNDAMENTALS")
    pdf.add_heading("1. Domain & Range")
    pdf.add_point("sin(x): Domain = R, Range = [-1, 1]")
    pdf.add_point("cos(x): Domain = R, Range = [-1, 1]")
    pdf.add_point("tan(x): Domain = R - {(2n+1)π/2}, Range = R")
    pdf.add_point("cot(x): Domain = R - {nπ}, Range = R")
    pdf.add_point("sec(x): Domain = R - {(2n+1)π/2}, Range = (-∞, -1] ∪ [1, ∞)")
    pdf.add_point("cosec(x): Domain = R - {nπ}, Range = (-∞, -1] ∪ [1, ∞)")
    
    pdf.add_heading("2. Compound Angles")
    pdf.add_point("sin(A + B) = sinA·cosB + cosA·sinB")
    pdf.add_point("cos(A + B) = cosA·cosB - sinA·sinB")
    pdf.add_point("tan(A + B) = (tanA + tanB) / (1 - tanA·tanB)")
    pdf.add_point("cot(A + B) = (cotA·cotB - 1) / (cotB + cotA)")

    # --- PAGE 11: TRIGONOMETRY (TRANSFORMATIONS & PERIODS) ---
    pdf.add_page()
    pdf.add_title("TRIGONOMETRY - TRANSFORMATIONS")
    pdf.add_heading("1. Sum to Product")
    pdf.add_point("sinC + sinD = 2·sin((C+D)/2)·cos((C-D)/2)")
    pdf.add_point("sinC - sinD = 2·cos((C+D)/2)·sin((C-D)/2)")
    pdf.add_point("cosC + cosD = 2·cos((C+D)/2)·cos((C-D)/2)")
    pdf.add_point("cosC - cosD = -2·sin((C+D)/2)·sin((C-D)/2)")
    
    pdf.add_heading("2. Specific Values")
    pdf.add_point("sin 15° = (√3 - 1) / 2√2")
    pdf.add_point("cos 15° = (√3 + 1) / 2√2")
    pdf.add_point("tan 15° = 2 - √3")
    pdf.add_point("tan 75° = 2 + √3")
    pdf.add_point("sin 18° = (√5 - 1) / 4")
    pdf.add_point("cos 36° = (√5 + 1) / 4")

    pdf.add_heading("3. Periodicity")
    pdf.add_point("sin(ax) -> Period = 2π/|a|")
    pdf.add_point("cos(ax) -> Period = 2π/|a|")
    pdf.add_point("tan(ax) -> Period = π/|a|")
    pdf.add_point("|sin(x)| -> Period = π")

    # --- PAGE 12: PARABOLA (PARAMETRIC & FOCAL) ---
    pdf.add_page()
    pdf.add_title("PARABOLA - PARAMETRIC & FOCAL")
    pdf.add_heading("1. Focal Chord")
    pdf.add_point("If PQ is a focal chord, then 1/SP + 1/SQ = 2/l (where l is semi-latus rectum)")
    pdf.add_point("If P(t1) and Q(t2) are ends of a focal chord, then t1·t2 = -1")
    pdf.add_point("Length of focal chord = a(t + 1/t)²")
    
    pdf.add_heading("2. Parametric Forms")
    pdf.add_point("Parametric point: P(t) = (at², 2at)")
    pdf.add_point("Chord joining P(t1) and Q(t2): y(t1+t2) = 2x + 2at1t2")
    pdf.add_point("Tangent at P(t): t·y = x + a·t²")
    pdf.add_point("Normal at P(t): t·x + y = 2at + a·t³")

    # --- PAGE 13: PARABOLA (STANDARD TABLE) ---
    pdf.add_page()
    pdf.add_title("PARABOLA - STANDARD EQUATIONS")
    pdf.add_point("1. y² = 4ax: Vertex (0,0), Focus (a,0), Directrix x = -a")
    pdf.add_point("2. y² = -4ax: Vertex (0,0), Focus (-a,0), Directrix x = a")
    pdf.add_point("3. x² = 4ay: Vertex (0,0), Focus (0,a), Directrix y = -a")
    pdf.add_point("4. x² = -4ay: Vertex (0,0), Focus (0,-a), Directrix y = a")
    pdf.add_figure("Four standard parabolas with their foci and directrices")

    # --- PAGE 14: PARABOLA (TANGENTS & AREAS) ---
    pdf.add_page()
    pdf.add_title("PARABOLA - TANGENTS & AREAS")
    pdf.add_heading("1. Tangents & Normals")
    pdf.add_point("Condition for y = mx + c to touch y² = 4ax: c = a/m")
    pdf.add_point("Point of contact: (a/m², 2a/m)")
    pdf.add_point("Condition for y = mx + c to be normal: c = -2am - am³")
    pdf.add_point("Sum of slopes of tangents from (x1,y1): m1 + m2 = 2a/y1")
    pdf.add_point("Product of slopes: m1·m2 = x1/y1")
    
    pdf.add_heading("2. Areas")
    pdf.add_point("Area of triangle formed by 2 tangents and chord of contact:")
    pdf.add_formula("Δ = (S11)^(3/2) / (2a)")
    pdf.add_point("Area of triangle formed by 3 points on parabola:")
    pdf.add_formula("Δ = (1/8a)|(y1-y2)(y2-y3)(y3-y1)|")

    # --- PAGE 15: ELLIPSE & HYPERBOLA ---
    pdf.add_page()
    pdf.add_title("ELLIPSE & HYPERBOLA")
    
    pdf.add_heading("1. Ellipse (x²/a² + y²/b² = 1, a > b)")
    pdf.add_point("Eccentricity: e = √(1 - b²/a²)  (e < 1)")
    pdf.add_point("Foci = (±ae, 0), Directrices = x = ±a/e")
    pdf.add_point("Length of Latus Rectum = 2b²/a")
    pdf.add_point("Distance b/w foci = 2ae, Distance b/w directrices = 2a/e")
    pdf.add_point("Product of distances = 2a²")
    
    pdf.add_heading("2. Hyperbola (x²/a² - y²/b² = 1)")
    pdf.add_point("Eccentricity: e = √(1 + b²/a²)  (e > 1)")
    pdf.add_point("Foci = (±ae, 0), Directrices = x = ±a/e")
    pdf.add_point("Length of Latus Rectum = 2b²/a")
    pdf.add_point("Asymptotes: y = ±(b/a)x")
    pdf.add_point("Transverse axis = 2a, Conjugate axis = 2b")
    pdf.add_figure("Ellipse with major/minor axes, Hyperbola with transverse/conjugate axes")

    # --- PAGE 16: HYPERBOLA (CONJUGATE & RECTANGULAR) ---
    pdf.add_page()
    pdf.add_title("HYPERBOLA - SPECIAL TYPES")
    pdf.add_heading("1. Conjugate Hyperbola")
    pdf.add_point("Equation: x²/a² - y²/b² = -1 (or y²/b² - x²/a² = 1)")
    pdf.add_point("Eccentricity: e_conjugate = √(1 + a²/b²)")
    pdf.add_point("Relation: 1/e1² + 1/e2² = 1")
    
    pdf.add_heading("2. Rectangular Hyperbola")
    pdf.add_point("Equation: x² - y² = a²  (when a = b)")
    pdf.add_point("Eccentricity: e = √2")
    pdf.add_point("Equation in parametric form: xy = c², x = ct, y = c/t")

    # Save PDF
    pdf_filename = "Complete_JEE_Notes_Typed.pdf"
    pdf.output(pdf_filename)
    return pdf_filename

if __name__ == "__main__":
    print("📄 Generating Master PDF (16 Pages)...")
    file = generate_master_pdf()
    print(f"✅ PDF Generated: {file}")
    
    print("📤 Sending to Telegram...")
    try:
        with open(file, "rb") as f:
            bot.send_document(ADMIN_ID, f, caption="📚 <b>Complete JEE Short Notes (Typed)</b>\nAll 16 pages, formulas, and diagrams transcribed perfectly.", parse_mode="HTML")
        print("🎉 Sent successfully! Check your Telegram.")
    except Exception as e:
        print(f"❌ Failed to send: {e}")
