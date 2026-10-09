"""Check named Python function documentation and types without importing hardware.

Run from anywhere with Python 3.11: python3 scripts/check_learning_contracts.py.
This structural check does not establish that the explanations or types are
semantically correct; review and behavior tests are still required.
"""

# Keep annotations available to editors without evaluating them at definition time.
from __future__ import annotations

# Inspect syntax rather than importing OpenCV, NumPy or sensor-driver modules.
import ast

# Resolve source paths relative to this script, not the caller's working directory.
from pathlib import Path

# Report an ordinary process exit code when the check fails.
import sys


def check_file(path: Path) -> tuple[int, list[str]]:
    """Check function contracts in one Python file using its syntax tree.

    Args:
        path (Path): Existing Python source, test or project-check script.

    Returns:
        tuple[int, list[str]]: Named-function count and human-readable violations.
            Raises SyntaxError or OSError if the file cannot be parsed/read.
    """
    # Reading/parsing does not execute module imports or touch physical hardware.
    tree = ast.parse(path.read_text(), filename=str(path))
    # Collect all failures so one check can explain every missing contract.
    errors: list[str] = []
    # Track coverage without relying on a hard-coded expected function count.
    count = 0
    # Include nested callbacks and test doubles, not only top-level functions.
    for node in ast.walk(tree):
        # Anonymous callbacks cannot expose the same named/docstring contract.
        if isinstance(node, ast.Lambda):
            # Ask the author to provide a named, documented callback instead.
            errors.append(
                f"{path}:{node.lineno}: replace anonymous callback with a documented function"
            )
        # Classes and ordinary statements have no function-parameter contract.
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Continue to the next syntax node without importing anything.
            continue
        # Count each real function definition exactly once.
        count += 1
        # Include the source line to make corrections easy in an editor.
        location = f"{path}:{node.lineno}: {node.name}"
        # None is also an explicit return contract; do not leave it implicit.
        if node.returns is None:
            # Keep this failure alongside any missing parameter/docstring failures.
            errors.append(f"{location}: missing return annotation")
        # Ordinary, positional-only and keyword-only arguments all need types.
        arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
        # Variadic callbacks still need a contract for each accepted extra value.
        arguments += [
            argument
            for argument in (node.args.vararg, node.args.kwarg)
            if argument is not None
        ]
        # Self/cls are understood from the enclosing class, as agreed in the plan.
        for argument in arguments:
            # Require every other explicitly accepted parameter to declare its type.
            if argument.arg not in ("self", "cls") and argument.annotation is None:
                # Name the exact parameter rather than reporting only a file failure.
                errors.append(f"{location}: missing type for {argument.arg}")
        # A missing docstring becomes an empty string for the checks below.
        description = ast.get_docstring(node) or ""
        # Both no-argument and returning-None functions still explain their contract.
        if (
            not description
            or "Args:" not in description
            or "Returns:" not in description
        ):
            # Require purpose plus the two explicit data-boundary sections.
            errors.append(
                f"{location}: docstring needs a description, Args: and Returns:"
            )
    # Let main combine results across source, tests and this check script.
    return count, errors


def main() -> int:
    """Audit first-party Python contracts without running the application.

    Args:
        None; source paths are resolved from this script's repository location.

    Returns:
        int: Zero when all named functions have contracts, otherwise one.
    """
    # The script lives one directory below the repository root.
    root = Path(__file__).resolve().parents[1]
    # Include the check itself so maintenance scripts follow the same convention.
    paths = (
        sorted((root / "src").rglob("*.py"))
        + sorted((root / "tests").rglob("*.py"))
        + sorted((root / "scripts").glob("*.py"))
    )
    # Accumulate coverage independently of test pass/fail results.
    count = 0
    # Delay failing until every file has had a chance to contribute diagnostics.
    errors: list[str] = []
    # Inspect each file without importing its optional runtime dependencies.
    for path in paths:
        # Parse and collect the per-file function contract findings.
        file_count, file_errors = check_file(path)
        # Add this file's named definitions to the total.
        count += file_count
        # Retain all actionable failures in deterministic file order.
        errors.extend(file_errors)
    # A present-but-invalid contract needs review just as a missing one does.
    if errors:
        # Show one diagnostic per line on stderr for editor/terminal readability.
        print("\n".join(errors), file=sys.stderr)
        # Return failure without modifying source or installing dependencies.
        return 1
    # Coverage is structural; no claim about Pi hardware correctness is implied.
    print(
        f"Documented and annotated {count} named Python functions across {len(paths)} files."
    )
    # Allow callers to combine this check with unit tests and shell syntax checks.
    return 0


# Importing this script for inspection must not run the audit automatically.
if __name__ == "__main__":
    # Propagate the audit status to the invoking shell.
    raise SystemExit(main())
