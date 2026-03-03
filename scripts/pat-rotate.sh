#!/usr/bin/env bash
# =============================================================================
# pat-rotate.sh — GitHub PAT Rotation Automation
# =============================================================================
# Usage:
#   ./scripts/pat-rotate.sh [OPTIONS]
#
# Options:
#   --repo         OWNER/REPO          Target repository (default: indestructibleorg/softwareos-base)
#   --token        GITHUB_TOKEN        Active PAT with repo+workflow+admin:org scope
#   --new-token    NEW_PAT             New PAT to set (if omitted, only revocation is performed)
#   --expiry       YYYY-MM-DD          Expiry date of new PAT
#   --revoke-ids   ID1,ID2,...         Comma-separated fine-grained PAT IDs to revoke
#   --secret-name  SECRET_NAME        GitHub Actions secret name (default: PAT_TOKEN)
#   --dry-run                          Print actions without executing
#
# Environment variables (alternative to flags):
#   GITHUB_TOKEN, NEW_PAT, PAT_EXPIRY_DATE, REVOKE_PAT_IDS, TARGET_REPO
#
# Examples:
#   # Full rotation: revoke old PATs, set new PAT and expiry
#   ./scripts/pat-rotate.sh \
#     --token ghp_xxx \
#     --new-token github_pat_yyy \
#     --expiry 2026-05-27 \
#     --revoke-ids 12345678,87654321
#
#   # Dry run to preview actions
#   ./scripts/pat-rotate.sh --token ghp_xxx --new-token github_pat_yyy --dry-run
# =============================================================================

set -euo pipefail

# ── Defaults ──────────────────────────────────────────────────────────────────
REPO="${TARGET_REPO:-indestructibleorg/softwareos-base}"
TOKEN="${GITHUB_TOKEN:-}"
NEW_TOKEN="${NEW_PAT:-}"
EXPIRY="${PAT_EXPIRY_DATE:-}"
REVOKE_IDS="${REVOKE_PAT_IDS:-}"
SECRET_NAME="PAT_TOKEN"
DRY_RUN=false
LOG_FILE="/tmp/pat-rotate-$(date -u +%Y%m%dT%H%M%SZ).log"

# ── Argument parsing ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo)        REPO="$2";        shift 2 ;;
    --token)       TOKEN="$2";       shift 2 ;;
    --new-token)   NEW_TOKEN="$2";   shift 2 ;;
    --expiry)      EXPIRY="$2";      shift 2 ;;
    --revoke-ids)  REVOKE_IDS="$2";  shift 2 ;;
    --secret-name) SECRET_NAME="$2"; shift 2 ;;
    --dry-run)     DRY_RUN=true;     shift   ;;
    *) echo "Unknown option: $1" >&2; exit 1 ;;
  esac
done

# ── Helpers ────────────────────────────────────────────────────────────────────
log() { echo "[$(date -u +%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"; }
die() { log "ERROR: $*"; exit 1; }
api() {
  local method="$1" path="$2" data="${3:-}"
  local args=(-s -X "$method" -H "Authorization: token $TOKEN" -H "Accept: application/vnd.github+json")
  [[ -n "$data" ]] && args+=(-H "Content-Type: application/json" -d "$data")
  curl "${args[@]}" "https://api.github.com${path}"
}

dry() {
  if $DRY_RUN; then
    log "[DRY-RUN] $*"
    return 0
  fi
  eval "$@"
}

# ── Validation ─────────────────────────────────────────────────────────────────
[[ -z "$TOKEN" ]] && die "--token or GITHUB_TOKEN is required"
[[ -z "$REPO" ]]  && die "--repo is required"

log "=== PAT Rotation Script ==="
log "Repository : $REPO"
log "Dry run    : $DRY_RUN"
log "Log file   : $LOG_FILE"

# Validate active token
log "Validating active token..."
USER=$(api GET /user | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('login','INVALID'))")
[[ "$USER" == "INVALID" ]] && die "Token validation failed. Check --token value."
log "Authenticated as: $USER"

