# ==========================================================
# notes_engine.py — Hamilton Study AI
# 3-stage notes: analyze → generate → validate
# Strict rule: output is ONLY rich markdown (math in $...$), no code blocks.
# ==========================================================

import json
import re
import time
import ai_client


# ==========================================================
# STAGE 1 — ANALYZE CHAPTER
# ==========================================================
def analyze_chapter(exam, subject, chapter, subtopics, concepts):
    """
    Returns dict:
    {
      "chapter_type": "formula-heavy" | "concept-heavy" | "reaction-heavy" | "graph-heavy" | "mixed",
      "pages_required": int (2-30),
      "reasoning": str
    }
    """
    sub_list = "\n".join(f"- {s}" for s in subtopics[:40])
    concept_list = "\n".join(f"- {c}" for c in concepts[:60])

    prompt = (
        f"Chapter: {chapter}\n"
        f"Subject: {subject} | Exam: {exam}\n\n"
        f"Subtopics ({len(subtopics)}):\n{sub_list}\n\n"
        f"Concepts ({len(concepts)}):\n{concept_list}\n\n"
        "Classify this chapter and estimate page count for exhaustive revision notes.\n"
        "Return ONLY JSON:\n"
        '{"chapter_type":"formula-heavy|concept-heavy|reaction-heavy|graph-heavy|mixed",'
        '"pages_required":<int between 2 and 30>,'
        '"reasoning":"<one short line>"}'
    )

    raw = ai_client.ask_hamilton(exam, prompt)
    if not raw:
        # Fallback: 1 page per subtopic, cap at 15
        return {"chapter_type": "mixed",
                "pages_required": max(2, min(15, len(subtopics))),
                "reasoning": "fallback"}

    raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"chapter_type": "mixed",
                "pages_required": max(2, min(15, len(subtopics))),
                "reasoning": "parse-fallback"}

    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"chapter_type": "mixed",
                "pages_required": max(2, min(15, len(subtopics))),
                "reasoning": "parse-fallback"}

    try:
        pages = int(data.get("pages_required", len(subtopics)))
    except Exception:
        pages = len(subtopics)
    pages = max(2, min(30, pages))

    return {
        "chapter_type": str(data.get("chapter_type", "mixed")),
        "pages_required": pages,
        "reasoning": str(data.get("reasoning", ""))[:120],
    }


# ==========================================================
# STAGE 2 — GENERATE ONE PAGE
# ==========================================================
def generate_page(exam, subject, chapter, page_num, total_pages,
                  page_topics, chapter_type):
    """
    page_topics: list of subtopic dicts [{"name":..., "concepts":[...]}]
    Returns plain markdown string with $ math. No code blocks.
    """
    topics_text = ""
    for st in page_topics:
        topics_text += f"\n### {st['name']}\n"
        for c in st["concepts"]:
            topics_text += f"- {c}\n"

    type_rules = {
        "formula-heavy":
            "Emphasise every formula + its applicability condition + trap. "
            "Short table for comparisons. No derivations unless critical.",
        "concept-heavy":
            "Emphasise definitions, classifications, comparison tables, "
            "exceptions. Compact 2-3 line explanations only.",
        "reaction-heavy":
            "Emphasise reaction map: SUBSTRATE → REAGENT → PRODUCT → KEY RULE. "
            "List conditions that change the product.",
        "graph-heavy":
            "For each important graph: axes, slope meaning, area meaning, "
            "intercepts, limiting behaviour.",
        "mixed":
            "Balance formulas, definitions, tables and exceptions as needed.",
    }
    type_rule = type_rules.get(chapter_type, type_rules["mixed"])

    system_override = (
        "You are a JEE revision-notes writer. "
        "Output ONLY clean markdown. "
        "STRICT RULE: every mathematical expression MUST be wrapped in $...$ (inline) "
        "or $$...$$ (display). Never write raw LaTeX without $ markers. "
        "NEVER use ``` code fences. NEVER output SVG code. "
        "For matrices use display math: $$A = \\begin{bmatrix} a & b \\\\ c & d \\end{bmatrix}$$. "
        "Friendly senior voice — 'Hey, look at this...'. "
        "Revision-focused: student has already studied the chapter."
    )

    prompt = (
        f"Write page {page_num} of {total_pages} — short revision notes.\n"
        f"Chapter: {chapter} ({subject}, {exam})\n"
        f"Chapter type: {chapter_type}\n\n"
        f"Subtopics on this page:\n{topics_text}\n\n"
        f"STYLE RULES:\n{type_rule}\n\n"
        "MANDATORY:\n"
        "1. Follow the subtopic order above. Do not invent or skip.\n"
        "2. Cover EVERY listed concept.\n"
        "3. Wrap every formula: $...$ inline, $$...$$ display.\n"
        "4. Include each formula's condition / when it applies.\n"
        "5. Include exceptions and boundary cases.\n"
        "6. Applications: as many as needed for PYQ-level problems.\n"
        "7. Avoid derivations, basic textbook explanations, filler.\n"
        "7b. SHORTCUTS: For any long chain, order, or multi-step rule, add a short mnemonic or trick box. Prefix with Mnemonic:.\n"
        "7c. For every list-to-remember (orders, series, classifications), give the fastest recall aid: acronym, rhyme, or visual pattern.\n"
        "7b. SHORTCUTS & MNEMONICS: For any long chain, order, or multi-step rule, "
        "add a short mnemonic/trick box (e.g., 'My Very Educated Mother...' style, "
        "or an acronym, or a pattern phrase). Prefix with '💡 Mnemonic: '.\n"
        "7c. For every 'list to remember' (orders, series, classification), "
        "give the fastest recall aid available — acronym, rhyme, visual pattern, "
        "or chunking trick.\n"
        "8. No code fences, no SVG blocks, no preamble, no title.\n"
        "9. Keep lines short. Use tables and bullet lists freely.\n"
    )

    notes = ai_client.ask_hamilton_raw(exam, prompt, system_override=system_override)
    if not notes:
        return None

    # Strip any code fences or SVG blocks that slipped through
    notes = _strip_forbidden(notes)
    return notes.strip()


