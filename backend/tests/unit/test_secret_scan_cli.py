import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_secret_scan_accepts_source_and_built_frontend() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/check_no_secrets.py"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "secret_scan_passed" in result.stdout


def test_secret_scan_rejects_privileged_name_in_ignored_frontend_bundle() -> None:
    probe = ROOT / "frontend/dist/__secret_scan_probe__.js"
    probe.parent.mkdir(parents=True, exist_ok=True)
    probe.write_text("const leaked = 'GOOGLE_API_KEY';", encoding="utf-8")
    try:
        result = subprocess.run(
            [sys.executable, "scripts/check_no_secrets.py"],
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
    finally:
        probe.unlink(missing_ok=True)

    assert result.returncode == 1
    assert "frontend_privilege:GOOGLE_API_KEY" in result.stdout
