#!/usr/bin/env python3
"""
Root-of-Trust Indexer
Generates deterministic index of all governed files with SHA3-512 digests.
"""

import os
import sys
import json
import hashlib
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, List, Optional

# Configuration
GOVERNED_EXTENSIONS = {
    '.py', '.sh', '.yml', '.yaml', '.json', '.rego', '.toml', '.md',
    '.txt', '.dockerfile', 'dockerfile', 'makefile', 'makefile'
}

EXCLUDED_PATHS = {
    '.git', '.github', '__pycache__', '.pytest_cache', 'htmlcov',
    '.tox', '.eggs', '*.egg-info', 'dist', 'build', 'node_modules',
    '.venv', 'venv', 'env', '.env', 'coverage.xml', '.coverage'
}

INDEX_OUTPUT = 'architecture/root-index.json'
SCHEMA_OUTPUT = 'schemas/root-index.schema.json'

def get_sha3_512(filepath: Path) -> str:
    """Calculate SHA3-512 digest of a file."""
    sha3_512 = hashlib.sha3_512()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(8192), b''):
            sha3_512.update(chunk)
    return sha3_512.hexdigest()

def is_excluded(path: Path) -> bool:
    """Check if path should be excluded from indexing."""
    path_str = str(path)
    for excluded in EXCLUDED_PATHS:
        if excluded in path_str:
            return True
    return False

def should_index(path: Path) -> bool:
    """Check if file should be indexed."""
    if is_excluded(path):
        return False
    if not path.is_file():
        return False
    
    # Check extension
    suffix = path.suffix.lower()
    if suffix in GOVERNED_EXTENSIONS:
        return True
    
    # Check special filenames
    if path.name.lower() in ['dockerfile', 'makefile']:
        return True
    
    return False

def scan_directory(root: Path) -> List[Dict]:
    """Scan directory for governed files."""
    entries = []
    for filepath in sorted(root.rglob('*')):
        if should_index(filepath):
            rel_path = filepath.relative_to(root)
            digest = get_sha3_512(filepath)
            entries.append({
                'id': str(rel_path).replace('/', ':'),
                'path': str(rel_path),
                'digest': digest,
                'algorithm': 'sha3-512',
                'size': filepath.stat().st_size,
                'lastModified': datetime.fromtimestamp(
                    filepath.stat().st_mtime, tz=timezone.utc
                ).isoformat()
            })
    return entries

def generate_index(root: Path) -> Dict:
    """Generate root index."""
    entries = scan_directory(root)
    
    index = {
        'apiVersion': 'platform.rot/v1',
        'kind': 'RootIndex',
        'metadata': {
            'generatedAt': datetime.now(timezone.utc).isoformat(),
            'generator': 'rot_indexer.py',
            'version': '1.0.0',
            'totalFiles': len(entries)
        },
        'spec': {
            'root': str(root),
            'entries': entries
        }
    }
    
    return index

def write_audit_log(action: str, resource: str, result: str, hash_value: str = ''):
    """Write audit log entry."""
    log_entry = {
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'actor': 'rot_indexer',
        'action': action,
        'resource': resource,
        'result': result,
        'hash': hash_value,
        'version': '1.0.0',
        'requestId': os.urandom(16).hex(),
        'correlationId': os.urandom(16).hex(),
        'ip': 'unknown',
        'userAgent': 'rot_indexer.py'
    }
    
    audit_dir = Path('audit')
    audit_dir.mkdir(exist_ok=True)
    
    audit_file = audit_dir / f'rot_indexer_{datetime.now(timezone.utc).strftime("%Y%m%d")}.jsonl'
    with open(audit_file, 'a') as f:
        f.write(json.dumps(log_entry) + '\n')

def main():
    """Main entry point."""
    root = Path.cwd()
    
    # Generate index
    index = generate_index(root)
    
    # Ensure output directory exists
    output_path = Path(INDEX_OUTPUT)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write index
    with open(output_path, 'w') as f:
        json.dump(index, f, indent=2, sort_keys=True)
    
    # Write audit log
    index_hash = get_sha3_512(output_path)
    write_audit_log('generate_index', INDEX_OUTPUT, 'success', index_hash)
    
    print(f'[rot_indexer] indexed_files={len(index["spec"]["entries"])} out={INDEX_OUTPUT}')
    return 0

if __name__ == '__main__':
    sys.exit(main())