# ==========================================================
# bot.py — Chunk 21: Find + Leaderboard + Rank Predictor
# ==========================================================

# ----------------------------------------------------------
# Save test result to profile on finish
# ----------------------------------------------------------
def _save_test_to_profile(uid, exam, papers_data, total_score, total_max):
    p = load_profile(uid) or {}
    history = p.setdefault("test_history", [])
    entry = {
        "date": datetime.now().isoformat(),
        "exam": exam,
        "total_score": total_score,
        "total_max": total_max,
        "percentile_pred": None,
        "rank_pred": None,
        "papers": len(papers_data),
        "correct": sum(x.get("correct", 0) for x in papers_data),
        "wrong": sum(x.get("wrong", 0) for x in papers_data),
        "skipped": sum(x.get("skipped", 0) for x in papers_data),
    }
    history.append(entry)
    p["test_history"] = history[-20:]
    save_profile(uid, p)


# Wrap existing _test_finish to save result
_prev_test_finish = _test_finish


def _test_finish(uid):
    sess = exam_engine.get_session(uid)
    if not sess or sess.get("mode") != "test":
        return
    exam = sess.get("exam")
    # Compute totals before original runs (it clears session)
    papers_data = sess.get("paper_scores", [])
    total_score = sum(x.get("score", 0) for x in papers_data)
    total_max = sum(x.get("max", 0) for x in papers_data)
    try:
        _save_test_to_profile(uid, exam, papers_data, total_score, total_max)
    except Exception as e:
        print(f"[TEST-SAVE] {e}")
    _prev_test_finish(uid)


# ----------------------------------------------------------
# Profile stats helper
# ----------------------------------------------------------
def _profile_stats(profile):
    """Returns dict with attempts, accuracy, health, rank, percentile, test_count."""
    summary = health.attempts_summary(profile)
    r = health.overall_health(profile)
    tests = profile.get("test_history", [])

    # Rank/percentile from test performance
    rank_score, rank_tier = _rank_from_tests(tests)
    pct = _percentile_from_tests(tests)

    # Selected chapters count
    sel = profile.get("selected_chapters", {})
    chapters_per_subject = {k: len(v) for k, v in sel.items()}
    total_chapters = sum(chapters_per_subject.values())

    return {
        "attempts": summary["attempted"],
        "correct": summary["correct"],
        "wrong": summary["wrong"],
        "accuracy": summary["accuracy"],
        "overall_health": r.get("overall"),
        "subjects": r.get("subjects", {}),
        "test_count": len(tests),
        "rank_tier": rank_tier,
        "rank_score": rank_score,
        "percentile": pct,
        "chapters_per_subject": chapters_per_subject,
        "total_chapters": total_chapters,
        "tests": tests,
    }


def _rank_from_tests(tests):
    """Best test performance → rank tier."""
    if not tests:
        return 0, "Not eligible — write a test"
    best = 0.0
    for t in tests:
        if t.get("total_max", 0) > 0:
            pct = t["total_score"] / t["total_max"] * 100
            best = max(best, pct)
    if best >= 85: return best, "Top 500"
    if best >= 75: return best, "Top 2,000"
    if best >= 65: return best, "Top 8,000"
    if best >= 55: return best, "Top 20,000"
    if best >= 45: return best, "Top 50,000"
    return best, "Needs improvement"


def _percentile_from_tests(tests):
    if not tests:
        return 0
    best = 0.0
    for t in tests:
        if t.get("total_max", 0) > 0:
            p = t["total_score"] / t["total_max"] * 100
            best = max(best, p)
    # Map 0-100 → percentile band
    if best >= 85: return 99.5
    if best >= 75: return 98.0
    if best >= 65: return 95.0
    if best >= 55: return 90.0
    if best >= 45: return 82.0
    if best >= 35: return 70.0
    return round(best * 1.5, 1)


