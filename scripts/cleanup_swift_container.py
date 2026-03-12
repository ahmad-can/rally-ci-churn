#!/usr/bin/env python3
"""Delete objects from a Swift container and optionally delete the container."""

from __future__ import annotations

import argparse
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request


def normalize_auth_url(auth_url: str) -> str:
    auth_url = auth_url.rstrip("/")
    if auth_url.endswith("/v3"):
        return auth_url + "/auth/tokens"
    return auth_url + "/v3/auth/tokens"


def build_ssl_context(cacert: str) -> ssl.SSLContext:
    if cacert:
        return ssl.create_default_context(cafile=cacert)
    return ssl.create_default_context()


def request_json(method: str, url: str, headers: dict[str, str], data: bytes | None = None):
    request = urllib.request.Request(url=url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(request, context=build_ssl_context("")) as response:
        body = response.read()
        return response, json.loads(body.decode("utf-8")) if body else {}


def authenticate(args) -> tuple[str, str]:
    payload = {
        "auth": {
            "identity": {
                "methods": ["password"],
                "password": {
                    "user": {
                        "name": args.username,
                        "password": args.password,
                        "domain": {"name": args.user_domain_name},
                    }
                },
            },
            "scope": {
                "project": {
                    "name": args.project_name,
                    "domain": {"name": args.project_domain_name},
                }
            },
        }
    }
    request = urllib.request.Request(
        url=normalize_auth_url(args.auth_url),
        method="POST",
        headers={"Content-Type": "application/json"},
        data=json.dumps(payload).encode("utf-8"),
    )
    with urllib.request.urlopen(request, context=build_ssl_context(args.cacert)) as response:
        body = json.loads(response.read().decode("utf-8"))
        token = response.headers.get("X-Subject-Token")
    if not token:
        raise RuntimeError("Keystone response did not include X-Subject-Token")

    for service in body.get("token", {}).get("catalog", []):
        if service.get("type") != "object-store":
            continue
        for endpoint in service.get("endpoints", []):
            if endpoint.get("interface") != args.interface:
                continue
            if args.region_name and endpoint.get("region") != args.region_name:
                continue
            return token, endpoint["url"].rstrip("/")

    raise RuntimeError("Unable to find a Swift endpoint in Keystone catalog")


def swift_request(method: str, url: str, token: str) -> tuple[int, bytes]:
    request = urllib.request.Request(
        url=url,
        method=method,
        headers={"X-Auth-Token": token},
    )
    try:
        with urllib.request.urlopen(request, context=build_ssl_context(args.cacert)) as response:
            return response.getcode(), response.read()
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read()


def list_objects(token: str, endpoint: str, container: str) -> list[str]:
    url = endpoint + "/" + urllib.parse.quote(container, safe="") + "?format=json"
    status, body = swift_request("GET", url, token)
    if status != 200:
        raise RuntimeError(f"Unable to list objects in {container}: {status} {body!r}")
    entries = json.loads(body.decode("utf-8"))
    return [entry["name"] for entry in entries]


def delete_object(token: str, endpoint: str, container: str, name: str) -> None:
    url = endpoint + "/" + "/".join(
        [
            urllib.parse.quote(container, safe=""),
            urllib.parse.quote(name, safe=""),
        ]
    )
    status, body = swift_request("DELETE", url, token)
    if status not in (204, 404):
        raise RuntimeError(f"Unable to delete object {name}: {status} {body!r}")


def delete_container(token: str, endpoint: str, container: str) -> None:
    url = endpoint + "/" + urllib.parse.quote(container, safe="")
    status, body = swift_request("DELETE", url, token)
    if status not in (204, 404):
        raise RuntimeError(f"Unable to delete container {container}: {status} {body!r}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--auth-url", required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--project-name", required=True)
    parser.add_argument("--user-domain-name", default="Default")
    parser.add_argument("--project-domain-name", default="Default")
    parser.add_argument("--region-name", default="")
    parser.add_argument("--interface", default="public")
    parser.add_argument("--cacert", default="")
    parser.add_argument("--container", required=True)
    parser.add_argument("--keep-container", action="store_true")
    return parser.parse_args()


def main() -> int:
    global args
    args = parse_args()
    token, endpoint = authenticate(args)
    names = list_objects(token, endpoint, args.container)

    for name in names:
        delete_object(token, endpoint, args.container, name)

    if not args.keep_container:
        delete_container(token, endpoint, args.container)

    print(f"Deleted {len(names)} object(s) from {args.container}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
