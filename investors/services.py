from collections import defaultdict
from datetime import datetime, time
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from .models import Deposit, ProfitAllocation, ProfitDistribution

INVESTOR_GROUP = "Investors"
CENT = Decimal("0.01")


def is_investor(user):
    return user.is_authenticated and user.groups.filter(name=INVESTOR_GROUP).exists()


def _successful_deposits(as_of=None):
    qs = Deposit.objects.filter(status=Deposit.Status.SUCCESS)
    if as_of is not None:
        end_of_day = timezone.make_aware(datetime.combine(as_of, time.max))
        qs = qs.filter(paid_at__lte=end_of_day)
    return qs


def investor_capital(user, as_of=None):
    total = _successful_deposits(as_of).filter(investor=user).aggregate(s=Sum("amount"))["s"]
    return total or Decimal("0")


def capital_by_investor(as_of=None):
    rows = (
        _successful_deposits(as_of)
        .values("investor")
        .annotate(capital=Sum("amount"))
        .filter(capital__gt=0)
    )
    return {row["investor"]: row["capital"] for row in rows}


def share_fraction(user, as_of=None):
    """The user's share of all investor capital, as a fraction between 0 and 1."""
    capitals = capital_by_investor(as_of)
    total = sum(capitals.values(), Decimal("0"))
    if not total:
        return Decimal("0")
    return capitals.get(user.pk, Decimal("0")) / total


class DistributionError(Exception):
    pass


@transaction.atomic
def distribute_profit(distribution: ProfitDistribution):
    """Split the distribution's profit across investors in proportion to their capital."""
    distribution = ProfitDistribution.objects.select_for_update().get(pk=distribution.pk)
    if distribution.allocations.exists():
        raise DistributionError("Profit for this distribution has already been allocated.")

    capitals = capital_by_investor(distribution.as_of)
    total_capital = sum(capitals.values(), Decimal("0"))
    if not total_capital:
        raise DistributionError("No investor capital existed on that date.")

    allocations = []
    for investor_id, capital in capitals.items():
        fraction = capital / total_capital
        allocations.append(
            ProfitAllocation(
                distribution=distribution,
                investor_id=investor_id,
                capital_at_time=capital,
                share_percent=(fraction * 100).quantize(Decimal("0.000001"), ROUND_HALF_UP),
                amount=(distribution.total_profit * fraction).quantize(CENT, ROUND_DOWN),
            )
        )

    # Rounding down leaves a few cents over; give them to the largest holders
    # so the allocations always add up to exactly the declared profit.
    leftover = distribution.total_profit - sum(a.amount for a in allocations)
    for allocation in sorted(allocations, key=lambda a: a.capital_at_time, reverse=True):
        if leftover < CENT:
            break
        allocation.amount += CENT
        leftover -= CENT

    return ProfitAllocation.objects.bulk_create(allocations)


def to_subunit(amount):
    """Paystack amounts are in the currency's subunit (cents, kobo...)."""
    return int((Decimal(amount) * 100).quantize(Decimal("1")))


@transaction.atomic
def apply_paystack_result(reference, data):
    """Record the outcome Paystack reports for a deposit. Safe to call repeatedly.

    Returns the deposit, or None if the reference is unknown.
    """
    deposit = Deposit.objects.select_for_update().filter(reference=reference).first()
    if deposit is None or deposit.status == Deposit.Status.SUCCESS:
        return deposit

    paid = (
        data.get("status") == "success"
        and data.get("amount") == to_subunit(deposit.amount)
        and str(data.get("currency", "")).upper() == deposit.currency.upper()
    )
    if paid:
        deposit.status = Deposit.Status.SUCCESS
        deposit.paid_at = timezone.now()
    elif data.get("status") in ("success", "failed", "abandoned", "reversed"):
        # A "success" with the wrong amount or currency is never credited.
        deposit.status = Deposit.Status.FAILED
    deposit.paystack_response = data
    deposit.save(update_fields=["status", "paid_at", "paystack_response"])
    return deposit


def portfolio(user):
    """Everything the investor dashboard shows."""
    deposits = list(user.deposits.all())
    allocations = list(user.profit_allocations.select_related("distribution"))
    principal = investor_capital(user)
    earned = sum((a.amount for a in allocations), Decimal("0"))
    paid = sum((a.amount for a in allocations if a.status == ProfitAllocation.Status.PAID), Decimal("0"))

    # Month-by-month running totals for the growth chart.
    monthly = defaultdict(lambda: [Decimal("0"), Decimal("0")])
    for d in deposits:
        if d.status == Deposit.Status.SUCCESS:
            monthly[timezone.localtime(d.paid_at).strftime("%Y-%m")][0] += d.amount
    for a in allocations:
        monthly[a.distribution.as_of.strftime("%Y-%m")][1] += a.amount
    labels, principal_series, profit_series = [], [], []
    running_principal = running_profit = Decimal("0")
    for month in sorted(monthly):
        running_principal += monthly[month][0]
        running_profit += monthly[month][1]
        labels.append(month)
        principal_series.append(float(running_principal))
        profit_series.append(float(running_profit))

    return {
        "principal": principal,
        "share_percent": share_fraction(user) * 100,
        "earned": earned,
        "paid": paid,
        "owed": earned - paid,
        "return_percent": (earned / principal * 100) if principal else Decimal("0"),
        "deposits": deposits,
        "allocations": allocations,
        "chart": {
            "labels": labels,
            "principal": principal_series,
            "profit": profit_series,
        },
    }


def investor_users():
    return get_user_model().objects.filter(groups__name=INVESTOR_GROUP)
