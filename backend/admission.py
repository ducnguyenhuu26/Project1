"""Small process-local request guards for a single API worker.

Run multiple workers behind a shared proxy/rate limiter for production-wide limits.
"""
from collections import OrderedDict, deque
from threading import BoundedSemaphore, Lock
import time


class RequestGuards:
    def __init__(self, inference_slots: int = 2):
        self.inference = BoundedSemaphore(max(1, inference_slots))
        self._lock = Lock()
        self._events: OrderedDict[tuple[str, str], deque[float]] = OrderedDict()

    def allow(self, scope: str, client_id: str, limit: int, window_seconds: float) -> tuple[bool, int]:
        now = time.monotonic()
        key = (scope, client_id)
        with self._lock:
            events = self._events.get(key)
            if events is None:
                if len(self._events) >= 10_000:
                    self._events.popitem(last=False)
                events = deque()
                self._events[key] = events
            self._events.move_to_end(key)
            while events and now - events[0] >= window_seconds:
                events.popleft()
            if len(events) >= limit:
                return False, max(1, int(window_seconds - (now - events[0]) + .999))
            events.append(now)
            return True, 0


def client_key(request) -> str:
    # Only use the direct peer. X-Forwarded-For is untrusted unless a trusted proxy
    # is explicitly configured; this application does not currently configure one.
    return request.client.host if request.client else "unknown"
