"""Tests for the budget guardrail — compute on-the-fly from runs.cost_usd."""
from types import SimpleNamespace

from services import budget


class _FakeTable:
    def __init__(self, rows):
        self._rows = rows
    def select(self, *_a, **_k): return self
    def eq(self, *_a, **_k):    return self
    def gte(self, *_a, **_k):   return self
    def lt(self, *_a, **_k):    return self
    def execute(self):          return SimpleNamespace(data=self._rows)


class _FakeAdmin:
    def __init__(self, rows): self._rows = rows
    def table(self, *_a, **_k): return _FakeTable(self._rows)


def _patch_admin(monkeypatch, rows):
    monkeypatch.setattr(budget, "get_supabase_admin", lambda: _FakeAdmin(rows))


def test_usage_empty_is_zero(monkeypatch):
    _patch_admin(monkeypatch, [])
    u = budget.get_current_usage("user-id")
    assert u.spent_usd == 0
    assert u.remaining_usd == u.budget_usd
    assert u.run_count == 0
    assert not u.as_dict()["over_budget"]


def test_usage_accumulates(monkeypatch):
    _patch_admin(monkeypatch, [{"cost_usd": "1.5"}, {"cost_usd": 2.25}, {"cost_usd": 0}])
    u = budget.get_current_usage("user-id")
    assert abs(u.spent_usd - 3.75) < 1e-6
    assert u.run_count == 3


def test_is_over_budget_honours_monthly_cap(monkeypatch):
    from config import settings
    monkeypatch.setattr(settings, "OPENAI_MONTHLY_BUDGET_USD", 10, raising=False)
    _patch_admin(monkeypatch, [{"cost_usd": 10.0001}])
    assert budget.is_over_budget("user-id") is True
    _patch_admin(monkeypatch, [{"cost_usd": 9.9}])
    assert budget.is_over_budget("user-id") is False
