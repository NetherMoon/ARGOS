"""Runtime requirements are mandatory; developer tools are optional to doctor."""

from importlib import metadata

RUNTIME_PACKAGES = (
    "numpy",
    "pandas",
    "scipy",
    "torch",
    "PyYAML",
    "scikit-learn",
    "matplotlib",
    "psutil",
    "tqdm",
)
DEVELOPMENT_PACKAGES = ("pytest", "ruff")


def package_versions() -> dict[str, str]:
    result = {name: metadata.version(name) for name in RUNTIME_PACKAGES}
    for name in DEVELOPMENT_PACKAGES:
        try:
            result[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            result[name] = "NOT_INSTALLED"
    return result
