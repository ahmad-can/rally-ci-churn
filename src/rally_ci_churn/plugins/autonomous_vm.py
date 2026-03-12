"""Autonomous VM benchmark scenario."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from importlib import resources
from ssl import SSLContext
import ssl
import uuid

from rally import exceptions as rally_exceptions
from rally.task import atomic
from rally.task import types
from rally.task import validation

from rally_openstack.common import consts
from rally_openstack.task import scenario
from rally_openstack.task.scenarios.nova import utils as nova_utils

from rally_ci_churn.results import build_metadata_output
from rally_ci_churn.results import build_stage_output
from rally_ci_churn.results import parse_console_result


POLL_INTERVAL_SECONDS = 2.0


@types.convert(image={"type": "glance_image"}, flavor={"type": "nova_flavor"})
@validation.add("required_services", services=[consts.Service.NOVA])
@validation.add("image_valid_on_flavor", flavor_param="flavor", image_param="image")
@validation.add("required_platform", platform="openstack", users=True)
@scenario.configure(
    name="CIChurn.boot_autonomous_vm",
    platform="openstack",
    context={"cleanup@openstack": ["nova"], "network@openstack": {}},
)
class BootAutonomousVM(nova_utils.NovaScenario):
    """Boot an autonomous cloud-init runner, wait for SHUTOFF, then delete."""

    @atomic.action_timer("vm.wait_for_shutdown")
    def _wait_for_shutdown(self, server, timeout_seconds: int):
        start = time.monotonic()
        while True:
            server = self._show_server(server)
            if server.status == "SHUTOFF":
                return server
            if server.status == "ERROR":
                raise rally_exceptions.ScriptError(
                    message=f"Server {server.id} entered ERROR state before shutdown"
                )
            if timeout_seconds > 0 and (time.monotonic() - start) >= timeout_seconds:
                raise rally_exceptions.TimeoutException(
                    timeout=timeout_seconds,
                    resource_type="server",
                    resource_name=server.name,
                    resource_id=server.id,
                    desired_status="SHUTOFF",
                    resource_status=server.status,
                )
            time.sleep(POLL_INTERVAL_SECONDS)

    def _build_user_data(self, payload: dict[str, object], swift_cacert_b64: str) -> str:
        runner_source = resources.files("rally_ci_churn.guest").joinpath("runner_main.py").read_text(encoding="utf-8")
        runner_b64 = base64.b64encode(runner_source.encode("utf-8")).decode("ascii")
        payload_b64 = base64.b64encode(json.dumps(payload, sort_keys=True).encode("utf-8")).decode("ascii")
        lines = [
            "#cloud-config",
            "write_files:",
            "  - path: /opt/rally-ci/runner_main.py",
            '    permissions: "0755"',
            "    encoding: b64",
            f"    content: {runner_b64}",
            "  - path: /opt/rally-ci/config.json",
            '    permissions: "0644"',
            "    encoding: b64",
            f"    content: {payload_b64}",
        ]
        if swift_cacert_b64:
            lines.extend(
                [
                    "  - path: /etc/ssl/certs/rally-ci-swift-ca.pem",
                    '    permissions: "0644"',
                    "    encoding: b64",
                    f"    content: {swift_cacert_b64}",
                ]
            )
        lines.extend(
            [
                "runcmd:",
                "  - [ cloud-init-per, once, rally-ci-runner, /bin/bash, -lc, \"python3 /opt/rally-ci/runner_main.py /opt/rally-ci/config.json > >(tee -a /var/log/rally-ci-runner.log /dev/console) 2>&1 || true; sync; (systemctl poweroff --force --force || poweroff -f || shutdown -P now)\" ]",
            ]
        )
        return "\n".join(lines) + "\n"

    def _build_ssl_context(self, swift_cacert_b64: str) -> SSLContext:
        if not swift_cacert_b64:
            return ssl.create_default_context()
        ca_data = base64.b64decode(swift_cacert_b64.encode("ascii")).decode("utf-8")
        return ssl.create_default_context(cadata=ca_data)

    def _request_json(self, method: str, url: str, headers: dict[str, str], context: SSLContext, data: bytes | None = None):
        request = urllib.request.Request(url=url, method=method, headers=headers, data=data)
        with urllib.request.urlopen(request, context=context) as response:
            body = response.read()
            return response, json.loads(body.decode("utf-8")) if body else {}

    def _normalize_auth_url(self, auth_url: str) -> str:
        auth_url = auth_url.rstrip("/")
        if auth_url.endswith("/v3"):
            return auth_url + "/auth/tokens"
        return auth_url + "/v3/auth/tokens"

    def _authenticate_swift(
        self,
        swift_auth_url: str,
        swift_username: str,
        swift_password: str,
        swift_project_name: str,
        swift_user_domain_name: str,
        swift_project_domain_name: str,
        swift_interface: str,
        swift_region_name: str,
        context: SSLContext,
    ) -> tuple[str, str]:
        auth = {
            "auth": {
                "identity": {
                    "methods": ["password"],
                    "password": {
                        "user": {
                            "name": swift_username,
                            "password": swift_password,
                            "domain": {"name": swift_user_domain_name},
                        }
                    },
                },
                "scope": {
                    "project": {
                        "name": swift_project_name,
                        "domain": {"name": swift_project_domain_name},
                    }
                },
            }
        }
        response, body = self._request_json(
            "POST",
            self._normalize_auth_url(swift_auth_url),
            {"Content-Type": "application/json"},
            context,
            json.dumps(auth).encode("utf-8"),
        )
        token = response.headers.get("X-Subject-Token")
        if not token:
            raise rally_exceptions.ScriptError(message="Keystone response did not include X-Subject-Token")
        for service in body.get("token", {}).get("catalog", []):
            if service.get("type") != "object-store":
                continue
            for endpoint in service.get("endpoints", []):
                if endpoint.get("interface") != swift_interface:
                    continue
                if swift_region_name and endpoint.get("region") != swift_region_name:
                    continue
                return token, endpoint["url"].rstrip("/")
        raise rally_exceptions.ScriptError(message="Unable to find a Swift endpoint in Keystone catalog")

    def _read_swift_object(
        self,
        endpoint: str,
        container: str,
        object_name: str,
        token: str,
        context: SSLContext,
    ) -> dict[str, object] | None:
        object_url = endpoint + "/" + "/".join(
            [
                urllib.parse.quote(container, safe=""),
                urllib.parse.quote(object_name, safe=""),
            ]
        )
        request = urllib.request.Request(
            url=object_url,
            method="GET",
            headers={"X-Auth-Token": token},
        )
        try:
            with urllib.request.urlopen(request, context=context) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code == 404:
                return None
            raise

    @atomic.action_timer("swift.wait_for_result")
    def _wait_for_result_object(
        self,
        endpoint: str,
        container: str,
        object_name: str,
        token: str,
        context: SSLContext,
        timeout_seconds: int,
    ) -> dict[str, object] | None:
        deadline = time.monotonic() + timeout_seconds
        while time.monotonic() < deadline:
            result = self._read_swift_object(endpoint, container, object_name, token, context)
            if result:
                return result
            time.sleep(2.0)
        return None

    def run(
        self,
        image,
        flavor,
        workload_profile,
        artifact_container,
        swift_auth_url,
        swift_username,
        swift_password,
        swift_project_name,
        swift_user_domain_name,
        swift_project_domain_name,
        timeout_seconds=3600,
        timeout_mode="fail",
        artifact_ttl_seconds=0,
        swift_interface="public",
        swift_region_name="",
        swift_cacert_b64="",
        workload_params=None,
        console_log_length=400,
        force_delete=False,
        wave=0,
        **kwargs,
    ):
        workload_params = workload_params or {}
        result_object_name = f"results/{uuid.uuid4().hex}.json"
        payload = {
            "scenario_name": "CIChurn.boot_autonomous_vm",
            "wave": wave,
            "iteration": self.context.get("iteration", 0),
            "workload_profile": workload_profile,
            "workload_params": workload_params,
            "artifact_container": artifact_container,
            "artifact_ttl_seconds": artifact_ttl_seconds,
            "swift_auth_url": swift_auth_url,
            "swift_username": swift_username,
            "swift_password": swift_password,
            "swift_project_name": swift_project_name,
            "swift_user_domain_name": swift_user_domain_name,
            "swift_project_domain_name": swift_project_domain_name,
            "swift_interface": swift_interface,
            "swift_region_name": swift_region_name,
            "swift_cacert": "/etc/ssl/certs/rally-ci-swift-ca.pem" if swift_cacert_b64 else "",
            "result_object_name": result_object_name,
        }
        kwargs["userdata"] = self._build_user_data(payload, swift_cacert_b64)

        server = self._boot_server(image, flavor, auto_assign_nic=True, **kwargs)
        console_output = ""
        timed_out = False
        result = None
        try:
            try:
                self._wait_for_shutdown(server, int(timeout_seconds))
            except rally_exceptions.TimeoutException:
                timed_out = True
                if timeout_mode not in ("fail", "soft"):
                    raise rally_exceptions.ScriptError(
                        message=f"Unsupported timeout_mode: {timeout_mode}"
                    )
            try:
                console_output = self._get_server_console_output(server, length=console_log_length)
            except Exception:  # noqa: BLE001
                console_output = ""
            result = parse_console_result(console_output)
            if not result:
                context = self._build_ssl_context(swift_cacert_b64)
                token, endpoint = self._authenticate_swift(
                    swift_auth_url,
                    swift_username,
                    swift_password,
                    swift_project_name,
                    swift_user_domain_name,
                    swift_project_domain_name,
                    swift_interface,
                    swift_region_name,
                    context,
                )
                result = self._wait_for_result_object(
                    endpoint,
                    artifact_container,
                    result_object_name,
                    token,
                    context,
                    30,
                )
            if result:
                if timed_out:
                    result["timeout"] = True
                    result["status"] = "timeout"
                self.add_output(complete=build_metadata_output(result))
                self.add_output(complete=build_stage_output(result))
                if result.get("status") == "error":
                    raise rally_exceptions.ScriptError(
                        message=str(result.get("diagnostics", {}).get("error", "Guest benchmark failed"))
                    )
            elif not timed_out:
                raise rally_exceptions.ScriptError(
                    message="Guest completed without emitting a structured result payload"
                )
            if timed_out and timeout_mode == "fail":
                raise rally_exceptions.ScriptError(
                    message=f"Guest did not reach SHUTOFF within {timeout_seconds} seconds"
                )
        finally:
            self._delete_server(server, force=force_delete)
