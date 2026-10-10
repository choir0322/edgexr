"""Check named Python function documentation and types without importing hardware.

Run from anywhere with Python 3.11: python3 scripts/check_learning_contracts.py.
This structural check does not establish that the explanations or types are
semantically correct; review and behavior tests are still required.
"""

from __future__ import annotations
import ast
from pathlib import Path
import sys


def check_file(path: Path) -> tuple[int, list[str]]:
    """Check function contracts in one Python file using its syntax tree.

    Args:
        path (Path): Existing Python source, test or project-check script.

    Returns:
        tuple[int, list[str]]: Named-function count and human-readable violations.
            Raises SyntaxError or OSError if the file cannot be parsed/read.
    """
    # Inspect syntax without importing optional hardware libraries. Visit nested
    # functions too, and reject undocumented anonymous callbacks.
    tree = ast.parse(path.read_text(), filename=str(path))
    errors: list[str] = []
    count = 0
    for node in ast.walk(tree):
        if isinstance(node, ast.Lambda):
            errors.append(
                f"{path}:{node.lineno}: replace anonymous callback with a documented function"
            )
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        # Check return and all explicit parameter annotations, including variadic
        # arguments. self/cls are implicitly typed by their owning class.
        count += 1
        location = f"{path}:{node.lineno}: {node.name}"
        if node.returns is None:
            errors.append(f"{location}: missing return annotation")
        arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        arguments += [
            argument
            for argument in (node.args.vararg, node.args.kwarg)
            if argument is not None
        ]
        for argument in arguments:
            if argument.arg not in ("self", "cls") and argument.annotation is None:
                errors.append(f"{location}: missing type for {argument.arg}")

        # Require description sections, not a comment count. Semantic accuracy and
        # helpful task grouping still need human review.
        description = ast.get_docstring(node) or ""
        if (
            not description
            or "Args:" not in description
            or "Returns:" not in description
        ):
            errors.append(
                f"{location}: docstring needs a description, Args: and Returns:"
            )
    return count, errors


def main() -> int:
    """Audit first-party Python contracts without running the application.

    Args:
        None; source paths are resolved from this script's repository location.

    Returns:
        int: Zero when all named functions have contracts, otherwise one.
    """
    # Audit first-party source, tests and Python helpers; aggregate diagnostics
    # so one run reports all missing contracts rather than stopping at the first.
    root = Path(__file__).resolve().parents[1]
    paths = (
        sorted((root / "src").rglob("*.py"))
        + sorted((root / "tests").rglob("*.py"))
        + sorted((root / "scripts").glob("*.py"))
    )
    count = 0
    errors: list[str] = []
    for path in paths:
        file_count, file_errors = check_file(path)
        count += file_count
        errors.extend(file_errors)
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"Documented and annotated {count} named Python functions across {len(paths)} files."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
