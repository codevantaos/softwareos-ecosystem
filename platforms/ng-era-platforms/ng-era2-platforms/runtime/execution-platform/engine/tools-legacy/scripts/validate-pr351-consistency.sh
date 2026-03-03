#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# PR #351 Consistency Validation Script
# Validates that all security enhancements are consistently referenced
# ═══════════════════════════════════════════════════════════════════════════

set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
EXIT_CODE=0
CONFIG_TARGET="machinenativeops.yaml"

echo "════════════════════════════════════════════════════════════════════════"
echo "  PR #351 Consistency Validation"
echo "════════════════════════════════════════════════════════════════════════"
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 1: Policy ID References
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 1: Checking policy ID references..."
POLICY_IDS=("SEC-PATH-001" "SEC-LOG-001" "SEC-CRYPTO-001")
REQUIRED_FILES=(
  "governance/10-policy/base-policies/security-policies.yaml"
  "governance/37-behavior-softwareos-contracts/core.slsa_provenance.yaml"
  "config/unified-config-index.yaml"
  "${CONFIG_TARGET}"
)

for policy_id in "${POLICY_IDS[@]}"; do
  echo "  Checking ${policy_id}..."
  for file in "${REQUIRED_FILES[@]}"; do
    if ! grep -q "${policy_id}" "${PROJECT_ROOT}/${file}" 2>/dev/null; then
      echo "    ✗ FAIL: ${policy_id} not found in ${file}"
      EXIT_CODE=1
    else
      echo "    ✓ OK: ${policy_id} found in ${file}"
    fi
  done
done
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 2: SAFE_ROOT_PATH Environment Variable
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 2: Checking SAFE_ROOT_PATH references..."
SAFE_ROOT_FILES=(
  ".env.example"
  "core/contract_service/softwareos-contracts-L1/softwareos-contracts/src/services/provenance.ts"
  "docs/security/PR351_SECURITY_ENHANCEMENTS.md"
)

for file in "${SAFE_ROOT_FILES[@]}"; do
  if ! grep -q "SAFE_ROOT_PATH" "${PROJECT_ROOT}/${file}" 2>/dev/null; then
    echo "  ✗ FAIL: SAFE_ROOT_PATH not found in ${file}"
    EXIT_CODE=1
  else
    echo "  ✓ OK: SAFE_ROOT_PATH found in ${file}"
  fi
done
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 3: PR #351 Documentation References
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 3: Checking PR #351 documentation..."
REQUIRED_DOCS=(
  "docs/security/PR351_SECURITY_ENHANCEMENTS.md"
  "docs/architecture/PR351_ARCHITECTURE_EVOLUTION.md"
)

for doc in "${REQUIRED_DOCS[@]}"; do
  if [ ! -f "${PROJECT_ROOT}/${doc}" ]; then
    echo "  ✗ FAIL: Required document missing: ${doc}"
    EXIT_CODE=1
  else
    echo "  ✓ OK: Document exists: ${doc}"
  fi
done

# Check DOCUMENTATION_INDEX.md references both docs
if grep -q "PR351_SECURITY_ENHANCEMENTS" "${PROJECT_ROOT}/DOCUMENTATION_INDEX.md" && \
   grep -q "PR351_ARCHITECTURE_EVOLUTION" "${PROJECT_ROOT}/DOCUMENTATION_INDEX.md"; then
  echo "  ✓ OK: Both docs referenced in DOCUMENTATION_INDEX.md"
else
  echo "  ✗ FAIL: PR #351 docs not properly referenced in DOCUMENTATION_INDEX.md"
  EXIT_CODE=1
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 4: Error Class Consistency
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 4: Checking error class consistency..."
ERROR_FILE="${PROJECT_ROOT}/core/contract_service/softwareos-contracts-L1/softwareos-contracts/src/errors/AppError.ts"

if [ ! -f "${ERROR_FILE}" ]; then
  echo "  ✗ FAIL: AppError.ts not found"
  EXIT_CODE=1
else
  EXPECTED_ERRORS=("ValidationError" "NotFoundError" "UnauthorizedError" "ForbiddenError" "ConflictError" "ServiceUnavailableError" "InternalError")
  for error_class in "${EXPECTED_ERRORS[@]}"; do
    if grep -q "export class ${error_class}" "${ERROR_FILE}"; then
      echo "  ✓ OK: ${error_class} defined"
    else
      echo "  ✗ FAIL: ${error_class} not defined"
      EXIT_CODE=1
    fi
  done
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 5: Service Method Consistency
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 5: Checking service method consistency..."
PROVENANCE_FILE="${PROJECT_ROOT}/core/contract_service/softwareos-contracts-L1/softwareos-contracts/src/services/provenance.ts"

if [ ! -f "${PROVENANCE_FILE}" ]; then
  echo "  ✗ FAIL: provenance.ts not found"
  EXIT_CODE=1
else
  EXPECTED_METHODS=("resolveSafePath" "generateFileDigest" "SAFE_ROOT")
  for method in "${EXPECTED_METHODS[@]}"; do
    if grep -q "${method}" "${PROVENANCE_FILE}"; then
      echo "  ✓ OK: ${method} found in provenance.ts"
    else
      echo "  ✗ FAIL: ${method} not found in provenance.ts"
      EXIT_CODE=1
    fi
  done
fi
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 6: Configuration Version Consistency
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 6: Checking configuration versions..."
check_version() {
  local file=$1
  local expected_pattern=$2
  if [ ! -f "${PROJECT_ROOT}/${file}" ]; then
    echo "  ✗ FAIL: ${file} not found"
    EXIT_CODE=1
    return
  fi
  if grep -q "${expected_pattern}" "${PROJECT_ROOT}/${file}"; then
    echo "  ✓ OK: ${file} has version information"
  else
    echo "  ⚠ WARN: ${file} version format differs"
  fi
}

check_version "${CONFIG_TARGET}" "version:"
check_version "config/unified-config-index.yaml" 'version: "2.0.0"'
check_version "governance/10-policy/base-policies/security-policies.yaml" 'version: "1.0.0"'
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Test 7: Bilingual Documentation Consistency
# ═══════════════════════════════════════════════════════════════════════════
echo "✓ Test 7: Checking bilingual consistency..."
BILINGUAL_DOCS=(
  "docs/security/PR351_SECURITY_ENHANCEMENTS.md"
  "governance/10-policy/README.md"
)

for doc in "${BILINGUAL_DOCS[@]}"; do
  if [ ! -f "${PROJECT_ROOT}/${doc}" ]; then
    echo "  ⚠ SKIP: ${doc} not found"
    continue
  fi
  # Check for Chinese characters (basic check)
  if grep -qP '[\p{Han}]' "${PROJECT_ROOT}/${doc}" 2>/dev/null || \
     grep -q '[一-龥]' "${PROJECT_ROOT}/${doc}" 2>/dev/null; then
    echo "  ✓ OK: ${doc} contains bilingual content"
  else
    echo "  ⚠ WARN: ${doc} may be missing Chinese content"
  fi
done
echo ""

# ═══════════════════════════════════════════════════════════════════════════
# Summary
# ═══════════════════════════════════════════════════════════════════════════
echo "════════════════════════════════════════════════════════════════════════"
if [ ${EXIT_CODE} -eq 0 ]; then
  echo "  ✅ ALL CONSISTENCY CHECKS PASSED"
else
  echo "  ❌ SOME CONSISTENCY CHECKS FAILED"
fi
echo "════════════════════════════════════════════════════════════════════════"
echo ""

exit ${EXIT_CODE}
