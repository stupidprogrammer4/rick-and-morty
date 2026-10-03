import argparse
import importlib.metadata as metadata
import tomllib
from collections import defaultdict, deque
from pathlib import Path

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name
from packaging.version import Version


def source_dependencies(path: Path):
    project = tomllib.loads((path / "pyproject.toml").read_text())["project"]
    dependencies = list(project.get("dependencies", []))
    for extra, requirements in project.get(
        "optional-dependencies", {}
    ).items():
        for item in requirements:
            requirement = Requirement(item)
            marker = (
                f"({requirement.marker}) and extra == '{extra}'"
                if requirement.marker
                else f"extra == '{extra}'"
            )
            requirement.marker = None
            dependencies.append(f"{requirement}; {marker}")
    return project["version"], dependencies


def resolve(root: Path, directory: str, sources, *, dev=False):
    project = tomllib.loads((root / directory / "pyproject.toml").read_text())[
        "project"
    ]
    contracts = tomllib.loads(
        (root / "packages/contracts/pyproject.toml").read_text()
    )["project"]
    queue = deque(project["dependencies"] + contracts["dependencies"])
    if dev:
        queue.extend(project["optional-dependencies"]["dev"])
    extras = defaultdict(set)
    constraints = defaultdict(set)
    versions = {}
    processed = {}
    urls = {}
    while queue:
        requirement = Requirement(queue.popleft())
        name = canonicalize_name(requirement.name)
        if name == "portal-contracts":
            continue
        constraints[name].add(str(requirement.specifier))
        extras[name].update(requirement.extras)
        if requirement.url:
            if name in urls and urls[name] != requirement.url:
                raise ValueError(f"Conflicting source URLs for {name}")
            urls[name] = requirement.url
        if name in sources:
            version, dependencies = source_dependencies(sources[name])
        else:
            distribution = metadata.distribution(name)
            version = distribution.version
            dependencies = distribution.requires or []
        versions[name] = version
        signature = frozenset(extras[name])
        if processed.get(name) == signature:
            continue
        processed[name] = signature
        for item in dependencies:
            dependency = Requirement(item)
            if dependency.marker and not any(
                dependency.marker.evaluate({"extra": extra})
                for extra in signature | {""}
            ):
                continue
            queue.append(str(dependency))
    for name, version in versions.items():
        for constraint in constraints[name]:
            if constraint and not Requirement(
                name + constraint
            ).specifier.contains(Version(version)):
                raise ValueError(
                    f"Installed {name}=={version} conflicts with {constraint}"
                )
    lines = [
        "# Resolved against the installed Python 3.13 environment.",
        "# CI reinstalls this graph and checks dependencies.",
        "# Framework sources use full commits; no credentials/local paths.",
    ]
    for name, version in sorted(versions.items()):
        suffix = (
            "[" + ",".join(sorted(extras[name])) + "]" if extras[name] else ""
        )
        value = " @ " + urls[name] if name in urls else "==" + version
        lines.append(name + suffix + value)
    filename = "requirements-dev.lock" if dev else "requirements.lock"
    (root / directory / filename).write_text("\n".join(lines) + "\n")
    print(f"{directory}/{filename}: {len(versions)} consistent distributions")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--papilio-source", type=Path)
    parser.add_argument("--tasks-source", type=Path)
    args = parser.parse_args()
    sources = {}
    if args.papilio_source:
        sources["papilio"] = args.papilio_source
    if args.tasks_source:
        sources["papilio-tasks"] = args.tasks_source
    root = Path(__file__).resolve().parents[1]
    resolve(root, "api", sources)
    resolve(root, "bots", sources)
    resolve(root, "api", sources, dev=True)


if __name__ == "__main__":
    main()
