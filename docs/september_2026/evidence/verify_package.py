"""Verify every payload byte; run from anywhere. No dependencies or network."""
from pathlib import Path
import hashlib, json
root = Path(__file__).resolve().parent
manifest = json.loads((root/'MANIFEST.json').read_text())
expected = {r['path']:r for r in manifest['files']}
actual = {p.relative_to(root).as_posix() for p in root.rglob('*') if p.is_file() and p.name != 'MANIFEST.json'}
assert actual == set(expected), ('Unexpected/missing files', actual ^ set(expected))
for name, row in expected.items():
    p = root/name
    assert p.stat().st_size == row['bytes'] and hashlib.sha256(p.read_bytes()).hexdigest() == row['sha256'], name
print(f"PASS: {len(expected)} files match the package manifest")
