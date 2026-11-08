from collections import Counter
from collections.abc import Callable
from datetime import date

from fastapi import Request


class QuotaTracker:
    """Free runs on the owner's key: per-IP daily limit plus a global daily cap."""

    # shortcut: in-memory counter, resets on restart and only works with one instance;
    # move to Redis if scaled out.
    def __init__(self, per_ip: int, global_cap: int, today: Callable[[], date] = date.today):
        self.per_ip = per_ip
        self.global_cap = global_cap
        self.today = today
        self.day = today()
        self.used: Counter[str] = Counter()

    def _roll(self) -> None:
        if self.today() != self.day:
            self.day = self.today()
            self.used.clear()

    def remaining(self, ip: str) -> int:
        self._roll()
        global_left = self.global_cap - self.used.total()
        return max(0, min(self.per_ip - self.used[ip], global_left))

    def refund(self, ip: str) -> None:
        if self.used[ip] > 0:
            self.used[ip] -= 1

    def try_consume(self, ip: str) -> bool:
        if self.remaining(ip) <= 0:
            return False
        self.used[ip] += 1
        return True


def client_ip(request: Request, trust_proxy: bool) -> str:
    """Behind a proxy, the rightmost X-Forwarded-For entry is the one the proxy appended;
    entries to its left are client-supplied and can be forged."""
    if trust_proxy:
        forwarded = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",")]
        if forwarded[-1]:
            return forwarded[-1]
    return request.client.host if request.client else "unknown"
