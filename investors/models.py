import secrets

from django.conf import settings
from django.db import models

MONEY = {"max_digits": 14, "decimal_places": 2}


def new_reference():
    return f"CHK-{secrets.token_hex(8).upper()}"


class Deposit(models.Model):
    """Money an investor paid in through Paystack. Only successful deposits count as capital."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Successful"
        FAILED = "failed", "Failed"

    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="deposits"
    )
    amount = models.DecimalField(**MONEY)
    currency = models.CharField(max_length=3)
    reference = models.CharField(max_length=40, unique=True, default=new_reference)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    paystack_response = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.reference} · {self.currency} {self.amount} ({self.status})"


class ProfitDistribution(models.Model):
    """Profit declared by the company, shared by investors in proportion to their capital."""

    title = models.CharField(max_length=120, help_text='For example "Q3 2026".')
    total_profit = models.DecimalField(**MONEY)
    as_of = models.DateField(
        help_text="Capital from deposits paid on or before this date is used for the split."
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-as_of", "-created_at"]

    def __str__(self):
        return f"{self.title} ({self.total_profit})"


class ProfitAllocation(models.Model):
    """One investor's slice of a profit distribution, tracked until it is paid out."""

    class Status(models.TextChoices):
        OWED = "owed", "Owed"
        PAID = "paid", "Paid"

    distribution = models.ForeignKey(
        ProfitDistribution, on_delete=models.CASCADE, related_name="allocations"
    )
    investor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="profit_allocations",
    )
    capital_at_time = models.DecimalField(**MONEY)
    share_percent = models.DecimalField(max_digits=9, decimal_places=6)
    amount = models.DecimalField(**MONEY)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.OWED)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-distribution__as_of", "investor__username"]
        constraints = [
            models.UniqueConstraint(
                fields=["distribution", "investor"], name="one_allocation_per_investor"
            )
        ]

    def __str__(self):
        return f"{self.investor} · {self.distribution.title}: {self.amount}"
