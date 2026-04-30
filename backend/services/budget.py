"""Monthly OpenAI budget guardrail.

We don't maintain a dedicated ``monthly_usage`` table — we compute on-the-fly
from ``runs.cost_usd`` for the given user's current calendar month (UTC).
That keeps the data single-source-of-truth and avoids drift.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from config import settings
from services.supabase_client import get_supabase_admin


@dataclass
class UsageSummary:
    spent_usd: float
    budget_usd: float
    remaining_usd: float
    run_count: int
    month: str  # YYYY-MM

    def as_dict(self) -> dict:
        return {
            "spent_usd": round(self.spent_usd, 4),
            "budget_usd": self.budget_usd,
            "remaining_usd": round(self.remaining_usd, 4),
            "run_count": self.run_count,
            "month": self.month,
            "over_budget": self.remaining_usd <= 0,
        }


def _month_bounds_iso() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    # Next month start
    year, month = (now.year, now.month + 1) if now.month < 12 else (now.year + 1, 1)
    end = start.replace(year=year, month=month)
    return start.isoformat(), end.isoformat()


def get_current_usage(owner_id: str) -> UsageSummary:
    admin = get_supabase_admin()
    start, end = _month_bounds_iso()
    res = (
        admin.table("runs")
        .select("cost_usd")
        .eq("owner_id", owner_id)
        .gte("created_at", start)
        .lt("created_at", end)
        .execute()
    )
    rows = res.data or []
    spent = float(sum(float(r.get("cost_usd") or 0) for r in rows))
    budget = float(settings.OPENAI_MONTHLY_BUDGET_USD)
    return UsageSummary(
        spent_usd=spent,
        budget_usd=budget,
        remaining_usd=max(0.0, budget - spent),
        run_count=len(rows),
        month=datetime.now(timezone.utc).strftime("%Y-%m"),
    )


def is_over_budget(owner_id: str) -> bool:
    return get_current_usage(owner_id).remaining_usd <= 0
