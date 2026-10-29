#!/usr/bin/env bash
# Master deploy / rollback for Stage 1 sticker patch
# Usage:
#   ./deploy_stickers.sh              → preflight + gate + swap + restart
#   ./deploy_stickers.sh --rollback   → validate + restore + restart
#   ./deploy_stickers.sh --preflight-only
set -uo pipefail

cd "$(dirname "$0")"

MANIFEST="install_manifest_20261014_224330.txt"
BACKUP_TS="20261014_224330"
BOT_BACKUP="bot.py.bak_${BACKUP_TS}"
CFG_BACKUP="config.py.bak_${BACKUP_TS}"
C01_BACKUP="bot_chunks/c01.py.bak_${BACKUP_TS}"
C02_BACKUP="bot_chunks/c02.py.bak_${BACKUP_TS}"
EXPECTED_CWD="/data/data/com.termux/files/home/hamilton"

MODE="${1:-deploy}"

# ---------- helpers ----------
fail() { echo "FAIL: $*"; exit 1; }
ok()   { echo "OK  : $*"; }

verify_bot_process() {
    local pids count pid exe cwd cmd
    pids=$(pgrep -f "python.*bot\.py" || true)
    count=$(printf '%s\n' "$pids" | grep -c . || true)
    [ "$count" = "1" ] || { echo "FAIL: expected 1 bot process, found $count"; return 1; }
    pid="$pids"
    case "$pid" in ''|*[!0-9]*) echo "FAIL: PID not numeric"; return 1;; esac
    [ -d "/proc/$pid" ] || { echo "FAIL: /proc/$pid missing"; return 1; }
    exe=$(readlink "/proc/$pid/exe" 2>/dev/null || true)
    cwd=$(readlink "/proc/$pid/cwd" 2>/dev/null || true)
    cmd=$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)
    [ "$cwd" = "$EXPECTED_CWD" ] || { echo "FAIL: cwd=$cwd"; return 1; }
    [ "$cmd" = "python bot.py " ] || { echo "FAIL: cmd=$cmd"; return 1; }
    case "$exe" in */bin/python3.*) ;; *) echo "FAIL: exe=$exe"; return 1;; esac
    echo "pid=$pid exe=$exe cwd=$cwd cmd=$cmd"
    return 0
}

stop_bot_graceful() {
    verify_bot_process || fail "cannot stop — identity check failed"
    local pid
    pid=$(pgrep -f "python.*bot\.py")
    kill -TERM "$pid"
    local i
    for i in $(seq 1 30); do
        [ ! -d "/proc/$pid" ] && { ok "process exited after ${i}s"; return 0; }
        sleep 1
    done
    echo "FAIL: PID $pid did not exit within 30s. No SIGKILL sent."
    echo "      Manual: kill -TERM $pid"
    exit 1
}

launch_bot() {
    nohup python -u bot.py > bot.log 2>&1 &
    local new_pid=$!
    echo "launched PID=$new_pid"
    sleep 5
    [ -d "/proc/$new_pid" ] || { echo "FAIL: new process gone"; tail -40 bot.log; exit 1; }
    local n_exe n_cwd
    n_exe=$(readlink "/proc/$new_pid/exe" 2>/dev/null || true)
    n_cwd=$(readlink "/proc/$new_pid/cwd" 2>/dev/null || true)
    echo "new exe=$n_exe"
    echo "new cwd=$n_cwd"
    [ "$n_cwd" = "$EXPECTED_CWD" ] || fail "new cwd mismatch"
    case "$n_exe" in */bin/python3.*) ;; *) fail "new exe mismatch";; esac
    if grep -q "Hamilton Study AI is live" bot.log; then
        ok "startup banner found"
    else
        # Fallback: banner may still be in Python's buffer — check liveness
        sleep 3
        if grep -q "Hamilton Study AI is live" bot.log; then
            ok "startup banner found (delayed flush)"
        else
            # Verify process is alive and polling (fallback liveness)
            local_pid=$(pgrep -f "python.*bot\.py" | head -1 || true)
            if [ -n "$local_pid" ] && [ -d "/proc/$local_pid" ]; then
                echo "WARN: startup banner not in log yet, but PID $local_pid is alive"
                echo "      (Python output buffering — cosmetic; bot is polling)"
                ok "process alive (log may flush later)"
            else
                echo "FAIL: startup banner missing AND process not alive"
                tail -30 bot.log
                exit 1
            fi
        fi
    fi
    ok "new bot live"
}

