"""Exercise the delivery gate against real isolated Git histories and worktrees."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from check_protocol_generations import check


class ProtocolGateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Gate Test")
        self.git("config", "user.email", "gate@example.invalid")
        self.write("provider.ts", "export const providerApiVersion = 1;\nexport interface PlayerRuntimeV1 {}\n")
        self.write("api/provider.json", '{"properties":{"schemaVersion":{"const":1}}}\n')
        self.write("api/v1/provider-module-v1.d.ts", "export type ProviderApiVersionV1 = 1;\n")
        self.write("api/catalog.yaml", "providerApiVersion:\n  type: integer\n  enum:\n    - 1\n")
        self.write("release.json", '{"tag":"v0.58.7"}\n')
        self.git("add", ".")
        self.git("commit", "-qm", "base")
        self.base = self.git("rev-parse", "HEAD").strip()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], text=True)

    def write(self, path, value):
        destination = self.root / path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(value)

    def test_changed_contract_and_new_data_keep_the_existing_identity(self):
        self.write("provider.ts", "export const providerApiVersion = 1;\nexport interface PlayerRuntimeV1 {failure: {code: string}}\n")
        self.write("api/provider.json", '{"properties":{"schemaVersion":{"const":1},"maxFileBytes":{"type":"integer"}},"required":["maxFileBytes"]}\n')
        self.write("release.json", '{"tag":"v0.59.0"}\n')
        self.assertEqual(check(self.root, self.base)["status"], "PASS")

    def test_provider_upgrade_fails_before_commit(self):
        self.write("provider.ts", "export const providerApiVersion = 2;\nexport interface PlayerRuntimeV2 {}\n")
        result = check(self.root, self.base)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual({item["identity"] for item in result["findings"]}, {"field:providerapiversion", "type:PlayerRuntime"})

    def test_committed_upgrade_still_fails_against_the_recorded_base(self):
        self.write("provider.ts", "export const providerApiVersion = 2;\n")
        self.git("add", "provider.ts")
        self.git("commit", "-qm", "upgrade")
        self.assertEqual(check(self.root, self.base)["status"], "FAIL")

    def test_json_schema_constant_upgrade_fails(self):
        self.write("api/provider.json", '{"properties":{"schemaVersion":{"const":2}}}\n')
        self.assertEqual(check(self.root, self.base)["status"], "FAIL")

    def test_prefixed_installer_constant_upgrade_fails(self):
        self.write("installer.py", "SUPPORTED_PROVIDER_API_VERSION = 1\n")
        self.git("add", "installer.py")
        self.git("commit", "-qm", "installer authority")
        base = self.git("rev-parse", "HEAD").strip()
        self.write("installer.py", "SUPPORTED_PROVIDER_API_VERSION = 2\n")
        result = check(self.root, base)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(item["identity"] == "field:providerapiversion" for item in result["findings"]))

    def test_parallel_generation_in_an_enum_or_type_union_fails(self):
        self.write("api/provider.json", '{"properties":{"schemaVersion":{"enum":[1,2]}}}\n')
        self.write("provider.ts", "export type ProviderApiVersionV1 = 1 | 2;\n")
        result = check(self.root, self.base)
        self.assertEqual({item["identity"] for item in result["findings"]}, {"field:schemaversion", "field:providerapiversion"})

    def test_staged_upgrade_cannot_hide_behind_a_corrected_working_file(self):
        self.write("provider.ts", "export const providerApiVersion = 2;\n")
        self.git("add", "provider.ts")
        self.write("provider.ts", "export const providerApiVersion = 1;\n")
        result = check(self.root, self.base)
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual({item["layer"] for item in result["findings"]}, {"index"})

    def test_yaml_enum_upgrade_fails(self):
        self.write("api/catalog.yaml", "providerApiVersion:\n  type: integer\n  enum:\n    - 2\n")
        self.assertEqual(check(self.root, self.base)["status"], "FAIL")

    def test_untracked_parallel_protocol_path_fails(self):
        self.write("api/v2/provider-module-v2.d.ts", "export type ProviderApiVersionV2 = 2;\n")
        result = check(self.root, self.base)
        self.assertEqual(result["status"], "FAIL")
        self.assertTrue(any(item["identity"] == "versioned-file-path" for item in result["findings"]))

    def test_route_upgrade_fails(self):
        self.write("routes.ts", 'router.get("/api/v2/games", handler);\n')
        self.assertEqual(check(self.root, self.base)["status"], "FAIL")

    def test_unchanged_existing_generation_and_unrelated_values_pass(self):
        self.write("existing.ts", "export const schemaVersion = 3;\n")
        self.git("add", "existing.ts")
        self.git("commit", "-qm", "existing unrelated protocol")
        base = self.git("rev-parse", "HEAD").strip()
        self.write("existing.ts", "export const schemaVersion = 3;\nexport const retries = 2;\n")
        self.write("provider.test.ts", "expect(() => load({providerApiVersion: 99})).toThrow();\n")
        self.assertEqual(check(self.root, base)["status"], "PASS")

    def test_new_consumer_of_an_established_package_format_passes(self):
        self.write("dependencies/manifest.go", "const schemaVersion = 8\n")
        self.git("add", "dependencies/manifest.go")
        self.git("commit", "-qm", "existing dependency format")
        base = self.git("rev-parse", "HEAD").strip()
        self.write("dependencies/paired.go", "value := Manifest{SchemaVersion: 8}\n")
        self.assertEqual(check(self.root, base)["status"], "PASS")

    def test_cli_fails_closed_for_invalid_base(self):
        script = Path(__file__).with_name("check_protocol_generations.py")
        result = subprocess.run(["python3", str(script), "--repo", str(self.root), "--base", "absent-base"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('"status": "ERROR"', result.stdout)


if __name__ == "__main__":
    unittest.main()
