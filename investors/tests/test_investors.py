import hashlib
import hmac
import json
from datetime import date, datetime
from decimal import Decimal
from unittest import mock

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from investors import paystack
from investors.models import Deposit, ProfitAllocation, ProfitDistribution
from investors.services import (
    DistributionError,
    apply_paystack_result,
    distribute_profit,
    portfolio,
)

SECRET = "sk_test_secret"


def make_investor(username):
    user = User.objects.create_user(username, f"{username}@example.com", "pw-12345!")
    user.groups.add(Group.objects.get(name="Investors"))
    return user


def paid_deposit(user, amount, when=datetime(2026, 1, 15)):
    return Deposit.objects.create(
        investor=user,
        amount=Decimal(amount),
        currency="KES",
        status=Deposit.Status.SUCCESS,
        paid_at=timezone.make_aware(when),
    )


class DistributeProfitTests(TestCase):
    def setUp(self):
        self.alice = make_investor("alice")
        self.bob = make_investor("bob")

    def test_split_is_proportional_to_capital(self):
        paid_deposit(self.alice, "75000")
        paid_deposit(self.bob, "25000")
        dist = ProfitDistribution.objects.create(
            title="Q1", total_profit=Decimal("10000"), as_of=date(2026, 3, 31)
        )
        distribute_profit(dist)

        alice = ProfitAllocation.objects.get(investor=self.alice)
        bob = ProfitAllocation.objects.get(investor=self.bob)
        self.assertEqual(alice.amount, Decimal("7500.00"))
        self.assertEqual(alice.share_percent, Decimal("75"))
        self.assertEqual(bob.amount, Decimal("2500.00"))

    def test_allocations_sum_exactly_to_total(self):
        carol = make_investor("carol")
        for user in (self.alice, self.bob, carol):
            paid_deposit(user, "1000")
        dist = ProfitDistribution.objects.create(
            title="Q1", total_profit=Decimal("100.00"), as_of=date(2026, 3, 31)
        )
        allocations = distribute_profit(dist)
        self.assertEqual(sum(a.amount for a in allocations), Decimal("100.00"))

    def test_ignores_unconfirmed_and_later_deposits(self):
        paid_deposit(self.alice, "1000")
        paid_deposit(self.bob, "5000", when=datetime(2026, 6, 1))  # after as_of
        Deposit.objects.create(investor=self.bob, amount=Decimal("9000"), currency="KES")
        dist = ProfitDistribution.objects.create(
            title="Q1", total_profit=Decimal("500"), as_of=date(2026, 3, 31)
        )
        allocations = distribute_profit(dist)
        self.assertEqual(len(allocations), 1)
        self.assertEqual(allocations[0].investor, self.alice)
        self.assertEqual(allocations[0].amount, Decimal("500.00"))

    def test_cannot_distribute_twice(self):
        paid_deposit(self.alice, "1000")
        dist = ProfitDistribution.objects.create(
            title="Q1", total_profit=Decimal("500"), as_of=date(2026, 3, 31)
        )
        distribute_profit(dist)
        with self.assertRaises(DistributionError):
            distribute_profit(dist)

    def test_portfolio_totals(self):
        paid_deposit(self.alice, "80000")
        paid_deposit(self.bob, "20000")
        dist = ProfitDistribution.objects.create(
            title="Q1", total_profit=Decimal("10000"), as_of=date(2026, 3, 31)
        )
        distribute_profit(dist)
        ProfitAllocation.objects.filter(investor=self.alice).update(
            status=ProfitAllocation.Status.PAID
        )
        p = portfolio(self.alice)
        self.assertEqual(p["principal"], Decimal("80000"))
        self.assertEqual(p["share_percent"], Decimal("80"))
        self.assertEqual(p["earned"], Decimal("8000"))
        self.assertEqual(p["paid"], Decimal("8000"))
        self.assertEqual(p["owed"], Decimal("0"))
        self.assertEqual(p["return_percent"], Decimal("10"))
        self.assertEqual(p["chart"]["principal"], [80000.0, 80000.0])
        self.assertEqual(p["chart"]["profit"], [0.0, 8000.0])


class ApplyPaystackResultTests(TestCase):
    def setUp(self):
        self.user = make_investor("alice")
        self.deposit = Deposit.objects.create(
            investor=self.user, amount=Decimal("5000"), currency="KES"
        )

    def result(self, **overrides):
        data = {"status": "success", "amount": 500000, "currency": "KES"}
        data.update(overrides)
        return data

    def test_success_credits_once(self):
        apply_paystack_result(self.deposit.reference, self.result())
        self.deposit.refresh_from_db()
        first_paid_at = self.deposit.paid_at
        self.assertEqual(self.deposit.status, Deposit.Status.SUCCESS)

        apply_paystack_result(self.deposit.reference, self.result())
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.paid_at, first_paid_at)

    def test_wrong_amount_is_not_credited(self):
        apply_paystack_result(self.deposit.reference, self.result(amount=100))
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.status, Deposit.Status.FAILED)

    def test_wrong_currency_is_not_credited(self):
        apply_paystack_result(self.deposit.reference, self.result(currency="NGN"))
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.status, Deposit.Status.FAILED)

    def test_unknown_reference(self):
        self.assertIsNone(apply_paystack_result("nope", self.result()))


