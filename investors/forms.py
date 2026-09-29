from decimal import Decimal

from django import forms

MIN_DEPOSIT = Decimal("100")
MAX_DEPOSIT = Decimal("10000000")


class DepositForm(forms.Form):
    amount = forms.DecimalField(
        min_value=MIN_DEPOSIT,
        max_value=MAX_DEPOSIT,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"step": "0.01", "placeholder": "e.g. 50000"}),
    )
