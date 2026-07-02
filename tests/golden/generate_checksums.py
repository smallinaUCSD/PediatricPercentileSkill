"""Regenerates tests/golden/CHECKSUMS.sha256 from the current golden fixtures.

Run this ONLY as part of a reviewed, cited change to a golden vector (see
CONTRIBUTING.md). CI fails the build if a fixture's checksum doesn't match
this file, which forces any edit to the frozen vectors to also touch this
file -- making the change visible to the CODEOWNERS review required on
tests/golden/.
"""

import hashlib
from pathlib import Path

HERE = Path(__file__).parent
FIXTURES = ["vectors.json", "formula_examples.json"]

lines = []
for name in FIXTURES:
    digest = hashlib.sha256((HERE / name).read_bytes()).hexdigest()
    lines.append(f"{digest}  {name}\n")

(HERE / "CHECKSUMS.sha256").write_text("".join(lines))
print("wrote", HERE / "CHECKSUMS.sha256")