def _strip_forbidden(text):
    """Remove code fences and SVG blocks from notes text."""
    if not text:
        return text
    # Remove fenced code blocks (``` ... ```)
    text = re.sub(r"```[a-zA-Z]*\n.*?\n```", "", text, flags=re.DOTALL)
    # Remove raw <svg>...</svg>
    text = re.sub(r"<svg[\s\S]*?</svg>", "", text, flags=re.IGNORECASE)
    # Remove leftover empty triple-backticks
    text = text.replace("```", "")
    return text.strip()


# ==========================================================
# STAGE 3 — VALIDATE COVERAGE
# ==========================================================
def validate_coverage(exam, chapter, subtopics, generated_pages_text):
    """
    Return:
    {
      "missing": [subtopics not covered],
      "notes": "<short summary>"
    }
    """
    sub_list = "\n".join(f"- {s}" for s in subtopics)
    combined = "\n\n".join(generated_pages_text)[:6000]

    prompt = (
        f"Chapter: {chapter}\n\n"
        f"Original subtopics:\n{sub_list}\n\n"
        f"Generated notes (excerpt):\n{combined}\n\n"
        "Check: which original subtopics are MISSING from the generated notes?\n"
        "Return ONLY JSON:\n"
        '{"missing":["subtopic1","subtopic2"]}'
    )

    raw = ai_client.ask_hamilton(exam, prompt)
    if not raw:
        return {"missing": [], "notes": "validation-skipped"}

    raw = re.sub(r"```(?:json)?", "", raw).replace("```", "").strip()
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if not m:
        return {"missing": [], "notes": "parse-failed"}

    try:
        data = json.loads(m.group(0))
    except Exception:
        return {"missing": [], "notes": "parse-failed"}

    return {
        "missing": list(data.get("missing", []))[:20],
        "notes": "ok",
    }


# ==========================================================
# PIPELINE HELPER — full chapter
# ==========================================================
def build_all_pages(exam, subject, chapter, subtopics, concepts,
                    on_page_ready=None):
    """
    Runs the full 3-stage pipeline.
    Calls on_page_ready(page_num, total_pages, text) for each page.
    Returns (all_pages_text, validation_result, analysis).
    """
    analysis = analyze_chapter(exam, subject, chapter, subtopics, concepts)
    total = analysis["pages_required"]
    ctype = analysis["chapter_type"]

    # Group subtopics so each group ≈ one page
    n = len(subtopics)
    per_page = max(1, (n + total - 1) // total)
    groups = []
    for i in range(0, n, per_page):
        chunk = subtopics[i:i + per_page]
        groups.append([{"name": s, "concepts": concepts.get(s, [])} for s in chunk])

    # Pad if fewer groups than pages
    while len(groups) < total and any(len(g) > 1 for g in groups):
        groups.sort(key=len, reverse=True)
        big = groups.pop(0)
        mid = len(big) // 2
        groups.append(big[:mid])
        groups.append(big[mid:])

    total = len(groups)
    pages_text = []
    for i, group in enumerate(groups, 1):
        page = generate_page(exam, subject, chapter, i, total, group, ctype)
        if page is None:
            page = f"_(page {i} could not be generated)_"
        pages_text.append(page)
        if on_page_ready:
            on_page_ready(i, total, page)

    validation = validate_coverage(exam, chapter, subtopics, pages_text)
    return pages_text, validation, analysis


if __name__ == "__main__":
    # Quick test with a tiny chapter
    import ai_client
    print("notes_engine.py loaded OK")
    print("Functions: analyze_chapter, generate_page, validate_coverage, build_all_pages")
