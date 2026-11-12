"""Build the student package from an explicit allow-list (no solution, no generator).

    uv run --no-project --with nbformat python tools/make_student_release.py

Output: dist/week6-lab-student/  and  dist/week6-lab-student.zip
"""
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "dist" / "week6-lab-student"

# Everything a student needs — and nothing else.
FILES = [
    "docker-compose.yml",
    "jupyter/Dockerfile",
    "data/01_init.sql",
    "notebooks/lab.ipynb",
    "notebooks/labkit.py",
    "tests/conftest.py",
    "tests/test_lab.py",
    "pytest.ini",
    "answers.json",
    "STUDENT_README.md",
]
# Strings that must never appear in the package.
FORBIDDEN = ["solution", "True, True, False, False", "4514", "1388"]

# 1. regenerate the student notebook so it matches the source
subprocess.run([sys.executable, str(ROOT / "tools" / "build_notebooks.py")], check=True)

# 2. copy the allow-list
shutil.rmtree(OUT, ignore_errors=True)
for rel in FILES:
    dst = OUT / ("README.md" if rel == "STUDENT_README.md" else rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / rel, dst)

# 3. blank answers file (in case the team's copy was filled in while testing)
answers = json.loads((OUT / "answers.json").read_text(encoding="utf-8"))
blank = {k: ([None] * len(v) if isinstance(v, list) else None) for k, v in answers.items()}
(OUT / "answers.json").write_text(json.dumps(blank, indent=2), encoding="utf-8")

# 4. leak check
nb = json.loads((OUT / "notebooks" / "lab.ipynb").read_text(encoding="utf-8"))
if any(c.get("outputs") for c in nb["cells"]):
    sys.exit("lab.ipynb has outputs — rebuild it")
for f in OUT.rglob("*"):
    if f.is_file():
        text = f.read_text(encoding="utf-8", errors="ignore")
        for s in FORBIDDEN:
            if s in text and f.name != "README.md":
                sys.exit(f"LEAK: {s!r} found in {f.relative_to(OUT)}")

# 5. zip
zip_path = shutil.make_archive(str(OUT), "zip", OUT.parent, OUT.name)
print(f"student package: {OUT.relative_to(ROOT)}/ ({len(FILES)} files) -> {Path(zip_path).relative_to(ROOT)}")
