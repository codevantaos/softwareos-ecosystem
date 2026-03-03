# @ECO-governed
# @ECO-layer: GL90-99
# @ECO-semantic: archive-tools
# @ECO-audit-trail: ../../engine/gl-platform.governance/GL_SEMANTIC_ANCHOR.json
#
# GL Unified Architecture Governance Framework Activated
#
# @ECO-governed
# @ECO-layer: gl-platform.governance
# @ECO-semantic: validate-phase2
# @ECO-audit-trail: ../../engine/gl-platform.governance/GL_SEMANTIC_ANCHOR.json
#
#!/usr/bin/env python3
"""
Phase 2 Deliverables Validator
Validates that all Phase 2 (Integration) deliverables are present and correctly formatted.
Usage:
    python3 tools/refactor/validate-phase2.py --deliverables-path <path>
"""
# MNGA-002: Import organization needs review
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Tuple
try:
    import yaml
except ImportError:
    print("❌ PyYAML not installed. Install with: pip install pyyaml")
    sys.exit(1)
class Phase2Validator:
    """Validator for Phase 2 deliverables."""
    REQUIRED_DELIVERABLES = {
        "module_boundaries.md": {
            "type": "markdown",
            "description": "Module boundary specifications",
            "min_size": 500,
            "required_sections": ["Responsibilities", "Boundaries"],
        },
        "interface_softwareos-contracts.yaml": {
            "type": "yaml",
            "description": "API contract definitions",
            "required_keys": ["softwareos-contracts", "version"],
        },
        "integration_strategy.md": {
            "type": "markdown",
            "description": "Integration strategy plan",
            "min_size": 1000,
            "required_sections": ["Strategy", "Patterns"],
        },
        "migration_roadmap.yaml": {
            "type": "yaml",
            "description": "Migration roadmap",
            "required_keys": ["phases", "timeline"],
        },
    }
    def __init__(self, deliverables_path: str):
        self.deliverables_path = Path(deliverables_path)
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.passed: List[str] = []
    def validate(self) -> Tuple[bool, Dict]:
        """Run all validations."""
        print(f"🔍 Validating Phase 2 deliverables at: {self.deliverables_path}")
        print("")
        # Check directory exists
        if not self.deliverables_path.exists():
            self.errors.append(
                f"Deliverables directory not found: {self.deliverables_path}"
            )
            return False, self._get_report()
        # Validate each deliverable
        for filename, spec in self.REQUIRED_DELIVERABLES.items():
            self._validate_deliverable(filename, spec)
        # Check for integration tests
        self._check_integration_tests()
        # Print summary
        self._print_summary()
        # Return results
        success = len(self.errors) == 0
        return success, self._get_report()
    def _validate_deliverable(self, filename: str, spec: Dict):
        """Validate a single deliverable."""
        filepath = self.deliverables_path / filename
        # Check existence
        if not filepath.exists():
            self.errors.append(f"Missing deliverable: {filename}")
            print(f"❌ {filename} - Not found")
            return
        # Check file size
        file_size = filepath.stat().st_size
        min_size = spec.get("min_size", 0)
        if file_size < min_size:
            self.warnings.append(
                f"{filename} is smaller than expected ({file_size} < {min_size} bytes)"
            )
        # Validate content based on type
        file_type = spec.get("type")
        try:
            if file_type == "yaml":
                self._validate_yaml(filepath, spec)
            elif file_type == "markdown":
                self._validate_markdown(filepath, spec)
            self.passed.append(filename)
            print(f"✓ {filename} - Valid")
        except Exception as e:
            self.errors.append(f"{filename}: {str(e)}")
            print(f"❌ {filename} - {str(e)}")
    def _validate_yaml(self, filepath: Path, spec: Dict):
        """Validate YAML file."""
        with open(filepath, "r", encoding='utf-8') as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ValueError("Empty YAML file")
        # Check required keys
        required_keys = spec.get("required_keys", [])
        for key in required_keys:
            if key not in data:
                raise ValueError(f"Missing required key: {key}")
    def _validate_markdown(self, filepath: Path, spec: Dict):
        """Validate Markdown file."""
        with open(filepath, "r", encoding='utf-8') as f:
            content = f.read()
        if len(content.strip()) == 0:
            raise ValueError("Empty Markdown file")
        # Check for required sections
        required_sections = spec.get("required_sections", [])
        for section in required_sections:
            if section.lower() not in content.lower():
                self.warnings.append(
                    f"{filepath.name}: Missing recommended section: {section}"
                )
    def _check_integration_tests(self):
        """Check for integration test suites."""
        # Look for tests directory in workspace
        repo_root = self.deliverables_path.parent.parent.parent
        tests_dir = repo_root / "workspace" / "tests" / "integration"
        if not tests_dir.exists():
            self.warnings.append(
                "Integration tests directory not found: workspace/tests/integration/"
            )
        else:
            # Count test files
            test_files = list(tests_dir.glob("**/*test*.{py,js,ts}"))
            if len(test_files) == 0:
                self.warnings.append("No integration test files found")
            else:
                print(f"ℹ Found {len(test_files)} integration test files")
    def _print_summary(self):
        """Print validation summary."""
        print("")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("📊 Validation Summary")
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print(f"✓ Passed: {len(self.passed)}")
        print(f"⚠ Warnings: {len(self.warnings)}")
        print(f"❌ Errors: {len(self.errors)}")
        print("")
        if self.warnings:
            print("Warnings:")
            for warning in self.warnings:
                print(f"  ⚠ {warning}")
            print("")
        if self.errors:
            print("Errors:")
            for error in self.errors:
                print(f"  ❌ {error}")
            print("")
    def _get_report(self) -> Dict:
        """Get validation report."""
        return {
            "phase": 2,
            "deliverables_path": str(self.deliverables_path),
            "passed": self.passed,
            "warnings": self.warnings,
            "errors": self.errors,
            "success": len(self.errors) == 0,
        }
def main():
    parser = argparse.ArgumentParser(
        description="Validate Phase 2 (Integration) deliverables"
    )
    parser.add_argument(
        "--deliverables-path",
        required=True,
        help="Path to Phase 2 deliverables directory",
    )
    parser.add_argument(
        "--output", help="Output validation report to file (JSON format)"
    )
    args = parser.parse_args()
    # Run validation
    validator = Phase2Validator(args.deliverables_path)
    success, report = validator.validate()
    # Save report if requested
    if args.output:
        with open(args.output, "w", encoding='utf-8') as f:
            json.dump(report, f, indent=2)
        print(f"📄 Report saved to: {args.output}")
    # Exit with appropriate code
    sys.exit(0 if success else 1)
if __name__ == "__main__":
    main()
