import json
import os
from datetime import datetime, timezone
from config import LOG_FILE


def log_interaction(question: str, tier: str, response: str) -> None:
    """
    Append a structured record of this interaction to the audit log.

    Writes one JSON object per line to LOG_FILE ("logs/audit.jsonl"), creating the
    logs/ directory on demand. Also prints a one-line summary to the terminal.

    Output: None — side effects only. Any I/O error is caught and reported rather
    than propagated, so an audit-log failure never breaks the user-facing response.
    """
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    record = {
        "timestamp": timestamp,
        "tier": tier,
        "question": question[:300],
        "response_preview": response[:200],
        "question_length": len(question),
        "response_length": len(response),
    }

    try:
        log_dir = os.path.dirname(LOG_FILE)
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)

        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"[LOG ERROR] could not write audit log: {e}")
        return

    # One-line terminal summary. Truncate the question for readability; show the full
    # response length so the terminal reflects how much was actually generated.
    q_preview = question if len(question) <= 60 else question[:57] + "..."
    print(f'[LOGGED] tier={tier} | "{q_preview}" → {len(response)} chars')
