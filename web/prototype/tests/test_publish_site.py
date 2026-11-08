"""Meaningful publication checks: retained live data, scope and failure safety."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("assemble", ROOT / ".github/scripts/assemble_prototype_site.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.web = self.root / "main-web"
        self.web.mkdir()
        for name in ("index.html", "app-icon.png", "manifest.webmanifest", "sw.js"):
            (self.web / name).write_bytes(b"original production bytes: " + name.encode())
        (self.web / "briefing.json").write_text('{"items":[],"review_queue":[]}')
        self.live = self.root / "live.json"
        self.live.write_bytes(b'{\n "items": [], "review_queue": [{"headline":"Current edition"}]\n}\n')
        self.proto = ROOT / "web/prototype"
        self.output = self.root / "release"

    def build(self):
        module.assemble(self.web, self.proto, self.live, self.output, "abc123")

    def test_preserves_current_edition_and_original_assets(self):
        self.build()
        self.assertEqual((self.output / "briefing.json").read_bytes(), self.live.read_bytes())
        for name in ("index.html", "app-icon.png", "manifest.webmanifest", "sw.js"):
            self.assertEqual((self.output / name).read_bytes(), (self.web / name).read_bytes())
        self.assertFalse((self.output / "prototype/node_modules").exists())
        marker = json.loads((self.output / "prototype/deployment.json").read_text())
        self.assertEqual(marker, {"commit": "abc123", "sample_only": True})
        manifest = json.loads((self.output / "prototype/manifest.webmanifest").read_text())
        self.assertEqual(manifest["start_url"], "./")
        self.assertEqual(manifest["scope"], "./")

    def test_bad_live_response_cannot_publish_empty_edition(self):
        self.live.write_text("<html>not the current edition</html>")
        with self.assertRaises(ValueError):
            self.build()
        self.assertFalse(self.output.exists())

    def test_refuses_overwriting_existing_directory(self):
        self.output.mkdir()
        sentinel = self.output / "user-file"
        sentinel.write_text("keep")
        with self.assertRaises(ValueError):
            self.build()
        self.assertEqual(sentinel.read_text(), "keep")


if __name__ == "__main__":
    unittest.main(verbosity=2)
