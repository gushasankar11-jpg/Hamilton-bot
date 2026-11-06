import ast

path = "corporate_pipeline.py"
content = open(path).read()

# Find the error handling inside manager_api_call
old_error = '''            else:
                err = data["error"]["message"]
                log_error(f"Key {k_idx+1} failed: {err}")
                update_state("Manager", "Error encountered", error=err)
                if "limit: 0" in err or "retry in" in err.lower():
                    BANNED_KEYS.add(key)
                time.sleep(2)'''

new_error = '''            else:
                err = data["error"]["message"]
                log_error(f"Key {k_idx+1} failed: {err}")
                update_state("Manager", "Error encountered", error=err)
                
                # If Google is overloaded (503 High Demand) or Network Timeout
                if "high demand" in err.lower() or "503" in err or "timeout" in err.lower():
                    log_error("Google Servers Overloaded. Forcing 5-minute cooldown.")
                    for rem in range(300, 0, -1):
                        update_state("Manager", f"Google Overload. Wait {rem//60}m {rem%60}s", error="503 High Demand")
                        time.sleep(1)
                    break # Restart the key loop
                
                # If Groq daily limit is reached (TPD)
                elif "tokens per day" in err.lower() or "tpd" in err.lower():
                    log_error("Groq Daily Limit Reached. Banning key.")
                    BANNED_KEYS.add(key)
                    
                # If standard rate limit (429)
                elif "limit: 0" in err or "429" in err:
                    BANNED_KEYS.add(key)
                else:
                    time.sleep(2)'''

if old_error in content:
    content = content.replace(old_error, new_error)
    try:
        ast.parse(content)
        open(path, "w").write(content)
        print("✅ Patched Manager: Added Smart Pausing for 503 Overload & Daily Limits.")
    except SyntaxError as e:
        print(f"❌ Syntax Error: {e}")
else:
    print("⚠️ Could not find error block.")