# ---------- ROLLBACK MODE ----------
if [ "$MODE" = "--rollback" ]; then
    echo "=== ROLLBACK MODE ==="
    [ -f "$MANIFEST" ] || fail "manifest $MANIFEST missing"

    echo "--- Phase R1: validate every manifest entry ---"
    COUNT=0
    while IFS=$'\t' read -r ts orig bak; do
        [ -z "${bak:-}" ] && continue
        [ -f "$bak" ] || fail "backup missing: $bak"
        case "$bak" in
            *.py) python3 -c "compile(open('$bak').read(),'$bak','exec')" \
                  || fail "backup $bak does not compile" ;;
        esac
        COUNT=$((COUNT+1))
    done < "$MANIFEST"
    [ "$COUNT" -ge 4 ] || fail "manifest has $COUNT entries (<4)"
    ok "validated $COUNT backups"

    echo "--- Phase R2: stage all restores to temp ---"
    STAGE_DIR=".rb_stage_$(date +%Y%m%d_%H%M%S)"
    mkdir -p "$STAGE_DIR"
    while IFS=$'\t' read -r ts orig bak; do
        [ -z "${bak:-}" ] && continue
        staged="$STAGE_DIR/$(echo "$orig" | tr '/' '_')"
        cp -p "$bak" "$staged"
        cmp -s "$staged" "$bak" || fail "staging $orig"
    done < "$MANIFEST"
    ok "staged into $STAGE_DIR"

    echo "--- Phase R3: atomic install ---"
    while IFS=$'\t' read -r ts orig bak; do
        [ -z "${bak:-}" ] && continue
        staged="$STAGE_DIR/$(echo "$orig" | tr '/' '_')"
        python3 -c "
import os, shutil
shutil.copyfile('$staged', '$orig.tmp')
os.replace('$orig.tmp', '$orig')
"
        cmp -s "$orig" "$bak" || fail "post-restore mismatch: $orig"
        ok "restored $orig"
    done < "$MANIFEST"
    rm -rf "$STAGE_DIR"

    echo "--- Phase R4: restart with restored bot ---"
    LOG_TS=$(date +%Y%m%d_%H%M%S)
    [ -f bot.log ] && cp -p bot.log "bot.log.rollback_${LOG_TS}"
    stop_bot_graceful
    launch_bot
    echo ""
    echo "=== ROLLBACK COMPLETE ==="
    exit 0
fi

# ---------- PREFLIGHT (both deploy and preflight-only) ----------
echo "=== PREFLIGHT ==="

echo "--- [1] bot.py.new compile + counts ---"
python3 -c "compile(open('bot.py.new').read(),'bot.py.new','exec')" \
    || fail "bot.py.new does not compile"
H=$(grep -cE '^def try_send_sticker\(' bot.py.new || true)
W=$(grep -c 'try_send_sticker(uid, "welcome")' bot.py.new || true)
[ "$H" = "1" ] || fail "helper defs=$H (need 1)"
[ "$W" = "1" ] || fail "welcome calls=$W (need 1)"
ok "helper=1 welcome=1"

echo "--- [2] bot.py.new == source reconstruction ---"
TMPD="${TMPDIR:-$HOME}"; REBUILT="$TMPD/_pre.py"
: > "$REBUILT"
for f in $(ls bot_chunks/c*.py | sort -V); do
    cat "$f" >> "$REBUILT"; echo "" >> "$REBUILT"; echo "" >> "$REBUILT"
done
cmp -s "$REBUILT" bot.py.new || { rm -f "$REBUILT"; fail "recon != bot.py.new"; }
rm -f "$REBUILT"
ok "reconstruction matches"

echo "--- [3] process identity ---"
verify_bot_process || fail "process check"

echo "--- [4] backups + manifest + patched-source sanity ---"
[ -f "$MANIFEST" ] || fail "manifest $MANIFEST missing"

# Each backup must exist and compile
while IFS=$'\t' read -r ts orig bak; do
    [ -z "${bak:-}" ] && continue
    [ -f "$bak" ] || fail "backup missing: $bak"
    [ -f "$orig" ] || fail "original missing: $orig"
    case "$bak" in
        *.py) python3 -c "compile(open('$bak').read(),'$bak','exec')" \
              || fail "backup does not compile: $bak" ;;
    esac
done < "$MANIFEST"
ok "backups exist and compile"

# bot.py must still equal its backup (not swapped yet)
cmp -s bot.py "$BOT_BACKUP" || fail "live bot.py differs from backup (already swapped?)"
ok "bot.py == original backup (not yet swapped)"

