#!/usr/bin/env python3
"""
Sync version from pyproject.toml to package.json

This ensures backend and frontend always have the same version.
Run this script before committing version changes.
"""

import json
import sys
from pathlib import Path

# Colors for terminal output
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
RESET = "\033[0m"


def read_pyproject_version(pyproject_path: Path) -> str:
    """Read version from pyproject.toml"""
    if not pyproject_path.exists():
        print(f"{RED}Error: pyproject.toml not found at {pyproject_path}{RESET}")
        sys.exit(1)

    try:
        # Python 3.11+ has tomllib built-in
        if sys.version_info >= (3, 11):
            import tomllib
        else:
            # Python 3.10 and below need tomli
            try:
                import tomli as tomllib
            except ImportError:
                print(f"{RED}Error: tomli not installed. Run: pip install tomli{RESET}")
                sys.exit(1)

        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
            version = data["project"]["version"]
            return version

    except Exception as e:
        print(f"{RED}Error reading pyproject.toml: {e}{RESET}")
        sys.exit(1)


def update_package_json(package_json_path: Path, version: str) -> bool:
    """Update version in package.json"""
    if not package_json_path.exists():
        print(f"{YELLOW}Warning: package.json not found at {package_json_path}{RESET}")
        print(f"{YELLOW}Skipping frontend version sync{RESET}")
        return False

    try:
        with open(package_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        old_version = data.get("version", "unknown")
        data["version"] = version

        with open(package_json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")  # Add trailing newline

        print(f"{GREEN}✓ Updated package.json: {old_version} → {version}{RESET}")
        return True

    except Exception as e:
        print(f"{RED}Error updating package.json: {e}{RESET}")
        return False


def main():
    # Get project root (parent of scripts/)
    project_root = Path(__file__).parent.parent

    pyproject_path = project_root / "pyproject.toml"
    package_json_path = project_root / "frontend" / "package.json"

    print(f"\n{GREEN}🔄 Syncing version from pyproject.toml...{RESET}\n")

    # Read version from pyproject.toml
    version = read_pyproject_version(pyproject_path)
    print(f"📦 Backend version (pyproject.toml): {GREEN}{version}{RESET}")

    # Update package.json
    success = update_package_json(package_json_path, version)

    if success:
        print(f"\n{GREEN}✅ Version sync complete!{RESET}")
        print(f"{GREEN}   Backend and frontend are now both v{version}{RESET}\n")
        return 0
    else:
        print(f"\n{YELLOW}⚠️  Version sync completed with warnings{RESET}\n")
        return 0


if __name__ == "__main__":
    sys.exit(main())
