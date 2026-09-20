"""The dock's two styling engines must stay two engines.

`core/styler.py` and `core/mpyy_styler.py` each defined a class named
`MPYYStylerEngine`, and `dock.py` imported both under that one name. A same-name
shadow is not an import error -- the second import simply won -- so nothing
complained while an entire code path silently died. The damage surfaced at a
call site: `gui/actions.py` drives the Ek-1e detail engine with that class's own
keywords, which the surviving class does not accept, so picking the MPYY / e-Plan
level in the dock raised

    TypeError: apply() got an unexpected keyword argument 'field'

No suite reached that branch and no suite read either engine object, so the gate
stayed green through a public release.

These checks are deliberately qgis-free (they parse source, not symbols), so
they run on both runtimes and cannot be skipped for want of a QGIS import. They
pin the wiring rather than the behaviour:

1. no module may import one local name from two different sources;
2. the dock must bind two distinct engine classes, from two distinct modules;
3. every `self.<engine>.<method>(...)` call in the actions must match the
   signature of the class the dock actually binds to that attribute.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

DOCK = ROOT / "dock.py"
ACTIONS = ROOT / "gui" / "actions.py"

# The two engines the dock is expected to own, as source modules. Named on
# purpose: collapsing them back into one is the regression this file exists for.
EXPECTED_ENGINES = {"core.styler", "core.mpyy_styler"}


def _normalize(module: str | None) -> str:
    """`.core.styler` / `planx_mpyy_studio.core.styler` -> `core.styler`."""
    parts = [part for part in (module or "").split(".") if part]
    if parts and parts[0] == "planx_mpyy_studio":
        parts = parts[1:]
    return ".".join(parts)


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _imports(tree: ast.Module) -> dict[str, set[tuple[str, str]]]:
    """Local name -> {(source module, original name)}."""
    found: dict[str, set[tuple[str, str]]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                local = alias.asname or alias.name
                found.setdefault(local, set()).add((_normalize(node.module), alias.name))
    return found


def _bound_attributes(tree: ast.Module) -> dict[str, str]:
    """`self.mpyy_engine = SomeEngine()` -> {"mpyy_engine": "SomeEngine"}."""
    bound: dict[str, str] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
            continue
        target, func = node.targets[0], node.value.func
        if (
            isinstance(target, ast.Attribute)
            and isinstance(target.value, ast.Name)
            and target.value.id == "self"
            and isinstance(func, ast.Name)
        ):
            bound[target.attr] = func.id
    return bound


def _signature(module: str, cls: str, method: str) -> tuple[list[str], int, bool, bool]:
    """(parameter names, required count, takes *args, takes **kwargs)."""
    tree = _parse(ROOT / (module.replace(".", "/") + ".py"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == cls:
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method:
                    args = item.args
                    names = [a.arg for a in args.args if a.arg != "self"]
                    required = len(names) - len(args.defaults)
                    if args.vararg is not None:
                        names.append(args.vararg.arg)
                    return names, required, args.vararg is not None, args.kwarg is not None
    raise AssertionError(f"{module}.{cls}.{method} not found")


def _engine_calls(tree: ast.Module) -> list[tuple[int, str, str, ast.Call]]:
    """Every `self.<attr>.<method>(...)` call, as (line, attr, method, node)."""
    calls = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        inner = node.func.value
        if (
            isinstance(inner, ast.Attribute)
            and isinstance(inner.value, ast.Name)
            and inner.value.id == "self"
        ):
            calls.append((node.lineno, inner.attr, node.func.attr, node))
    return calls


class EngineWiringTest(unittest.TestCase):
    def test_no_module_imports_one_name_from_two_sources(self):
        """A shadowed import is invisible at runtime; catch it statically."""
        offenders = []
        for path in sorted(ROOT.rglob("*.py")):
            if ".git" in path.parts or "__pycache__" in path.parts:
                continue
            for local, sources in _imports(_parse(path)).items():
                if len(sources) > 1:
                    offenders.append(
                        f"{path.relative_to(ROOT)}: {local} <- {sorted(sources)}"
                    )
        self.assertEqual(
            [],
            offenders,
            "a local name is imported from two different modules; the second "
            "import silently wins and the first becomes unreachable:\n  "
            + "\n  ".join(offenders),
        )

    def test_dock_binds_two_distinct_engines(self):
        """Both engines must exist as separate objects, not one overwritten."""
        imports = _imports(_parse(DOCK))
        bound = _bound_attributes(_parse(DOCK))

        engines: dict[str, tuple[str, str]] = {}
        for attr, cls in bound.items():
            if not attr.endswith("_engine") or attr.startswith("_"):
                continue
            sources = imports.get(cls, set())
            self.assertEqual(
                1,
                len(sources),
                f"dock binds self.{attr} = {cls}(), but {cls} is imported "
                f"from {sorted(sources)} -- the binding is ambiguous",
            )
            engines[attr] = next(iter(sources))

        modules = {module for module, _ in engines.values()}
        self.assertTrue(
            EXPECTED_ENGINES <= modules,
            f"the dock no longer owns both styling engines; bound to {modules}",
        )
        self.assertEqual(
            len(engines),
            len(set(engines.values())),
            f"two engine attributes resolve to the same class: {engines}",
        )

    def test_engine_calls_match_the_class_the_dock_binds(self):
        """Every call's keywords must exist on the class that receives it."""
        imports = _imports(_parse(DOCK))
        bound = _bound_attributes(_parse(DOCK))

        checked = 0
        for line, attr, method, node in _engine_calls(_parse(ACTIONS)):
            cls = bound.get(attr)
            if cls is None:
                continue  # bound by a mixin, not by the dock
            sources = imports.get(cls, set())
            self.assertEqual(
                1,
                len(sources),
                f"actions.py:{line} calls self.{attr}, but the dock's binding "
                f"of {cls} is ambiguous: {sorted(sources)}",
            )
            module, name = next(iter(sources))
            names, required, has_varargs, has_kwargs = _signature(module, name, method)
            where = f"actions.py:{line} -> {module}.{name}.{method}({', '.join(names)})"

            keywords = [kw.arg for kw in node.keywords]
            splat = None in keywords
            unexpected = [kw for kw in keywords if kw is not None and kw not in names]
            self.assertEqual(
                [], unexpected, f"{where}: unexpected keyword argument(s) {unexpected}"
            )

            if not (splat or has_varargs):
                filled = len(node.args) + len([kw for kw in keywords if kw in names])
                self.assertGreaterEqual(
                    filled,
                    required,
                    f"{where}: called with {filled} argument(s), {required} required",
                )
            checked += 1

        self.assertGreater(
            checked, 0, "no engine call was checked -- this test would pass vacuously"
        )


if __name__ == "__main__":
    unittest.main()
