"""Fail when source/build output contains credential material or frontend privileges."""

from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".css",
    ".html",
    ".js",
    ".json",
    ".md",
    ".py",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
SECRET_PATTERNS = {
    "google_api_key": re.compile(r"AIza[0-9A-Za-z_-]{35}"),
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
}
FRONTEND_FORBIDDEN_NAMES = {
    "GEMINI_API_KEY",
    "GOOGLE_API_KEY",
    "DATABASE_URL",
    "MCP_CREDENTIAL",
    "APP_WS_TOKEN_SECRET",
}


def _candidate_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    candidates = {ROOT / line for line in result.stdout.splitlines() if line}
    frontend_dist = ROOT / "frontend/dist"
    if frontend_dist.exists():
        candidates.update(path for path in frontend_dist.rglob("*") if path.is_file())
    return sorted(candidates)


def _is_frontend_runtime(path: Path) -> bool:
    relative = path.relative_to(ROOT)
    return relative.parts[:2] in {("frontend", "src"), ("frontend", "dist")}


def find_violations() -> list[str]:
    """Return deterministic, value-free descriptions of detected violations."""
    violations: list[str] = []
    for path in sorted(_candidate_files()):
        if not path.is_file() or path.suffix not in TEXT_SUFFIXES:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore")
        relative = path.relative_to(ROOT)
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(content):
                violations.append(f"{relative}:{name}")
        if _is_frontend_runtime(path):
            for name in sorted(FRONTEND_FORBIDDEN_NAMES):
                if name in content:
                    violations.append(f"{relative}:frontend_privilege:{name}")
    return violations


def main() -> int:
    """Print a stable result without echoing any detected secret value."""
    violations = find_violations()
    if violations:
        print("secret_scan_failed")
        for violation in violations:
            print(violation)
        return 1
    print("secret_scan_passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
