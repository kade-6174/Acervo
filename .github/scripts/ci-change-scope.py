"""文書だけの差分を限定し、それ以外や判定不能な差分では全CIを実行する。"""

import os
import re
import subprocess
from pathlib import Path, PurePosixPath

ROOT_DOCUMENTS = {
    "AGENTS.md",
    "PLAN.md",
    "PROJECT_SPEC.md",
    "README.md",
    "STATUS.md",
    "THIRD_PARTY_NOTICES.md",
}


def documentation_only(paths):
    if not paths:
        return False
    for name in paths:
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts:
            return False
        if name in ROOT_DOCUMENTS:
            continue
        if len(path.parts) >= 2 and path.parts[0] == "docs" and path.suffix == ".md":
            continue
        return False
    return True


def needs_runtime_checks(base, head):
    if not all(re.fullmatch(r"[0-9a-f]{40}", sha or "") for sha in (base, head)):
        return True
    if base == "0" * 40:
        return True
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "--no-renames", "-z", base, head, "--"],
            check=True,
            capture_output=True,
        )
        paths = result.stdout.decode("utf-8").rstrip("\0").split("\0")
        if not documentation_only(paths):
            return True
        # READMEはイメージとPython packageの入力でもある。削除・symlinkは全CIへ。
        return any(Path(name).is_symlink() for name in paths) or not Path("README.md").is_file()
    except (OSError, UnicodeError, subprocess.CalledProcessError):
        return True


if __name__ == "__main__":
    runtime = needs_runtime_checks(os.environ.get("CI_BASE_SHA"), os.environ.get("CI_HEAD_SHA"))
    result = f"runtime={str(runtime).lower()}"
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
        output.write(result + "\n")
    print(result)
