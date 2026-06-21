import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_real_probe_without_credentials_is_explicitly_blocked() -> None:
    environment = os.environ.copy()
    environment.pop("GOOGLE_API_KEY", None)
    result = subprocess.run(
        [
            sys.executable,
            "backend/scripts/validate_live_transcription.py",
            "--real",
        ],
        cwd=ROOT,
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 2
    assert json.loads(result.stdout)["status"] == "blocked_missing_credentials"
