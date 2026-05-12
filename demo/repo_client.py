#!/usr/bin/env python3
"""Small command-line demo client for artifact repository APIs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import requests


def get_token(base_url: str, username: str, password: str) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/api/auth/token/",
        data={"username": username, "password": password},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()["token"]


def create_repository(base_url: str, token: str, name: str, repo_type: str, mode: str, remote_url: str | None):
    payload = {"name": name, "type": repo_type, "mode": mode}
    if remote_url:
        payload["remote_url"] = remote_url
    response = requests.post(
        f"{base_url.rstrip('/')}/api/repositories/",
        headers={"Authorization": f"Token {token}"},
        json=payload,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def upload_artifact(base_url: str, token: str, repository_id: int, file_path: str):
    with Path(file_path).open("rb") as handle:
        response = requests.post(
            f"{base_url.rstrip('/')}/api/artifacts/upload/",
            headers={"Authorization": f"Token {token}"},
            files={"file": (Path(file_path).name, handle)},
            data={"repository": str(repository_id)},
            timeout=60,
        )
    response.raise_for_status()
    return response.json()


def list_artifacts(base_url: str, token: str):
    response = requests.get(
        f"{base_url.rstrip('/')}/api/artifacts/",
        headers={"Authorization": f"Token {token}"},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def main():
    parser = argparse.ArgumentParser(description="Artifact repository demo client")
    parser.add_argument("--base-url", default="http://localhost:8000")
    sub = parser.add_subparsers(dest="cmd", required=True)

    token_cmd = sub.add_parser("token")
    token_cmd.add_argument("--username", required=True)
    token_cmd.add_argument("--password", required=True)

    create_cmd = sub.add_parser("create-repo")
    create_cmd.add_argument("--token", required=True)
    create_cmd.add_argument("--name", required=True)
    create_cmd.add_argument("--type", required=True, choices=["deb", "rpm", "pypi", "msi", "generic"])
    create_cmd.add_argument("--mode", default="local", choices=["local", "remote", "virtual"])
    create_cmd.add_argument("--remote-url")

    upload_cmd = sub.add_parser("upload")
    upload_cmd.add_argument("--token", required=True)
    upload_cmd.add_argument("--repository-id", required=True, type=int)
    upload_cmd.add_argument("--file", required=True)

    list_cmd = sub.add_parser("list-artifacts")
    list_cmd.add_argument("--token", required=True)

    args = parser.parse_args()
    if args.cmd == "token":
        print(get_token(args.base_url, args.username, args.password))
    elif args.cmd == "create-repo":
        data = create_repository(args.base_url, args.token, args.name, args.type, args.mode, args.remote_url)
        print(json.dumps(data, indent=2))
    elif args.cmd == "upload":
        data = upload_artifact(args.base_url, args.token, args.repository_id, args.file)
        print(json.dumps(data, indent=2))
    elif args.cmd == "list-artifacts":
        data = list_artifacts(args.base_url, args.token)
        print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