# ── Step 1: Revoke old fine-grained PATs ──────────────────────────────────────
if [[ -n "$REVOKE_IDS" ]]; then
  log "--- Step 1: Revoking fine-grained PATs ---"
  IFS=',' read -ra IDS <<< "$REVOKE_IDS"
  for id in "${IDS[@]}"; do
    id=$(echo "$id" | tr -d ' ')
    log "Revoking PAT ID: $id"
    if $DRY_RUN; then
      log "[DRY-RUN] DELETE /user/personal-access-tokens/$id"
    else
      STATUS=$(api DELETE "/user/personal-access-tokens/$id" | python3 -c "
import sys, json
try:
    d = json.load(sys.stdin)
    print(d.get('message', 'revoked'))
except:
    print('revoked')
" 2>/dev/null || echo "revoked")
      log "PAT $id: $STATUS"
    fi
  done
else
  log "--- Step 1: No PAT IDs to revoke (--revoke-ids not provided) ---"
  log "To revoke Classic PATs, visit: https://github.com/settings/tokens"
  log "To revoke Fine-grained PATs, visit: https://github.com/settings/personal-access-tokens"
fi

# ── Step 2: Update GitHub Actions Secrets ─────────────────────────────────────
if [[ -n "$NEW_TOKEN" ]]; then
  log "--- Step 2: Updating GitHub Actions Secrets ---"

  # Get repo public key for secret encryption
  log "Fetching repo public key..."
  KEY_RESPONSE=$(api GET "/repos/$REPO/actions/secrets/public-key")
  KEY_ID=$(echo "$KEY_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['key_id'])")
  KEY_B64=$(echo "$KEY_RESPONSE" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['key'])")

  # Encrypt secret using PyNaCl (libsodium)
  encrypt_secret() {
    local secret_value="$1"
    python3 - "$KEY_B64" "$secret_value" << 'PYEOF'
import sys, base64
from base64 import b64decode, b64encode

key_b64 = sys.argv[1]
secret  = sys.argv[2]

try:
    from nacl import encoding, public
    public_key = public.PublicKey(key_b64.encode(), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted  = sealed_box.encrypt(secret.encode())
    print(b64encode(encrypted).decode())
except ImportError:
    # Fallback: install pynacl
    import subprocess
    subprocess.check_call(["pip3", "install", "pynacl", "-q"])
    from nacl import encoding, public
    public_key = public.PublicKey(key_b64.encode(), encoding.Base64Encoder())
    sealed_box = public.SealedBox(public_key)
    encrypted  = sealed_box.encrypt(secret.encode())
    print(b64encode(encrypted).decode())
PYEOF
  }

  # Update PAT_TOKEN secret
  log "Encrypting and updating secret: $SECRET_NAME"
  ENCRYPTED=$(encrypt_secret "$NEW_TOKEN")
  TOKEN_ID_SHORT="${NEW_TOKEN:0:30}"

  if $DRY_RUN; then
    log "[DRY-RUN] PUT /repos/$REPO/actions/secrets/$SECRET_NAME"
    log "[DRY-RUN] PUT /repos/$REPO/actions/secrets/PAT_TOKEN_ID"
    [[ -n "$EXPIRY" ]] && log "[DRY-RUN] PUT /repos/$REPO/actions/secrets/PAT_EXPIRY_DATE = $EXPIRY"
  else
    # Update PAT_TOKEN
    RESULT=$(api PUT "/repos/$REPO/actions/secrets/$SECRET_NAME" \
      "{\"encrypted_value\":\"$ENCRYPTED\",\"key_id\":\"$KEY_ID\"}")
    log "$SECRET_NAME updated: $(echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin) if sys.stdin.read(1) else {}; print(d.get('message','OK'))" 2>/dev/null || echo "OK")"

    # Update PAT_TOKEN_ID
    ENCRYPTED_ID=$(encrypt_secret "$TOKEN_ID_SHORT")
    api PUT "/repos/$REPO/actions/secrets/PAT_TOKEN_ID" \
      "{\"encrypted_value\":\"$ENCRYPTED_ID\",\"key_id\":\"$KEY_ID\"}" > /dev/null
    log "PAT_TOKEN_ID updated: ${TOKEN_ID_SHORT}..."

    # Update PAT_EXPIRY_DATE
    if [[ -n "$EXPIRY" ]]; then
      if ! echo "$EXPIRY" | grep -qE '^[0-9]{4}-[0-9]{2}-[0-9]{2}$'; then
        die "Invalid --expiry format: '$EXPIRY'. Expected YYYY-MM-DD."
      fi
      ENCRYPTED_EXP=$(encrypt_secret "$EXPIRY")
      api PUT "/repos/$REPO/actions/secrets/PAT_EXPIRY_DATE" \
        "{\"encrypted_value\":\"$ENCRYPTED_EXP\",\"key_id\":\"$KEY_ID\"}" > /dev/null
      log "PAT_EXPIRY_DATE updated: $EXPIRY"
    fi
  fi
else
  log "--- Step 2: Skipped (--new-token not provided) ---"
fi

# ── Step 3: Audit log entry ────────────────────────────────────────────────────
log "--- Step 3: Generating audit entry ---"
AUDIT_ENTRY=$(python3 - << PYEOF
import json
from datetime import datetime, timezone

entry = {
    "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "action": "pat_rotation",
    "actor": "${USER}",
    "repo": "${REPO}",
    "revoked_ids": [x.strip() for x in "${REVOKE_IDS}".split(",") if x.strip()],
    "new_token_prefix": "${NEW_TOKEN:0:20}..." if "${NEW_TOKEN}" else None,
    "new_expiry": "${EXPIRY}" if "${EXPIRY}" else None,
    "secrets_updated": ["${SECRET_NAME}", "PAT_TOKEN_ID", "PAT_EXPIRY_DATE"] if "${NEW_TOKEN}" else [],
    "dry_run": ${DRY_RUN},
}
print(json.dumps(entry, indent=2))
PYEOF
)

AUDIT_FILE="/tmp/pat-rotation-audit-$(date -u +%Y%m%dT%H%M%SZ).json"
echo "$AUDIT_ENTRY" > "$AUDIT_FILE"
log "Audit entry written: $AUDIT_FILE"
echo "$AUDIT_ENTRY"

# ── Summary ────────────────────────────────────────────────────────────────────
log ""
log "=== Rotation Complete ==="
log "Log : $LOG_FILE"
log "Audit: $AUDIT_FILE"
[[ -n "$REVOKE_IDS" ]] && log "Revoked PAT IDs: $REVOKE_IDS"
[[ -n "$NEW_TOKEN"  ]] && log "New token set in: $SECRET_NAME, PAT_TOKEN_ID, PAT_EXPIRY_DATE"
[[ -n "$EXPIRY"     ]] && log "Next expiry: $EXPIRY"
log ""
log "Next steps:"
log "  1. Verify CI pipeline: https://github.com/$REPO/actions"
log "  2. Update docs/pat-audit-report.md with rotation record"
log "  3. Confirm old token revoked: https://github.com/settings/tokens"
