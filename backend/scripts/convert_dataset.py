import json
from pathlib import Path


def convert() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    cases_json_path = repo_root / "evals" / "cases.json"
    dest_path = repo_root / "backend" / "tests" / "eval" / "datasets" / "kithkin_cases.json"

    print(f"Reading cases from {cases_json_path}")
    with open(cases_json_path, encoding="utf-8") as f:
        data = json.load(f)

    eval_cases = []
    for case in data.get("cases", []):
        case_id = case.get("id")
        title = case.get("title")
        input_data = case.get("input", {})
        text = input_data.get("text", "")
        speaker = input_data.get("speaker", "user")

        # We can prepend the speaker so the model gets context who is speaking
        prompt_text = f"[{speaker}] {text}" if speaker != "user" else text

        eval_cases.append(
            {
                "eval_case_id": f"{case_id}_{title.replace(' ', '_').lower()}",
                "prompt": {"role": "user", "parts": [{"text": prompt_text}]},
            }
        )

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        json.dump({"eval_cases": eval_cases}, f, indent=2, ensure_ascii=False)

    print(f"Successfully wrote {len(eval_cases)} cases to {dest_path}")


if __name__ == "__main__":
    convert()
