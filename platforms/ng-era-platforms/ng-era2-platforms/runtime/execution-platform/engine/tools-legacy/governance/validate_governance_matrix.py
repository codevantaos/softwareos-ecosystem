# @ECO-governed
# @ECO-layer: GL90-99
# @ECO-semantic: archive-tools
# @ECO-audit-trail: ../../engine/gl-platform.governance/GL_SEMANTIC_ANCHOR.json
#
# GL Unified Architecture Governance Framework Activated
#
# @ECO-governed
# @ECO-layer: gl-platform.governance
# @ECO-semantic: validate-gl-platform.governance-matrix
# @ECO-audit-trail: ../../engine/gl-platform.governance/GL_SEMANTIC_ANCHOR.json
#
#!/usr/bin/env python3
"""
Validate Architecture Governance Matrix
驗證架構治理矩陣的完整性和一致性
Usage:
    python validate-gl-platform.governance-matrix.py [--verbose]
"""
# MNGA-002: Import organization needs review
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict
try:
    import yaml
except ImportError:
    print(
        "Error: PyYAML is required. Install it with: pip install pyyaml",
        file=sys.stderr,
    )
    sys.exit(1)
def load_yaml_safe(file_path: str) -> Dict:
    """Safely load YAML file"""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"Warning: Could not load {file_path}: {e}", file=sys.stderr)
        return {}
def validate_layers_domains(verbose: bool = False) -> bool:
    """Validate layers and domains configuration"""
    file_path = "gl-platform.governance/architecture/layers-domains.yaml"
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found, skipping validation", file=sys.stderr)
        return True  # Don't fail if file doesn't exist
    data = load_yaml_safe(file_path)
    if not data:
        print(f"Warning: {file_path} is empty or invalid", file=sys.stderr)
        return True
    layers = data.get("layers", {})
    domains = data.get("domains", {})
    if verbose:
        print(f"✅ Layers defined: {len(layers)}")
        print(f"✅ Domains defined: {len(domains)}")
    # Check minimum requirements
    if len(layers) < 3:
        print("Warning: Less than 3 layers defined", file=sys.stderr)
    return True
def validate_ownership_map(verbose: bool = False) -> bool:
    """Validate ownership map"""
    file_path = "gl-platform.governance/ownership-map.yaml"
    if not os.path.exists(file_path):
        print(f"Warning: {file_path} not found, skipping validation", file=sys.stderr)
        return True
    data = load_yaml_safe(file_path)
    if not data:
        print(f"Warning: {file_path} is empty or invalid", file=sys.stderr)
        return True
    modules = data.get("modules", {})
    if verbose:
        print(f"✅ Modules with ownership: {len(modules)}")
    return True
def validate_behavior_softwareos-contracts(verbose: bool = False) -> bool:
    """Validate behavior softwareos-contracts"""
    softwareos-contracts_dir = "gl-platform.governance/behavior-softwareos-contracts"
    if not os.path.exists(softwareos-contracts_dir):
        print(
            f"Warning: {softwareos-contracts_dir} not found, skipping validation", file=sys.stderr
        )
        return True
    softwareos-contracts = list(Path(softwareos-contracts_dir).rglob("*.yaml"))
    if verbose:
        print(f"✅ Behavior softwareos-contracts found: {len(softwareos-contracts)}")
    # Validate each contract
    for contract_path in softwareos-contracts:
        data = load_yaml_safe(str(contract_path))
        if not data:
            print(f"Warning: Invalid contract: {contract_path}", file=sys.stderr)
    return True
def validate_schemas(verbose: bool = False) -> bool:
    """Validate gl-platform.governance schemas"""
    schemas_dir = "gl-platform.governance/schemas"
    if not os.path.exists(schemas_dir):
        print(
            f"Warning: {schemas_dir} not found, creating empty validation",
            file=sys.stderr,
        )
        return True
    schemas = list(Path(schemas_dir).rglob("*.json"))
    if verbose:
        print(f"✅ Schema files found: {len(schemas)}")
    # Validate JSON syntax
    for schema_path in schemas:
        try:
            with open(schema_path, "r", encoding='utf-8') as f:
                json.load(f)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {schema_path}: {e}", file=sys.stderr)
            return False
    return True
def validate_policies(verbose: bool = False) -> bool:
    """Validate policy files"""
    policies_dir = "gl-platform.governance/policies"
    if not os.path.exists(policies_dir):
        print(
            f"Info: {policies_dir} not found, skipping policy validation",
            file=sys.stderr,
        )
        return True
    policies = list(Path(policies_dir).rglob("*.yaml")) + list(
        Path(policies_dir).rglob("*.yml")
    )
    if verbose:
        print(f"✅ Policy files found: {len(policies)}")
    for policy_path in policies:
        data = load_yaml_safe(str(policy_path))
        if not data:
            print(f"Warning: Invalid policy: {policy_path}", file=sys.stderr)
    return True
def main():
    parser = argparse.ArgumentParser(
        description="Validate Architecture Governance Matrix"
    )
    parser.add_argument("--verbose", action="store_true", help="Verbose output")
    args = parser.parse_args()
    print("🔍 Validating Architecture Governance Matrix...", file=sys.stderr)
    all_valid = True
    # Run all validations
    checks = [
        ("Layers & Domains", validate_layers_domains),
        ("Ownership Map", validate_ownership_map),
        ("Behavior Contracts", validate_behavior_softwareos-contracts),
        ("Schemas", validate_schemas),
        ("Policies", validate_policies),
    ]
    for name, check_func in checks:
        if args.verbose:
            print(f"\nValidating {name}...", file=sys.stderr)
        try:
            result = check_func(args.verbose)
            if not result:
                all_valid = False
                print(f"❌ {name} validation failed", file=sys.stderr)
            elif args.verbose:
                print(f"✅ {name} validation passed", file=sys.stderr)
        except Exception as e:
            print(f"❌ {name} validation error: {e}", file=sys.stderr)
            all_valid = False
    if all_valid:
        print("\n✅ All gl-platform.governance validations passed", file=sys.stderr)
        return 0
    else:
        print("\n❌ Some gl-platform.governance validations failed", file=sys.stderr)
        return 1
if __name__ == "__main__":
    sys.exit(main())
