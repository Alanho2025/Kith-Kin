"""Evaluate sanitised input-transcription captures for the Phase 00 gate."""

import argparse
import os
import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from pydantic import BaseModel, ConfigDict  # noqa: E402

from app.domain.live_validation import (  # noqa: E402
    LiveProbeSample,
    evaluate_live_probe,
    missing_credentials_result,
)


class ProbeCapture(BaseModel):
    """Sanitised normalised capture accepted by the evaluator."""

    model_config = ConfigDict(extra="forbid")

    samples: tuple[LiveProbeSample, ...]


def _load_capture(path: Path) -> ProbeCapture:
    return ProbeCapture.model_validate_json(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--fixture", type=Path, help="Evaluate a sanitised JSON capture")
    mode.add_argument("--real", action="store_true", help="Check the credential-backed gate")
    parser.add_argument(
        "--capture",
        type=Path,
        help="Sanitised capture exported from the authenticated AI Studio run",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run fixture evaluation or report the exact real-validation blocker."""
    args = _parser().parse_args(argv)
    if args.real and not os.getenv("GOOGLE_API_KEY"):
        result = missing_credentials_result()
        print(result.model_dump_json())
        return 2
    capture_path: Path | None = args.capture if args.real else args.fixture
    if capture_path is None:
        _parser().error("--real requires --capture after the authenticated Live session")
    result = evaluate_live_probe(_load_capture(capture_path).samples)
    print(result.model_dump_json())
    return 0 if result.status.value == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
