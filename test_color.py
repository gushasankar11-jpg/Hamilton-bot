import os
import subprocess

OUT = os.path.expanduser("~/storage/shared/Hamilton_Test")
os.makedirs(OUT, exist_ok=True)

svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="600" height="400" viewBox="0 0 600 400">
  <rect width="600" height="400" fill="#0a0a1a"/>
  
  <!-- Title -->
  <text x="300" y="35" font-size="24" font-family="Arial" font-weight="bold" fill="#ffffff" text-anchor="middle">HAMILTON STUDY AI — COLOR TEST</text>
  
  <!-- Row 1: Solid color circles -->
  <circle cx="80" cy="100" r="35" fill="#FF0000"/>
  <circle cx="170" cy="100" r="35" fill="#FF7F00"/>
  <circle cx="260" cy="100" r="35" fill="#FFFF00"/>
  <circle cx="350" cy="100" r="35" fill="#00FF00"/>
  <circle cx="440" cy="100" r="35" fill="#0000FF"/>
  <circle cx="530" cy="100" r="35" fill="#9400D3"/>
  
  <!-- Row 1 labels -->
  <text x="80" y="160" font-size="11" fill="#ffffff" text-anchor="middle">RED</text>
  <text x="170" y="160" font-size="11" fill="#ffffff" text-anchor="middle">ORANGE</text>
  <text x="260" y="160" font-size="11" fill="#ffffff" text-anchor="middle">YELLOW</text>
  <text x="350" y="160" font-size="11" fill="#ffffff" text-anchor="middle">GREEN</text>
  <text x="440" y="160" font-size="11" fill="#ffffff" text-anchor="middle">BLUE</text>
  <text x="530" y="160" font-size="11" fill="#ffffff" text-anchor="middle">VIOLET</text>
  
  <!-- Row 2: Gradient rectangle -->
  <defs>
    <linearGradient id="rainbow" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%" stop-color="#FF0000"/>
      <stop offset="16%" stop-color="#FF7F00"/>
      <stop offset="33%" stop-color="#FFFF00"/>
      <stop offset="50%" stop-color="#00FF00"/>
      <stop offset="66%" stop-color="#00BFFF"/>
      <stop offset="83%" stop-color="#0000FF"/>
      <stop offset="100%" stop-color="#9400D3"/>
    </linearGradient>
    <radialGradient id="sun" cx="50%" cy="50%" r="50%">
      <stop offset="0%" stop-color="#FFFFFF"/>
      <stop offset="40%" stop-color="#FFD700"/>
      <stop offset="100%" stop-color="#FF4500"/>
    </radialGradient>
  </defs>
  
  <rect x="50" y="190" width="500" height="50" fill="url(#rainbow)" rx="25"/>
  <text x="300" y="260" font-size="14" fill="#ffffff" text-anchor="middle">Rainbow Gradient Bar</text>
  
  <!-- Row 3: Sun with radial gradient -->
  <circle cx="120" cy="330" r="45" fill="url(#sun)"/>
  <text x="120" y="395" font-size="11" fill="#ffffff" text-anchor="middle">SUN (Radial)</text>
  
  <!-- Row 3: Colored diamond -->
  <polygon points="300,290 340,330 300,370 260,330" fill="#00FFFF" stroke="#FFFFFF" stroke-width="2"/>
  <text x="300" y="395" font-size="11" fill="#ffffff" text-anchor="middle">CYAN DIAMOND</text>
  
  <!-- Row 3: Colored star -->
  <polygon points="470,290 480,320 510,320 486,340 495,370 470,350 445,370 454,340 430,320 460,320" 
           fill="#FF00FF" stroke="#FFFF00" stroke-width="2"/>
  <text x="470" y="395" font-size="11" fill="#ffffff" text-anchor="middle">MAGENTA STAR</text>
  
  <!-- Border -->
  <rect x="5" y="5" width="590" height="390" fill="none" stroke="#00FF00" stroke-width="3" rx="15"/>
</svg>'''

svg_path = os.path.join(OUT, "color_test.svg")
png_path = os.path.join(OUT, "color_test.png")

with open(svg_path, "w") as f:
    f.write(svg)

print("🎨 Converting colorful SVG to PNG...")
result = subprocess.run(
    ["rsvg-convert", "-w", "900", "-o", png_path, svg_path],
    capture_output=True, text=True
)

if result.returncode == 0:
    size = os.path.getsize(png_path)
    print(f"✅ Success! PNG saved ({size} bytes)")
    print(f"📁 Location: {png_path}")
    print(f"📱 Open Files → Hamilton_Test → color_test.png")
else:
    print(f"❌ Failed: {result.stderr}")
