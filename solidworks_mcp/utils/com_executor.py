"""Single-threaded executor for SolidWorks' COM automation interface."""

from __future__ import annotations

import atexit
import queue
import threading
from concurrent.futures import Future
from concurrent.futures import TimeoutError as FuturesTimeoutError
from typing import Any, Callable, Optional, TypeVar

import pythoncom

T = TypeVar("T")
_STOP = object()


class ComCallTimeoutError(TimeoutError):
    """A COM call exceeded its timeout; the executor is now poisoned."""


class ComExecutorPoisonedError(RuntimeError):
    """The COM thread is stuck on an earlier call; restart the server."""


class ComExecutor:
    """Run every SolidWorks call in one initialized COM apartment.

    COM calls cannot be safely interrupted from another thread. When a call
    exceeds its timeout, the worker keeps executing it and the executor is
    marked poisoned: every later call fails fast with
    :class:`ComExecutorPoisonedError` until the process is restarted.
    """

    def __init__(self) -> None:
        self._queue: queue.Queue[Any] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._start_lock = threading.Lock()
        self._poisoned_reason: Optional[str] = None

    def _ensure_started(self) -> None:
        if self._thread is not None and self._thread.is_alive():
            return
        with self._start_lock:
            if self._thread is not None and self._thread.is_alive():
                return
            self._thread = threading.Thread(
                target=self._worker,
                name="solidworks-com-sta",
                daemon=True,
            )
            self._thread.start()

    def _worker(self) -> None:
        pythoncom.CoInitialize()
        try:
            while True:
                item = self._queue.get()
                if item is _STOP:
                    return
                future, function, args, kwargs = item
                if not future.set_running_or_notify_cancel():
                    continue
                try:
                    future.set_result(function(*args, **kwargs))
                except BaseException as exc:
                    future.set_exception(exc)
        finally:
            pythoncom.CoUninitialize()

    def call(
        self,
        function: Callable[..., T],
        *args: Any,
        timeout: Optional[float] = None,
        **kwargs: Any,
    ) -> T:
        """Execute a callable on the COM thread and return its result.

        With ``timeout`` (seconds) set, an overrunning call raises
        :class:`ComCallTimeoutError` and poisons this executor.
        """
        self._ensure_started()
        if self._poisoned_reason:
            raise ComExecutorPoisonedError(self._poisoned_reason)
        if threading.current_thread() is self._thread:
            return function(*args, **kwargs)
        future: Future[T] = Future()
        self._queue.put((future, function, args, kwargs))
        if timeout is None:
            return future.result()
        try:
            return future.result(timeout=timeout)
        except FuturesTimeoutError as exc:
            self._poisoned_reason = (
                f"A SolidWorks COM call exceeded {timeout:.1f}s. The COM "
                "thread cannot be interrupted safely, so SolidWorks tools "
                "are unavailable until the MCP server is restarted."
            )
            raise ComCallTimeoutError(self._poisoned_reason) from exc

    def shutdown(self) -> None:
        """Request a clean COM apartment shutdown without blocking indefinitely."""
        thread = self._thread
        if thread is None or not thread.is_alive():
            return
        self._queue.put(_STOP)
        thread.join(timeout=2.0)


_executor = ComExecutor()
atexit.register(_executor.shutdown)


def run_com(
    function: Callable[..., T],
    *args: Any,
    timeout: Optional[float] = None,
    **kwargs: Any,
) -> T:
    """Run a SolidWorks operation on the process-wide COM apartment thread."""
    return _executor.call(function, *args, timeout=timeout, **kwargs)
