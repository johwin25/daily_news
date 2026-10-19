"""Display a dated report in Actions without interpreting model text as HTML."""
import html
import json
import os
from pathlib import Path


def render_summary(folder):
    folder = Path(folder)
    status_path = folder / "run_status.json"
    if not status_path.exists():
        return "## Daily News research\n\nNo run status was produced. Check the failed step.\n"
    status = json.loads(status_path.read_text(encoding="utf-8"))
    if status.get("status") == "failed":
        body = ("Pipeline failed.\nStage: " + status.get("stage", "unknown")
                + "\nDiagnostic: " + status.get("error", "unknown"))
    else:
        report = folder / "briefing.txt"
        body = report.read_text(encoding="utf-8") if report.exists() else "Report file missing."
    return "## Daily News research\n\n<pre>" + html.escape(body) + "</pre>\n"


def main():
    folders = sorted(Path("output").glob("*/run_status.json"))
    summary = render_summary(folders[-1].parent if folders else Path("output"))
    destination = os.environ.get("GITHUB_STEP_SUMMARY")
    if destination:
        with open(destination, "a", encoding="utf-8") as stream:
            stream.write(summary)
    else:
        print(summary)


if __name__ == "__main__":
    main()