@override_settings(PAYSTACK_SECRET_KEY=SECRET, PAYSTACK_CURRENCY="KES")
class DepositFlowTests(TestCase):
    def setUp(self):
        self.user = make_investor("alice")
        self.client.force_login(self.user)

    @mock.patch("investors.paystack.initialize", return_value="https://checkout.paystack.com/abc")
    def test_deposit_redirects_to_paystack(self, initialize):
        response = self.client.post(reverse("investors:deposit"), {"amount": "5000"})
        self.assertRedirects(
            response, "https://checkout.paystack.com/abc", fetch_redirect_response=False
        )
        deposit = Deposit.objects.get()
        self.assertEqual(deposit.status, Deposit.Status.PENDING)
        kwargs = initialize.call_args.kwargs
        self.assertEqual(kwargs["amount_subunit"], 500000)
        self.assertEqual(kwargs["reference"], deposit.reference)
        self.assertEqual(kwargs["email"], "alice@example.com")

    def test_deposit_below_minimum_rejected(self):
        response = self.client.post(reverse("investors:deposit"), {"amount": "5"})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(Deposit.objects.exists())

    @mock.patch("investors.paystack.initialize", side_effect=paystack.PaystackError("down"))
    def test_paystack_failure_marks_deposit_failed(self, _):
        response = self.client.post(reverse("investors:deposit"), {"amount": "5000"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(Deposit.objects.get().status, Deposit.Status.FAILED)

    def test_callback_verifies_and_credits(self):
        deposit = Deposit.objects.create(investor=self.user, amount=Decimal("5000"), currency="KES")
        with mock.patch(
            "investors.paystack.verify",
            return_value={"status": "success", "amount": 500000, "currency": "KES"},
        ):
            response = self.client.get(
                reverse("investors:deposit_callback"), {"reference": deposit.reference}
            )
        self.assertRedirects(response, reverse("investors:dashboard"))
        deposit.refresh_from_db()
        self.assertEqual(deposit.status, Deposit.Status.SUCCESS)

    def test_callback_ignores_other_investors_deposits(self):
        other = make_investor("bob")
        deposit = Deposit.objects.create(investor=other, amount=Decimal("5000"), currency="KES")
        with mock.patch("investors.paystack.verify") as verify:
            self.client.get(reverse("investors:deposit_callback"), {"reference": deposit.reference})
        verify.assert_not_called()


@override_settings(PAYSTACK_SECRET_KEY=SECRET)
class WebhookTests(TestCase):
    def setUp(self):
        self.user = make_investor("alice")
        self.deposit = Deposit.objects.create(
            investor=self.user, amount=Decimal("5000"), currency="KES"
        )
        self.body = json.dumps(
            {
                "event": "charge.success",
                "data": {
                    "reference": self.deposit.reference,
                    "status": "success",
                    "amount": 500000,
                    "currency": "KES",
                },
            }
        ).encode()

    def post(self, signature):
        return self.client.post(
            reverse("investors:paystack_webhook"),
            data=self.body,
            content_type="application/json",
            headers={"X-Paystack-Signature": signature},
        )

    def test_bad_signature_rejected(self):
        self.assertEqual(self.post("bad").status_code, 400)
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.status, Deposit.Status.PENDING)

    def test_valid_charge_success_credits(self):
        signature = hmac.new(SECRET.encode(), self.body, hashlib.sha512).hexdigest()
        self.assertEqual(self.post(signature).status_code, 200)
        self.deposit.refresh_from_db()
        self.assertEqual(self.deposit.status, Deposit.Status.SUCCESS)


class AccessTests(TestCase):
    def test_anonymous_redirected_to_login(self):
        response = self.client.get(reverse("investors:dashboard"))
        self.assertRedirects(
            response, f"{reverse('investors:login')}?next={reverse('investors:dashboard')}"
        )

    def test_non_investor_forbidden(self):
        user = User.objects.create_user("visitor", password="pw-12345!")
        self.client.force_login(user)
        self.assertEqual(self.client.get(reverse("investors:dashboard")).status_code, 403)

    def test_investor_sees_only_own_data(self):
        alice = make_investor("alice")
        bob = make_investor("bob")
        mine = paid_deposit(alice, "1000")
        theirs = paid_deposit(bob, "2000")
        self.client.force_login(alice)
        response = self.client.get(reverse("investors:dashboard"))
        self.assertContains(response, mine.reference)
        self.assertNotContains(response, theirs.reference)
        self.assertContains(response, "33.33%")

    def test_login_page_renders(self):
        self.assertEqual(self.client.get(reverse("investors:login")).status_code, 200)


class DepositWithoutEmailTests(TestCase):
    @mock.patch("investors.paystack.initialize")
    def test_investor_without_email_cannot_start_payment(self, initialize):
        user = make_investor("noemail")
        user.email = ""
        user.save()
        self.client.force_login(user)
        response = self.client.post(reverse("investors:deposit"), {"amount": "5000"})
        self.assertContains(response, "no email address")
        initialize.assert_not_called()
        self.assertFalse(Deposit.objects.exists())
