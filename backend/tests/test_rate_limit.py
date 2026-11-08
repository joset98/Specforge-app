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
