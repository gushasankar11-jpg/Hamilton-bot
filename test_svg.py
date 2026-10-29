import os
import subprocess

OUT = os.path.expanduser("~/storage/shared/Hamilton_Test")
os.makedirs(OUT, exist_ok=True)

svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="500" height="300" viewBox="0 0 500 300">
  <rect width="500" height="300" fill="white"/>
  <line x1="20" y1="150" x2="480" y2="150" stroke="black" stroke-width="1.5" stroke-dasharray="5,3"/>
  <text x="440" y="145" font-size="13" font-family="Arial">Principal Axis</text>
  <path d="M 380,40 Q 320,150 380,260" stroke="black" stroke-width="3" fill="none"/>
  <line x1="380" y1="40" x2="395" y2="45" stroke="black" stroke-width="1"/>
  <line x1="370" y1="70" x2="385" y2="75" stroke="black" stroke-width="1"/>
  <line x1="360" y1="105" x2="375" y2="110" stroke="black" stroke-width="1"/>
  <line x1="352" y1="150" x2="367" y2="150" stroke="black" stroke-width="1"/>
  <line x1="360" y1="195" x2="375" y2="190" stroke="black" stroke-width="1"/>
  <line x1="370" y1="230" x2="385" y2="225" stroke="black" stroke-width="1"/>
  <line x1="380" y1="260" x2="395" y2="255" stroke="black" stroke-width="1"/>
  <circle cx="350" cy="150" r="3" fill="black"/>
  <text x="345" y="170" font-size="13" font-family="Arial">P</text>
  <circle cx="220" cy="150" r="3" fill="black"/>
  <text x="215" y="170" font-size="13" font-family="Arial">C</text>
  <circle cx="285" cy="150" r="3" fill="black"/>
  <text x="280" y="170" font-size="13" font-family="Arial">F</text>
  <line x1="120" y1="150" x2="120" y2="70" stroke="blue" stroke-width="2"/>
  <polygon points="115,75 120,65 125,75" fill="blue"/>
  <text x="95" y="60" font-size="12" font-family="Arial" fill="blue">Object</text>
  <line x1="120" y1="70" x2="355" y2="70" stroke="red" stroke-width="1.5"/>
  <polygon points="350,65 360,70 350,75" fill="red"/>
  <line x1="355" y1="70" x2="180" y2="220" stroke="red" stroke-width="1.5"/>
  <line x1="120" y1="70" x2="345" y2="160" stroke="green" stroke-width="1.5"/>
  <line x1="345" y1="160" x2="180" y2="100" stroke="green" stroke-width="1.5"/>
  <line x1="245" y1="150" x2="245" y2="115" stroke="orange" stroke-width="2"/>
  <polygon points="240,120 245,110 250,120" fill="orange"/>
  <text x="200" y="200" font-size="12" font-family="Arial" fill="orange">Image</text>
</svg>'''

svg_path = os.path.join(OUT, "concave_mirror.svg")
png_path = os.path.join(OUT, "concave_mirror.png")

with open(svg_path, "w") as f:
    f.write(svg)

print("Converting SVG to PNG...")
result = subprocess.run(
    ["rsvg-convert", "-w", "800", "-o", png_path, svg_path],
    capture_output=True, text=True
)

if result.returncode == 0:
    size = os.path.getsize(png_path)
    print(f"✅ Success! PNG saved ({size} bytes)")
    print(f"📁 Location: {png_path}")
    print(f"📱 Open Files app → Hamilton_Test → concave_mirror.png")
else:
    print(f"❌ Failed: {result.stderr}")
