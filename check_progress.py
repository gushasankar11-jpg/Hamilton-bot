import os
base = "pyq_images/books"
if not os.path.exists(base):
    print("❌ No books extracted yet. The script might still be starting.")
    exit()

print("=" * 75)
print(f" 📚 LOCAL EXTRACTION PROGRESS")
print("=" * 75)
print(f"{'BOOK NAME':<30} | {'THEORY':<7} | {'ILLUS':<7} | {'EXER':<7} | {'SOL':<7}")
print("-" * 75)

t_t = t_i = t_e = t_s = 0

for root, dirs, files in os.walk(base):
    if "theory" in dirs or "exercise" in dirs:
        book_name = os.path.basename(root)[:28]
        t = len([f for f in os.listdir(os.path.join(root, "theory")) if f.endswith('.png')]) if "theory" in dirs else 0
        i = len([f for f in os.listdir(os.path.join(root, "illustration")) if f.endswith('.png')]) if "illustration" in dirs else 0
        e = len([f for f in os.listdir(os.path.join(root, "exercise")) if f.endswith('.png')]) if "exercise" in dirs else 0
        s = len([f for f in os.listdir(os.path.join(root, "solution")) if f.endswith('.png')]) if "solution" in dirs else 0
        
        t_t += t; t_i += i; t_e += e; t_s += s
        print(f"{book_name:<30} | {t:<7} | {i:<7} | {e:<7} | {s:<7}")

print("-" * 75)
print(f"{'TOTAL':<30} | {t_t:<7} | {t_i:<7} | {t_e:<7} | {t_s:<7}")
print("=" * 75)
