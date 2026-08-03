import pathlib
import re
import unittest


ROOT = pathlib.Path(__file__).resolve().parents[2]


class AwsBootContractTest(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def test_service_waits_for_cloud_init_and_loads_deployment_overrides_last(self) -> None:
        service = self.read("aws/boot/prefer-boot.service")

        self.assertRegex(service, r"(?m)^After=.*\bcloud-final\.service\b")
        self.assertRegex(service, r"(?m)^Requires=.*\bcloud-final\.service\b")
        self.assertRegex(service, r"(?m)^WantedBy=cloud-init\.target$")
        self.assertNotRegex(service, r"(?m)^WantedBy=multi-user\.target$")

        defaults = "EnvironmentFile=/opt/prefer/prefer-boot.env"
        deployment = "EnvironmentFile=-/opt/prefer/deployment.env"
        self.assertIn(defaults, service)
        self.assertIn(deployment, service)
        self.assertLess(service.index(defaults), service.index(deployment))

    def test_baked_router_default_loads_only_one_model(self) -> None:
        defaults = self.read("aws/boot/prefer-boot.env")
        self.assertRegex(defaults, r"(?m)^LLAMA_ARG_MODELS_MAX=1$")

    def test_cdk_writes_deployment_file_without_controlling_the_service(self) -> None:
        stack = self.read("aws/cdk/lib/prefer-stack.ts")

        self.assertIn("cat > /opt/prefer/deployment.env.tmp", stack)
        self.assertIn("chmod 0600 /opt/prefer/deployment.env.tmp", stack)
        self.assertIn("mv /opt/prefer/deployment.env.tmp /opt/prefer/deployment.env", stack)
        self.assertIn("'LLAMA_ARG_MODELS_MAX=1'", stack)
        self.assertIn("`AWS_REGION=${cdk.Aws.REGION}`", stack)
        self.assertNotIn(">> /opt/prefer/prefer-boot.env", stack)
        self.assertNotIn("systemctl restart prefer-boot.service", stack)

    def test_container_runner_passes_the_router_limit(self) -> None:
        runner = self.read("aws/boot/20-run-container.sh")
        passthrough = re.search(r"for v in (?P<variables>[^;]+); do", runner)
        self.assertIsNotNone(passthrough)
        self.assertIn("LLAMA_ARG_MODELS_MAX", passthrough.group("variables"))


if __name__ == "__main__":
    unittest.main()
