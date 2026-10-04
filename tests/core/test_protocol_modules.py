from __future__ import annotations

import builtins
import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import call, patch

from kapisch_core import protocol

_STAGE42_API = {
    "ConcurrentModificationError",
    "RunState",
    "load_state",
    "publish_state",
    "persist_request",
    "reserve_operation",
    "publish_uncertainty",
}


class ProtocolModuleTests(unittest.TestCase):
    def test_protocol_is_a_facade_for_the_existing_public_api(self) -> None:
        self.assertEqual(set(protocol.__all__), _STAGE42_API)
        expected_parameters = {
            "load_state": ["repo", "run_id"],
            "publish_state": ["repo", "run_id", "state", "expected_revision"],
            "persist_request": ["repo", "run_id", "operation_id", "packet"],
            "reserve_operation": [
                "repo",
                "run_id",
                "operation_id",
                "stage_id",
                "role",
                "request",
                "adapter_binding",
            ],
            "publish_uncertainty": [
                "repo",
                "run_id",
                "state",
                "expected_revision",
                "operation_id",
            ],
        }
        import inspect

        for name, parameters in expected_parameters.items():
            with self.subTest(function=name):
                self.assertEqual(
                    list(inspect.signature(getattr(protocol, name)).parameters),
                    parameters,
                )

    def test_responsibility_modules_are_internal_and_importable(self) -> None:
        for name in ("_locking", "_state", "_invocation", "_authority"):
            with self.subTest(module=name):
                module = importlib.import_module(f"kapisch_core.{name}")
                self.assertTrue(module.__name__.startswith("kapisch_core._"))

    @unittest.skipUnless(
        sys.platform != "win32" and importlib.util.find_spec("fcntl"),
        "POSIX flock required",
    )
    def test_lock_acquisition_and_release_use_posix_flock_directly(self) -> None:
        import fcntl

        from kapisch_core import _locking

        with patch.object(fcntl, "flock") as flock:
            _locking._acquire_lock(17)
            _locking._release_lock(17)

        self.assertEqual(
            flock.call_args_list, [call(17, fcntl.LOCK_EX), call(17, fcntl.LOCK_UN)]
        )

    @unittest.skipUnless(
        sys.platform != "win32" and importlib.util.find_spec("fcntl"),
        "POSIX flock required",
    )
    def test_lock_acquisition_failure_closes_unacquired_descriptors(self) -> None:
        import os
        import tempfile

        from kapisch_core import _locking

        for fail_at in (1, 2):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as repo:
                opened = []
                acquired = []
                released = []
                original_open = os.open

                def track_open(name, *args, **kwargs):
                    descriptor = original_open(name, *args, **kwargs)
                    if isinstance(name, str) and name.endswith(".lock"):
                        opened.append(descriptor)
                    return descriptor

                def fail_acquisition(descriptor):
                    acquired.append(descriptor)
                    if len(acquired) == fail_at:
                        raise OSError("injected lock acquisition failure")

                with (
                    patch.object(_locking.os, "open", side_effect=track_open),
                    patch.object(
                        _locking, "_acquire_lock", side_effect=fail_acquisition
                    ),
                    patch.object(
                        _locking, "_release_lock", side_effect=released.append
                    ),
                ):
                    with self.assertRaisesRegex(
                        OSError, "injected lock acquisition failure"
                    ):
                        with _locking._locked(
                            Path(repo), "run-lock-acquisition-failure"
                        ):
                            self.fail("lock context unexpectedly acquired all locks")

                self.assertEqual(len(opened), fail_at)
                self.assertEqual(released, opened[: fail_at - 1])
                for descriptor in opened:
                    with self.assertRaises(OSError):
                        os.fstat(descriptor)

    def test_repository_lock_precedes_run_lock(self) -> None:
        import stat
        from types import SimpleNamespace

        from kapisch_core import _locking

        opened = []
        acquired = []
        descriptors = iter((21, 22))
        with (
            patch.object(_locking, "_open_tree", return_value=(20, [19, 20])),
            patch.object(
                _locking.os,
                "open",
                side_effect=lambda name, *args, **kwargs: (
                    opened.append(name) or next(descriptors)
                ),
            ),
            patch.object(
                _locking.os, "fstat", return_value=SimpleNamespace(st_mode=stat.S_IFREG)
            ),
            patch.object(_locking.os, "close"),
            patch.object(_locking, "_acquire_lock", side_effect=acquired.append),
            patch.object(_locking, "_release_lock") as release,
            patch.object(_locking, "_close"),
        ):
            with _locking._locked(Path("."), "run-lock-order"):
                pass

        self.assertEqual(opened, ["repository.lock", "run-run-lock-order.lock"])
        self.assertEqual(acquired, [21, 22])
        self.assertEqual(release.call_args_list, [call(22), call(21)])

    @unittest.skipUnless(
        sys.platform != "win32" and importlib.util.find_spec("fcntl"),
        "POSIX flock required",
    )
    def test_lock_acquisition_does_not_fall_back_to_msvcrt(self) -> None:
        from kapisch_core import _locking

        imported = []
        real_import = builtins.__import__

        def reject_lock_import(name, *args, **kwargs):
            if name in {"fcntl", "msvcrt"}:
                imported.append(name)
            if name == "fcntl":
                raise ImportError("fcntl unavailable")
            if name == "msvcrt":
                raise AssertionError("unsafe platform fallback attempted")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=reject_lock_import):
            with self.assertRaisesRegex(ImportError, "fcntl unavailable"):
                _locking._acquire_lock(17)
        self.assertEqual(imported, ["fcntl"])

    def test_authority_storage_rejects_missing_descriptor_relative_support(
        self,
    ) -> None:
        from kapisch_core import storage

        with patch.object(storage, "_REQUIRED_SUPPORT", False):
            with self.assertRaisesRegex(OSError, "unsupported on this platform"):
                storage.load_bundle(Path("."), "0" * 64)

            from kapisch_core import _state

            with self.assertRaisesRegex(OSError, "unsupported on this platform"):
                _state.load_state(Path("."), "run-unsupported")


if __name__ == "__main__":
    unittest.main()