# ----------------------------------------------------------
# Leaderboard eligibility
# ----------------------------------------------------------
CHAPTERS_MIN_PER_SUBJECT = 15
TESTS_MIN = 1


def _is_leaderboard_eligible(profile):
    """Returns (eligible_bool, reason_str)."""
    sel = profile.get("selected_chapters", {})
    if not sel:
        return False, "No chapters selected"

    for subj, chs in sel.items():
        if len(chs) < CHAPTERS_MIN_PER_SUBJECT:
            return False, f"{subj}: only {len(chs)} chapters (need {CHAPTERS_MIN_PER_SUBJECT})"

    # Require at least 2 subjects selected
    if len([s for s in sel if len(sel[s]) >= CHAPTERS_MIN_PER_SUBJECT]) < 2:
        return False, "Need at least 2 subjects with 15+ chapters"

    tests = profile.get("test_history", [])
    if len(tests) < TESTS_MIN:
        return False, f"Write at least {TESTS_MIN} full test first"

    return True, "eligible"


# ----------------------------------------------------------
# Rebuild leaderboard with new rules
# ----------------------------------------------------------
def _compute_leaderboard(level_filter=None):
    entries = []
    if not os.path.exists(PROFILE_DIR):
        return entries
    for fname in os.listdir(PROFILE_DIR):
        if not fname.endswith(".json"):
            continue
        uid_str = fname.replace(".json", "")
        try:
            with open(os.path.join(PROFILE_DIR, fname)) as f:
                p = json.load(f)
        except Exception:
            continue
        if not p.get("secured") or not p.get("name"):
            continue
        if not p.get("leaderboard_optin", True):
            continue
        if not p.get("exams"):
            continue

        lvl = (p.get("level") or "").lower()
        if level_filter == "junior" and lvl != "junior":
            continue
        if level_filter == "senior" and lvl not in ("senior", "dropper"):
            continue

        eligible, _ = _is_leaderboard_eligible(p)
        if not eligible:
            continue

        stats = _profile_stats(p)
        score = (stats["rank_score"] * 0.6) + (stats["percentile"] * 0.4)

        entries.append({
            "uid": uid_str,
            "hku": p.get("hku_id", "—"),
            "name": p.get("name"),
            "institute": p.get("institute", "—"),
            "level": p.get("level", "—"),
            "health": round(stats["overall_health"] or 0, 1),
            "percentile": stats["percentile"],
            "rank_tier": stats["rank_tier"],
            "attempts": stats["attempts"],
            "accuracy": stats["accuracy"],
            "test_count": stats["test_count"],
            "score": round(score, 1),
        })
    entries.sort(key=lambda x: x["score"], reverse=True)
    return entries


