"""Assemble an additive Pages release while retaining the published briefing bytes."""
import argparse
import json
import shutil
from pathlib import Path


def assemble(main_web, prototype, published_briefing, destination, commit):
    main_web, prototype, published_briefing, destination = map(
        lambda p: Path(p).resolve(), (main_web, prototype, published_briefing, destination)
    )
    if destination.exists() or any(destination.is_relative_to(p) for p in (main_web, prototype)):
        raise ValueError("Destination must be a new directory outside the source trees")
    content = published_briefing.read_bytes()
    if len(content) > 2 * 1024 * 1024:
        raise ValueError("Published briefing exceeds the expected public-data limit")
    briefing = json.loads(content)
    if not isinstance(briefing, dict) or not all(
        isinstance(briefing.get(key), list) for key in ("items", "review_queue")
    ):
        raise ValueError("Existing live briefing is unavailable or invalid; refusing replacement")
    for required in ("index.html", "app-icon.png", "manifest.webmanifest", "sw.js"):
        if not (main_web / required).is_file():
            raise ValueError(f"Missing existing production file: {required}")
    manifest = json.loads((prototype / "manifest.webmanifest").read_text())
    if manifest.get("start_url") != "./" or manifest.get("scope") != "./":
        raise ValueError("Home Screen entry must remain scoped to the prototype")
    for required in ("index.html", "app.js", "curl-renderer.js", "vendor/html-to-image.js"):
        if not (prototype / required).is_file():
            raise ValueError(f"Missing prototype file: {required}")
    ignore = shutil.ignore_patterns("node_modules", "__pycache__", ".git", "test-results")
    shutil.copytree(main_web, destination, ignore=ignore)
    target = destination / "prototype"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(prototype, target, ignore=ignore)
    (destination / "briefing.json").write_bytes(content)
    (target / "deployment.json").write_text(
        json.dumps({"commit": commit, "sample_only": True}, indent=2) + "\n"
    )
    assert (destination / "index.html").read_bytes() == (main_web / "index.html").read_bytes()
    assert (destination / "briefing.json").read_bytes() == content


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("main_web", "prototype", "published_briefing", "destination", "commit"):
        parser.add_argument(name)
    args = parser.parse_args()
    assemble(**vars(args))
    print("PASS: additive prototype artifact; existing reader and live briefing preserved")
