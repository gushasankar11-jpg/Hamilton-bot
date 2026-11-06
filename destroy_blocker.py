import os, ast

print("🔍 Hunting down the 'No data yet' blocker...")

fixed = False
for filename in os.listdir("bot_chunks"):
    if filename.endswith(".py"):
        path = os.path.join("bot_chunks", filename)
        content = open(path).read()
        
        if "No data yet. /exam first." in content:
            print(f"🎯 Found it in {path}!")
            lines = content.split("\n")
            new_lines = []
            
            for line in lines:
                if "No data yet. /exam first." in line:
                    print(f"   Commenting out line: {line.strip()}")
                    # Comment out the safe_send line
                    new_lines.append("# " + line)
                else:
                    new_lines.append(line)
                    
            new_content = "\n".join(new_lines)
            try:
                ast.parse(new_content)
                open(path, "w").write(new_content)
                print(f"✅ Successfully removed the blocker from {path}")
                fixed = True
            except SyntaxError as e:
                print(f"❌ Syntax error after patch in {path}: {e}")

if not fixed:
    print("⚠️ Could not find the blocker in any file.")

# Ensure c50_planner.py has the /plan command
planner_path = "bot_chunks/c50_planner.py"
if os.path.exists(planner_path):
    print(f"✅ {planner_path} exists.")
else:
    print(f"❌ {planner_path} is MISSING. We need to recreate it.")
