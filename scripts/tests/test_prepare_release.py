import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location(
    "prepare_release", Path(__file__).resolve().parents[1] / "prepare_release.py"
)
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_notes_and_state_are_private(self):
        for name in (
            "activity.md", "AGENTS.md", "EmOtIoNs.MD", "WORK.md",
            "backend/.env", "backend/uploads/a.mp3", "backend/results/a.json",
            "tribev2/.git/config", "backend/references/audio.json",
        ):
            self.assertTrue(release.is_private(Path(name)), name)
        self.assertFalse(release.is_private(Path("backend/.env.example")))
        self.assertFalse(release.is_private(Path("backend/app/models/schemas.py")))

    def test_real_manifest_contains_only_source_and_asset_setup(self):
        paths = release.release_files(release.ROOT)
        self.assertIn(Path("backend/app/main.py"), paths)
        self.assertIn(Path("backend/app/models/database.py"), paths)
        self.assertIn(Path("backend/app/models/schemas.py"), paths)
        self.assertIn(Path("tribev2/LICENSE"), paths)
        self.assertIn(Path("backend/scripts/prepare_assets.py"), paths)
        self.assertIn(Path("frontend/public/.gitkeep"), paths)
        self.assertNotIn(Path("backend/static/atlas/hcp_atlas.json"), paths)
        self.assertTrue(all(path.suffix != ".gii" for path in paths))
        self.assertNotIn(Path("backend/neurolens.db"), paths)
        self.assertTrue(all(not release.is_private(path) for path in paths))

    def test_credential_findings_never_echo_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            secret = "hf_" + "x" * 32
            (root / "example.py").write_text(f'token = "{secret}"')
            with self.assertRaises(ValueError) as error:
                release.check_sources(root, [Path("example.py")])
            self.assertNotIn(secret, str(error.exception))
            self.assertIn("example.py", str(error.exception))


if __name__ == "__main__":
    unittest.main()
