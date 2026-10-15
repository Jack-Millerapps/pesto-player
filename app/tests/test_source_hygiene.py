"""Source files must not contain lone surrogates in docstrings (or, outside tests, in
any string constant). Python 3.9 tolerates them; 3.13 raises UnicodeEncodeError at
import. Walk every .py under app/ and pi/ with ast so the Mac-side suite catches it."""
import ast
import os
import re

SURROGATE = re.compile("[\ud800-\udfff]")
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _py_files():
    for top in ("app", "pi"):
        for dirpath, dirs, files in os.walk(os.path.join(ROOT, top)):
            dirs[:] = [d for d in dirs if d not in ("__pycache__", ".venv", "node_modules")]
            for f in files:
                if f.endswith(".py"):
                    yield os.path.join(dirpath, f)


def _is_test(path):
    return os.sep + "tests" + os.sep in path or os.path.basename(path).startswith("test_")


def test_no_lone_surrogates_in_docstrings_or_source_constants():
    problems = []
    for path in _py_files():
        with open(path, encoding="utf-8") as f:
            tree = ast.parse(f.read(), path)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node, clean=False)
                if doc and SURROGATE.search(doc):
                    problems.append(f"{path}: docstring of {getattr(node, 'name', 'module')}")
            if (not _is_test(path) and isinstance(node, ast.Constant)
                    and isinstance(node.value, str) and SURROGATE.search(node.value)):
                problems.append(f"{path}:{node.lineno}: string constant")
    assert not problems, "\n".join(problems)


def test_files_found():
    assert sum(1 for _ in _py_files()) > 20
