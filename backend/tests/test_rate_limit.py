from datetime import date

from app.rate_limit import QuotaTracker


def test_per_ip_limit():
    q = QuotaTracker(per_ip=3, global_cap=100)
    assert [q.try_consume("1.1.1.1") for _ in range(4)] == [True, True, True, False]
    assert q.remaining("1.1.1.1") == 0
    assert q.remaining("2.2.2.2") == 3


def test_global_cap_across_ips():
    q = QuotaTracker(per_ip=3, global_cap=2)
    assert q.try_consume("a") and q.try_consume("b")
    assert not q.try_consume("c")
    assert q.remaining("c") == 0


def test_resets_on_new_day():
    day = [date(2026, 1, 1)]
    q = QuotaTracker(per_ip=1, global_cap=10, today=lambda: day[0])
    assert q.try_consume("a") and not q.try_consume("a")
    day[0] = date(2026, 1, 2)
    assert q.remaining("a") == 1 and q.try_consume("a")


def _request(xff: str | None, host: str = "10.0.0.1"):
    from starlette.requests import Request

    headers = [(b"x-forwarded-for", xff.encode())] if xff else []
    return Request({"type": "http", "headers": headers, "client": (host, 1234)})


def test_client_ip_uses_rightmost_forwarded_entry_behind_proxy():
    from app.rate_limit import client_ip

    # The visitor can forge leftmost entries; the proxy appends the real IP last.
    assert client_ip(_request("6.6.6.6, 203.0.113.9"), trust_proxy=True) == "203.0.113.9"


def test_client_ip_ignores_forwarded_header_without_proxy():
    from app.rate_limit import client_ip

    assert client_ip(_request("6.6.6.6"), trust_proxy=False) == "10.0.0.1"
    assert client_ip(_request(None), trust_proxy=True) == "10.0.0.1"


def test_refund_returns_a_run():
    q = QuotaTracker(per_ip=1, global_cap=10)
    assert q.try_consume("a") and q.remaining("a") == 0
    q.refund("a")
    assert q.remaining("a") == 1
    q.refund("a")
    assert q.remaining("a") == 1
