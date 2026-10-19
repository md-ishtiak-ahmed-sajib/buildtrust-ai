"""Bounded, expiring process-local account and IP failure buckets."""

import time
from collections import OrderedDict
from threading import Lock

from .security import DomainError


class LoginThrottle:
    def __init__(self, clock=time.monotonic, capacity=4096):
        self.clock, self.capacity = clock, capacity
        self.buckets, self.lock = OrderedDict(), Lock()

    def _bucket(self, key, now):
        values = [t for t in self.buckets.pop(key, []) if now - t < 60]
        self.buckets[key] = values
        while len(self.buckets) > self.capacity:
            self.buckets.popitem(last=False)
        return values

    def check(self, identifier, address):
        with self.lock:
            now = self.clock()
            for key, limit in (("account:" + identifier, 10), ("ip:" + address, 50)):
                values = self._bucket(key, now)
                if len(values) >= limit:
                    raise DomainError(
                        429,
                        "LOGIN_RATE_LIMIT",
                        "Wait before retrying sign-in.",
                        retry_after=max(1, int(60 - (now - values[0])) + 1),
                    )

    def failed(self, identifier, address):
        with self.lock:
            now = self.clock()
            for key in ("account:" + identifier, "ip:" + address):
                self._bucket(key, now).append(now)
