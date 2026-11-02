"""The dependency lists must agree with each other.

requirements*.txt is what CI and the README install; pyproject.toml is what
`pip install .` installs. They were maintained by hand in two places and drifted
(playwright was a runtime requirement but only a pyproject extra), so the two
are compared here instead of trusted.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

tomllib = pytest.importorskip("tomllib")  # Python 3.10 has no stdlib TOML parser


def normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def specs(text: str) -> dict[str, str]:
    """Requirement lines -> {normalised name: version specifier}."""
    found = {}
    for line in text.splitlines():
        line = line.split("#")[0].strip()
        if not line or line.startswith("-"):
            continue
        name, _, spec = re.split(r"(==|>=|<=|~=|>|<)", line, maxsplit=1)
        found[normalise(name.strip())] = (
            line[len(name.strip()) :].strip() if spec else ""
        )
    return found


def requirements(path: Path) -> dict[str, str]:
    """A requirements file, with any `-r other.txt` include merged in."""
    found = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.split("#")[0].strip()
        if stripped.startswith("-r "):
            found |= requirements((path.parent / stripped[3:].strip()).resolve())
        elif stripped:
            found |= specs(stripped)
    return found


def pyproject_groups() -> dict[str, dict[str, str]]:
    data = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    project = data["project"]
    groups = {"dependencies": specs("\n".join(project["dependencies"]))}
    for extra, lines in project.get("optional-dependencies", {}).items():
        groups[extra] = specs("\n".join(lines))
    return groups


RUNTIME = pytest.mark.parametrize("name", sorted(requirements(ROOT / "requirements.txt")))
DEV = pytest.mark.parametrize(
    "name",
    sorted(
        set(requirements(ROOT / "requirements-dev.txt"))
        - set(requirements(ROOT / "requirements.txt"))
    ),
)


@RUNTIME
def test_runtime_requirements_are_installed_by_pip_install(name):
    groups = pyproject_groups()
    assert name in groups["dependencies"], (
        f"{name} is in requirements.txt but not in pyproject's core dependencies, "
        "so `pip install .` ships the app without it"
    )
    assert groups["dependencies"][name] == requirements(ROOT / "requirements.txt")[name]


@DEV
def test_dev_requirements_have_one_declared_home(name):
    groups = pyproject_groups()
    homes = [
        group
        for group in groups
        if group != "dependencies" and name in groups[group]
    ]
    assert homes, f"{name} is in requirements-dev.txt but in no pyproject extra"
    allowed = {groups[group][name] for group in homes} | {
        groups["dependencies"].get(name)
    }
    assert requirements(ROOT / "requirements-dev.txt")[name] in allowed, (
        f"{name} is pinned differently in requirements-dev.txt than in {homes}"
    )