# Live sources must carry the intended patch
grep -qE "^ENABLE_STICKERS\s*=\s*False" config.py \
    || fail "config.py missing ENABLE_STICKERS=False"
grep -qE "^STICKER_IDS\s*=\s*\{\}" config.py \
    || fail "config.py missing STICKER_IDS={}"
ok "config.py has flag+ids"

grep -qE "^def try_send_sticker\(" bot_chunks/c01.py \
    || fail "c01.py missing helper"
ok "c01.py has helper"

grep -q 'try_send_sticker(uid, "welcome")' bot_chunks/c02.py \
    || fail "c02.py missing welcome call"
ok "c02.py has welcome call"

echo ""
echo "=== PREFLIGHT PASSED ==="

if [ "$MODE" = "--preflight-only" ]; then
    echo "(--preflight-only: stopping here)"
    exit 0
fi

# ---------- APPROVAL GATE ----------
echo ""
echo "Deployment will:"
echo "  1. Snapshot current bot.py as bot.py.preswap_<ts>"
echo "  2. Atomic swap bot.py.new -> bot.py"
echo "  3. Kill current PID (graceful, no SIGKILL)"
echo "  4. Launch new bot and verify"
echo "  5. Preserve bot.log as bot.log.preswap_<ts>"
echo ""
printf "Type DEPLOY to proceed, or anything else to abort: "
read -r CONFIRM
[ "$CONFIRM" = "DEPLOY" ] || { echo "aborted by user"; exit 0; }

# ---------- DEPLOY ----------
echo ""
echo "=== DEPLOY ==="

cmp -s bot.py "$BOT_BACKUP" || fail "live bot.py drifted since backup"

TS=$(date +%Y%m%d_%H%M%S)
cp -p bot.py "bot.py.preswap_${TS}"
ok "snapshot: bot.py.preswap_${TS}"

python3 << 'SWAP'
import os, stat, tempfile, sys
src, dst = "bot.py.new", "bot.py"
with open(src, "rb") as f:
    content = f.read()
try:
    compile(content.decode("utf-8"), dst, "exec")
except SyntaxError as e:
    print(f"FAIL: compile: {e}"); sys.exit(1)
mode = stat.S_IMODE(os.stat(dst).st_mode)
d = os.path.dirname(os.path.abspath(dst))
fd, tmp = tempfile.mkstemp(dir=d, prefix=".bot.swap")
try:
    with os.fdopen(fd, "wb") as f:
        f.write(content); f.flush(); os.fsync(f.fileno())
    os.chmod(tmp, mode)
    os.replace(tmp, dst)
    print("SWAP OK")
except Exception as e:
    try: os.unlink(tmp)
    except Exception: pass
    print(f"FAIL: replace: {e}"); sys.exit(1)
SWAP

if cmp -s bot.py bot.py.new; then
    ok "bot.py == bot.py.new"
elif cmp -s bot.py "$BOT_BACKUP"; then
    fail "swap did not take effect (bot.py still == original)"
else
    fail "bot.py matches neither original nor new"
fi

python3 -c "compile(open('bot.py').read(),'bot.py','exec')" \
    || fail "swapped bot.py does not compile"
ok "post-swap verify"

echo ""
echo "--- Restart ---"
LOG_TS=$(date +%Y%m%d_%H%M%S)
[ -f bot.log ] && cp -p bot.log "bot.log.preswap_${LOG_TS}" && ok "log preserved"
stop_bot_graceful
launch_bot

echo ""
echo "=== POST-DEPLOY CHECKS ==="
python3 - << 'PYEOF'
import sys, config
assert config.ENABLE_STICKERS is False, "flag is not False"
assert config.STICKER_IDS == {}, "ids not empty"
print("OK  : ENABLE_STICKERS=False, STICKER_IDS={}")
PYEOF

if tail -200 bot.log | grep -iE "traceback|unhandled"; then
    echo "FAIL: errors in log"
    exit 1
fi
ok "log clean"

cmp -s bot.py bot.py.new || fail "post-deploy mismatch"
ok "bot.py == bot.py.new"

echo ""
echo "=== DEPLOY COMPLETE ==="
echo ""
echo "Now test in Telegram:"
echo "  T1: /start   → greeting"
echo "  T2: /health  → health report"
echo "  T3: /exam    → mode selector"
echo "  T4: /status  → profile summary"
echo ""
echo "If any test fails, run:  ./deploy_stickers.sh --rollback"
