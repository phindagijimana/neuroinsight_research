"""
Tests for error handling across backend modules.

Verifies that except blocks log errors instead of silently swallowing them.
Uses AST inspection to ensure no bare `except: pass` or `except Exception: pass`
patterns remain in critical backend files.
"""
import ast
import os
from pathlib import Path

import pytest


BACKEND_ROOT = Path(__file__).parent.parent / "backend"

CRITICAL_FILES = [
    "execution/celery_tasks.py",
    "execution/local_backend.py",
    "execution/remote_docker_backend.py",
    "execution/slurm_backend.py",
    "core/transfer_manager.py",
    "core/ssh_manager.py",
    "routes/hpc.py",
    "routes/results.py",
    "routes/transfer.py",
    "main.py",
    "connectors/xnat.py",
]

ALLOWED_PASS_PARENTS = {
    "ClassDef",       # class Foo: pass
    "FunctionDef",    # def foo(): pass  (abstract methods / stubs)
}

ALLOWED_EXCEPTION_TYPES = {
    "FileNotFoundError",
    "PermissionError",
    "IOError",  # SFTP mkdir -p pattern (directory may already exist)
}


class TestNoSilentExceptions:
    """Ensure no silent `except: pass` blocks remain in critical backend files."""

    @pytest.mark.parametrize("rel_path", CRITICAL_FILES)
    def test_no_bare_except_pass(self, rel_path):
        """No except handler should have only `pass` as its body (AST check).

        Exceptions:
          - FileNotFoundError/PermissionError handlers (OS probing) are allowed
          - Abstract method stubs in base classes are allowed
        """
        filepath = BACKEND_ROOT / rel_path
        if not filepath.exists():
            pytest.skip(f"{rel_path} not found")

        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))

        violations = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue

            body = node.body
            if len(body) != 1:
                continue

            stmt = body[0]
            is_pass = isinstance(stmt, ast.Pass)
            is_continue = isinstance(stmt, ast.Continue)

            if not (is_pass or is_continue):
                continue

            # Allow specific exception types that are genuinely acceptable
            if node.type is not None:
                if isinstance(node.type, ast.Name) and node.type.id in ALLOWED_EXCEPTION_TYPES:
                    continue
                if isinstance(node.type, ast.Tuple):
                    names = {
                        elt.id for elt in node.type.elts
                        if isinstance(elt, ast.Name)
                    }
                    if names <= ALLOWED_EXCEPTION_TYPES:
                        continue

            violations.append(
                f"  Line {node.lineno}: except {_except_type_str(node)} -> {type(stmt).__name__}"
            )

        if violations:
            msg = f"Silent exception handlers in {rel_path}:\n" + "\n".join(violations)
            pytest.fail(msg)


def _except_type_str(handler: ast.ExceptHandler) -> str:
    """Human-readable string for the exception type in a handler."""
    if handler.type is None:
        return "(bare except)"
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    if isinstance(handler.type, ast.Tuple):
        return "(" + ", ".join(
            elt.id if isinstance(elt, ast.Name) else "?" for elt in handler.type.elts
        ) + ")"
    return "?"


class TestExceptionHandlerQuality:
    """Verify that exception handlers in critical files have logging."""

    @pytest.mark.parametrize("rel_path", CRITICAL_FILES)
    def test_except_handlers_have_names(self, rel_path):
        """Exception handlers should capture the exception (except ... as e:)
        or use a specific exception type, not bare `except:` or `except Exception:`.
        """
        filepath = BACKEND_ROOT / rel_path
        if not filepath.exists():
            pytest.skip(f"{rel_path} not found")

        source = filepath.read_text()
        tree = ast.parse(source, filename=str(filepath))

        bare_handlers = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            # Bare `except:` (no type, no name)
            if node.type is None and node.name is None:
                bare_handlers.append(f"  Line {node.lineno}: bare except (no type or name)")

        if bare_handlers:
            msg = f"Bare exception handlers in {rel_path}:\n" + "\n".join(bare_handlers)
            pytest.fail(msg)
