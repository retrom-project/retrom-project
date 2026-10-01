"""Workspace Provider commands pass cache ownership and selected checkout inputs."""
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


class ProviderCacheForwardingTests(unittest.TestCase):
    def test_provider_commands_forward_to_baseline_and_named_pfb(self):
        with tempfile.TemporaryDirectory(prefix="provider workspace ") as temporary:
            workspace = Path(temporary)
            shutil.copyfile(WORKSPACE_ROOT / "Makefile", workspace / "Makefile")
            for name in (None, "feature"):
                checkout = workspace / ("project/retrom" if name is None else ".worktree/feature/project/retrom")
                checkout.mkdir(parents=True)
                (checkout / "Makefile").write_text(
                    'runtime-provider-prepare runtime-provider-pin-release runtime-provider-cache-import:\n'
                    '\t@echo "$(CURDIR)|$(RETROM_PROVIDER_CACHE_ROOT)|$(TAG)|$(SOURCE_ROOT)"\n',
                    encoding="utf-8",
                )
                for target in ("runtime-provider-prepare", "runtime-provider-pin-release", "runtime-provider-cache-import"):
                    for custom in (False, True):
                        with self.subTest(pfb=name, target=target, custom=custom):
                            expected = workspace / ("custom cache" if custom else ".cache/runtime-providers")
                            arguments = [] if name is None else [f"PFB={name}"]
                            if custom:
                                arguments.append(f"RETROM_PROVIDER_CACHE_ROOT={expected}")
                            output = subprocess.run(
                                ["make", "--no-print-directory", target, "TAG=v1.0.0", "SOURCE_ROOT=source cache",
                                 *arguments], cwd=workspace, capture_output=True, text=True, check=True,
                            ).stdout.strip()
                            self.assertEqual(output, f"{checkout}|{expected}|v1.0.0|source cache")


if __name__ == "__main__":
    unittest.main()
