#!/usr/bin/env python3
"""Windows 11 software inventory collector.

Creates a JSON report named:
    software_inventory_<host>-<date>-<time>.json
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as dt
import json
import os
import platform
import subprocess
import sys
from typing import Any, Dict, List, Optional


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect Windows system and software inventory."
    )
    parser.add_argument(
        "--admin",
        action="store_true",
        help="Request administrative privileges (UAC prompt).",
    )
    parser.add_argument(
        "--elevated-child",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    return parser.parse_args()


def is_windows() -> bool:
    return sys.platform.startswith("win")


def is_admin() -> bool:
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def rerun_as_admin() -> bool:
    quoted_args = [f'"{arg}"' if " " in arg else arg for arg in sys.argv[1:]]
    if "--elevated-child" not in quoted_args:
        quoted_args.append("--elevated-child")
    params = " ".join(quoted_args)
    exe = sys.executable
    script = os.path.abspath(sys.argv[0])
    command = f'"{script}" {params}'.strip()
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", exe, command, None, 1
    )
    return result > 32


def run_powershell_json(command: str) -> List[Dict[str, Any]]:
    ps_command = (
        f"$ErrorActionPreference='SilentlyContinue'; {command} | ConvertTo-Json -Depth 6"
    )
    completed = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps_command],
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        return []
    raw = completed.stdout.strip()
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        return [data]
    return []


def get_general_system_information() -> Dict[str, Any]:
    return {
        "hostname": platform.node(),
        "os_name": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
        "is_admin": is_admin(),
        "current_user": os.getlogin() if hasattr(os, "getlogin") else None,
        "generated_at_utc": dt.datetime.utcnow().isoformat() + "Z",
    }


def get_windows_patch_level() -> Dict[str, Any]:
    import winreg  # pylint: disable=import-outside-toplevel

    values: Dict[str, Optional[str]] = {
        "product_name": None,
        "display_version": None,
        "current_build": None,
        "ubr": None,
        "release_id": None,
    }
    try:
        with winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        ) as key:
            for reg_name in [
                "ProductName",
                "DisplayVersion",
                "CurrentBuild",
                "UBR",
                "ReleaseId",
            ]:
                try:
                    reg_value, _ = winreg.QueryValueEx(key, reg_name)
                except OSError:
                    reg_value = None
                values_map = {
                    "ProductName": "product_name",
                    "DisplayVersion": "display_version",
                    "CurrentBuild": "current_build",
                    "UBR": "ubr",
                    "ReleaseId": "release_id",
                }
                values[values_map[reg_name]] = reg_value
    except OSError:
        pass

    latest_hotfix = run_powershell_json(
        (
            "Get-HotFix | Sort-Object InstalledOn -Descending | "
            "Select-Object -First 1 HotFixID, Description, InstalledOn"
        )
    )
    values["latest_hotfix"] = latest_hotfix[0] if latest_hotfix else None
    return values


def get_installed_security_updates() -> List[Dict[str, Any]]:
    updates = run_powershell_json(
        (
            "Get-HotFix | Where-Object { $_.Description -match 'Security' } | "
            "Select-Object HotFixID, Description, InstalledBy, InstalledOn"
        )
    )
    normalized: List[Dict[str, Any]] = []
    for item in updates:
        normalized.append(
            {
                "hotfix_id": item.get("HotFixID"),
                "description": item.get("Description"),
                "installed_by": item.get("InstalledBy"),
                "installed_on": str(item.get("InstalledOn"))
                if item.get("InstalledOn") is not None
                else None,
            }
        )
    return normalized


def read_uninstall_key(root: Any, path: str) -> List[Dict[str, Any]]:
    import winreg  # pylint: disable=import-outside-toplevel

    results: List[Dict[str, Any]] = []
    try:
        with winreg.OpenKey(root, path) as uninstall_key:
            subkey_count, _, _ = winreg.QueryInfoKey(uninstall_key)
            for index in range(subkey_count):
                try:
                    subkey_name = winreg.EnumKey(uninstall_key, index)
                    with winreg.OpenKey(uninstall_key, subkey_name) as app_key:
                        display_name = _query_reg_value(app_key, "DisplayName")
                        if not display_name:
                            continue
                        entry = {
                            "name": display_name,
                            "version": _query_reg_value(app_key, "DisplayVersion"),
                            "publisher": _query_reg_value(app_key, "Publisher"),
                            "install_date": _query_reg_value(app_key, "InstallDate"),
                            "install_location": _query_reg_value(
                                app_key, "InstallLocation"
                            ),
                            "uninstall_string": _query_reg_value(
                                app_key, "UninstallString"
                            ),
                            "registry_key": f"{path}\\{subkey_name}",
                        }
                        results.append(entry)
                except OSError:
                    continue
    except OSError:
        return []
    return results


def _query_reg_value(reg_key: Any, value_name: str) -> Optional[Any]:
    import winreg  # pylint: disable=import-outside-toplevel,unused-import

    try:
        value, _ = winreg.QueryValueEx(reg_key, value_name)
        return value
    except OSError:
        return None


def get_installed_software_all_users() -> List[Dict[str, Any]]:
    import winreg  # pylint: disable=import-outside-toplevel

    paths = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    ]
    software: List[Dict[str, Any]] = []
    for path in paths:
        software.extend(read_uninstall_key(winreg.HKEY_LOCAL_MACHINE, path))
    return _dedupe_software(software)


def get_local_users() -> List[Dict[str, str]]:
    users = run_powershell_json(
        "Get-CimInstance Win32_UserAccount -Filter \"LocalAccount='True'\" | "
        "Select-Object Name, SID, Disabled, Lockout"
    )
    normalized: List[Dict[str, str]] = []
    for user in users:
        sid = user.get("SID")
        name = user.get("Name")
        if sid and name:
            normalized.append(
                {
                    "name": str(name),
                    "sid": str(sid),
                    "disabled": str(user.get("Disabled")),
                    "lockout": str(user.get("Lockout")),
                }
            )
    return normalized


def get_installed_software_per_local_user(
    can_enumerate_all_users: bool,
) -> Dict[str, Any]:
    import winreg  # pylint: disable=import-outside-toplevel

    current_user = os.environ.get("USERNAME", "current_user")
    result: Dict[str, Any] = {}

    if not can_enumerate_all_users:
        current_entries = read_uninstall_key(
            winreg.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        result[current_user] = _dedupe_software(current_entries)
        return result

    local_users = get_local_users()
    for user in local_users:
        sid = user["sid"]
        user_entries = read_uninstall_key(
            winreg.HKEY_USERS,
            rf"{sid}\Software\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        wow_entries = read_uninstall_key(
            winreg.HKEY_USERS,
            rf"{sid}\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
        )
        if user_entries or wow_entries:
            result[user["name"]] = _dedupe_software(user_entries + wow_entries)
        else:
            result[user["name"]] = {
                "status": "no_visible_per_user_registry_data",
                "note": (
                    "User hive may not be loaded. Sign in as that user or run with "
                    "appropriate rights to access additional per-user entries."
                ),
                "sid": sid,
            }
    return result


def _dedupe_software(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for item in items:
        key = (
            str(item.get("name", "")).strip().lower(),
            str(item.get("version", "")).strip().lower(),
            str(item.get("publisher", "")).strip().lower(),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    deduped.sort(key=lambda x: str(x.get("name", "")).lower())
    return deduped


def build_report(can_enumerate_all_users: bool) -> Dict[str, Any]:
    return {
        "general_system_information": get_general_system_information(),
        "installed_security_updates": get_installed_security_updates(),
        "windows_patch_level": get_windows_patch_level(),
        "installed_software_for_all_users": get_installed_software_all_users(),
        "installed_software_for_each_local_user": get_installed_software_per_local_user(
            can_enumerate_all_users=can_enumerate_all_users
        ),
    }


def output_filename(hostname: str) -> str:
    now = dt.datetime.now()
    date_part = now.strftime("%Y%m%d")
    time_part = now.strftime("%H%M%S")
    safe_host = hostname.replace(" ", "_")
    return f"software_inventory_{safe_host}-{date_part}-{time_part}.json"


def main() -> int:
    args = parse_args()

    if not is_windows():
        print("This script only runs on Windows.")
        return 1

    print(
        "Info: pass --admin to request administrative privileges for broader inventory."
    )

    admin_mode = is_admin()
    if args.admin and not admin_mode and not args.elevated_child:
        print("Administrative mode requested. Triggering UAC prompt...")
        elevated = rerun_as_admin()
        if elevated:
            print("Elevated process started. Exiting non-elevated instance.")
            return 0
        print(
            "UAC elevation was not completed. Continuing without administrative privileges."
        )
    elif args.admin and admin_mode:
        print("Running with administrative privileges.")

    admin_mode = is_admin()
    if not admin_mode:
        print(
            "Running without administrative privileges; only software visible to this user will be reported."
        )

    report = build_report(can_enumerate_all_users=admin_mode)
    host = report["general_system_information"].get("hostname", platform.node())
    filename = output_filename(str(host))

    with open(filename, "w", encoding="utf-8") as json_file:
        json.dump(report, json_file, indent=2, ensure_ascii=True)

    print(f"Inventory report written to: {os.path.abspath(filename)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
