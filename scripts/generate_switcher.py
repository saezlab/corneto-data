#!/usr/bin/env python3
"""
Script to generate switcher.json for documentation version switching.
Scans the gh-pages branch and creates version entries based on directories found.
"""

import json
import re
import subprocess
import tempfile
import shutil
import os
from pathlib import Path
from typing import List, Dict, Any, Optional
import argparse


def run_command(cmd: List[str], cwd: str = None) -> str:
    """Run a command and return its output."""
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def clone_gh_pages(repo_url: str, temp_dir: str) -> None:
    """Clone the gh-pages branch to a temporary directory."""
    run_command(
        ["git", "clone", "--branch", "gh-pages", "--single-branch", repo_url, temp_dir]
    )


def get_version_directories(gh_pages_dir: str) -> List[str]:
    """Get all version directories from gh-pages."""
    path = Path(gh_pages_dir)

    # Exclude certain directories that aren't versions
    exclude_dirs = {
        ".git",
        ".jupyter_cache",
        "corneto",
        "docs",
        "jupyter_execute",
        "__pycache__",
    }

    directories = []
    for item in path.iterdir():
        if (
            item.is_dir()
            and item.name not in exclude_dirs
            and not item.name.startswith(".")
        ):
            directories.append(item.name)

    return sorted(directories, key=lambda x: version_sort_key(x))


def version_sort_key(version: str) -> tuple:
    """Create a sort key for versions to order them properly."""
    # Handle special cases first
    if version == "latest":
        return (0, 0, 0, 0, "latest")
    elif version == "main":
        return (0, 0, 0, 1, "main")
    elif version == "dev":
        return (0, 0, 0, 2, "dev")
    elif version == "stable":
        return (0, 0, 0, 3, "stable")

    # Parse semantic versions
    # Remove 'v' prefix if present
    clean_version = version.lstrip("v")

    # Try to parse semantic version
    version_pattern = r"^(\d+)\.(\d+)\.(\d+)(?:[-.](.+))?$"
    match = re.match(version_pattern, clean_version)

    if match:
        major, minor, patch, suffix = match.groups()
        major, minor, patch = int(major), int(minor), int(patch)

        # Handle pre-release suffixes
        suffix_order = 1000  # Default for stable releases
        if suffix:
            if "dev" in suffix:
                suffix_order = 100
            elif "alpha" in suffix:
                suffix_order = 200
            elif "beta" in suffix:
                suffix_order = 300
            elif "rc" in suffix:
                suffix_order = 400

        return (1, major, minor, patch, suffix_order, suffix or "")

    # Fallback for non-semantic versions
    return (2, 0, 0, 0, version)


def get_version_from_index(version_dir: str) -> Optional[str]:
    """Extract the theme_switcher_version_match from index.html."""
    index_path = Path(version_dir) / "index.html"

    if not index_path.exists():
        return None

    try:
        with open(index_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Look for theme_switcher_version_match in the script
        pattern = r"DOCUMENTATION_OPTIONS\.theme_switcher_version_match\s*=\s*['\"]([^'\"]+)['\"]"
        match = re.search(pattern, content)

        if match:
            return match.group(1)
    except Exception as e:
        print(f"Warning: Could not read {index_path}: {e}")

    return None


def create_switcher_entry(
    directory: str, version_match: str, base_url: str
) -> Dict[str, Any]:
    """Create a switcher entry for a version."""
    entry = {
        "name": version_match or directory,
        "version": version_match or directory,
        "url": f"{base_url}/{directory}/",
    }

    # Mark latest/main as preferred
    if version_match in ["latest", "main"] or directory in ["latest", "main"]:
        entry["preferred"] = True

    return entry


def generate_switcher_json(
    repo_url: str, base_url: str, output_file: str = None
) -> str:
    """Generate switcher.json content by scanning gh-pages branch."""

    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Cloning gh-pages branch from {repo_url}...")
        clone_gh_pages(repo_url, temp_dir)

        print("Scanning version directories...")
        directories = get_version_directories(temp_dir)
        print(f"Found directories: {directories}")

        # Create switcher entries by reading version from each index.html
        switcher_data = []
        for directory in directories:
            version_dir_path = os.path.join(temp_dir, directory)
            version_match = get_version_from_index(version_dir_path)

            print(f"Directory '{directory}' -> version_match: '{version_match}'")

            entry = create_switcher_entry(directory, version_match, base_url)
            switcher_data.append(entry)

        # Convert to JSON
        json_content = json.dumps(switcher_data, indent=2)

        # Write to file if specified
        if output_file:
            with open(output_file, "w") as f:
                f.write(json_content)
            print(f"Switcher JSON written to: {output_file}")

        return json_content


def main():
    parser = argparse.ArgumentParser(
        description="Generate switcher.json for documentation versions"
    )
    parser.add_argument(
        "--repo-url",
        required=True,
        help="Repository URL (e.g., https://github.com/user/repo.git)",
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL for docs (e.g., https://user.github.io/repo)",
    )
    parser.add_argument(
        "--output", "-o", help="Output file path (default: print to stdout)"
    )

    args = parser.parse_args()

    try:
        json_content = generate_switcher_json(args.repo_url, args.base_url, args.output)
        if not args.output:
            print(json_content)
    except Exception as e:
        print(f"Error: {e}")
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