# ----------------------------------------------------------
# /find — full user profile
# ----------------------------------------------------------
@bot.message_handler(commands=['find'])
def cmd_find(message):
    uid = message.chat.id
    parts = message.text.strip().split()
    if len(parts) < 2:
        safe_send(uid,
            "🔍 *Search a user*\n\n"
            "Usage: `/find HKU-000001`\n\n"
            "_Reply with the exact HKU ID (uppercase)._",
            parse_mode="Markdown")
        return
    hku = parts[1].strip().upper()
    if not hku.startswith("HKU-"):
        safe_send(uid, "❌ ID format must be HKU-XXXXXX")
        return

    found_uid = find_user_by_hku_id(hku)
    if not found_uid:
        safe_send(uid, f"❌ No user found with ID {hku}.")
        return

    try:
        target = load_profile(int(found_uid))
    except Exception:
        target = load_profile(found_uid)
    if not target or not target.get("secured"):
        safe_send(uid, "❌ User profile not available.")
        return

    stats = _profile_stats(target)

    lines = [
        f"🔍 *Profile — {target.get('name','—')}*",
        "",
        f"🆔 {hku}",
        f"🏫 {target.get('institute','—')}",
        f"🎓 {target.get('level','—')}",
        f"📚 {', '.join(EXAM_NAMES.get(e,e) for e in target.get('exams',[]))}",
        f"📅 Year: {target.get('target_year','—')}",
        "",
        "━━━ 📖 Chapters ━━━",
    ]
    for subj, count in stats["chapters_per_subject"].items():
        lines.append(f"   {subj}: {count} chapters")
    lines.append(f"   Total: {stats['total_chapters']}")

    lines += [
        "",
        "━━━ 📊 Attempts (all modes) ━━━",
        f"Total attempted: *{stats['attempts']}*",
        f"✅ Correct: {stats['correct']}",
        f"❌ Wrong: {stats['wrong']}",
        f"🎯 Accuracy: *{stats['accuracy']}%*",
        "",
        "━━━ 🧪 Test History ━━━",
        f"Tests written: *{stats['test_count']}*",
    ]

    for t in stats["tests"][-3:]:
        lines.append(
            f"   • {t['exam']}: {t['total_score']}/{t['total_max']}")

    lines += [
        "",
        "━━━ ❤️ Health ━━━",
        f"Overall: *{stats['overall_health'] or 0}/100*",
    ]
    for subj, sd in stats["subjects"].items():
        h = sd.get("health")
        if h is not None:
            lines.append(f"   {subj}: {h}/100")

    lines += [
        "",
        "━━━ 🏆 Rank Prediction (from tests) ━━━",
        f"Tier: *{stats['rank_tier']}*",
        f"Percentile: *{stats['percentile']}*",
    ]

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")

    if SVG_ENABLED and stats["overall_health"] is not None:
        subj_data = {s: d.get("health") for s, d in stats["subjects"].items()}
        svg = svg_templates.combined_progress(stats["overall_health"], subj_data)
        path = svg_renderer.render_svg(svg, name=f"find_{found_uid}")
        if path:
            safe_send_photo(uid, path,
                            caption=f"{target.get('name','')} — Progress")
            svg_renderer.cleanup_file(path)


# ----------------------------------------------------------
# /rank — user's own prediction (per exam)
# ----------------------------------------------------------
@bot.message_handler(commands=['rank'])
def cmd_rank(message):
    uid = message.chat.id
    ready, reason = _profile_ready(uid)
    if not ready:
        _send_setup_prompt(uid, reason)
        return

    p = load_profile(uid)
    stats = _profile_stats(p)

    lines = ["🏆 *YOUR RANK PREDICTION*", ""]
    lines.append(f"👤 {p.get('name','—')}  ·  🆔 {p.get('hku_id','—')}")
    lines.append("")

    # Per-exam prediction
    for exam in p.get("exams", []):
        exam_tests = [t for t in stats["tests"] if t["exam"] == exam]
        if not exam_tests:
            lines.append(f"📘 *{EXAM_NAMES[exam]}*: no tests yet")
            continue
        best = max(
            (t["total_score"] / t["total_max"] * 100) if t["total_max"] else 0
            for t in exam_tests
        )
        if best >= 85: tier, pct = "Top 500", 99.5
        elif best >= 75: tier, pct = "Top 2,000", 98.0
        elif best >= 65: tier, pct = "Top 8,000", 95.0
        elif best >= 55: tier, pct = "Top 20,000", 90.0
        elif best >= 45: tier, pct = "Top 50,000", 82.0
        else: tier, pct = "Needs work", round(best * 1.5, 1)
        lines.append(f"📘 *{EXAM_NAMES[exam]}*")
        lines.append(f"   Best score: {best:.1f}%")
        lines.append(f"   Tier: {tier}  ·  %ile: {pct}")
        lines.append("")

    lines.append(f"🧪 Tests written: {stats['test_count']}")
    lines.append(f"❤️ Overall health: {stats['overall_health'] or 0}/100")

    safe_send(uid, "\n".join(lines), parse_mode="Markdown")


print("bot.py Chunk 21 loaded: find + leaderboard + rank ready.")

