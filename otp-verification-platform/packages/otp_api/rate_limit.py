"""Small in-process request limiter for single-worker deployments."""

from math import ceil
from threading import Lock
from time import monotonic


class RateLimitExceeded(Exception):
    """Raised when a client exceeds a fixed-window request limit."""

    def __init__(self, retry_after_seconds: int) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Request rate limit exceeded")


class InMemoryRateLimiter:
    """Apply fixed-window limits keyed by action and client address.

    This limiter is intentionally process-local. Production deployments with
    multiple workers must replace it with shared storage.
    """

    def __init__(self) -> None:
        self._windows: dict[tuple[str, str], tuple[float, int]] = {}
        self._lock = Lock()

    def check(
        self,
        key: tuple[str, str],
        limit: int,
        window_seconds: int,
    ) -> None:
        now = monotonic()
        with self._lock:
            window = self._windows.get(key)
            if window is None or now - window[0] >= window_seconds:
                self._windows[key] = (now, 1)
                if len(self._windows) > 10_000:
                    self._windows = {
                        item_key: item_window
                        for item_key, item_window in self._windows.items()
                        if now - item_window[0] < window_seconds
                    }
                return

            started_at, count = window
            if count >= limit:
                retry_after = max(
                    1,
                    ceil(window_seconds - (now - started_at)),
                )
                raise RateLimitExceeded(retry_after)
            self._windows[key] = (started_at, count + 1)
