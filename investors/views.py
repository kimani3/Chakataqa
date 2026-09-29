import json

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse, HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from . import paystack
from .forms import DepositForm
from .models import Deposit
from .services import apply_paystack_result, is_investor, portfolio, to_subunit


def _require_investor(user):
    if not is_investor(user):
        raise PermissionDenied
    return True


investor_required = user_passes_test(_require_investor)


@login_required
@investor_required
def dashboard(request):
    context = portfolio(request.user)
    context["currency"] = settings.PAYSTACK_CURRENCY
    return render(request, "investors/dashboard.html", context)


@login_required
@investor_required
def deposit(request):
    form = DepositForm(request.POST or None)
    if not request.user.email:
        messages.error(
            request, "Your account has no email address, which Paystack requires. Please contact us."
        )
    elif request.method == "POST" and form.is_valid():
        record = Deposit.objects.create(
            investor=request.user,
            amount=form.cleaned_data["amount"],
            currency=settings.PAYSTACK_CURRENCY,
        )
        try:
            checkout_url = paystack.initialize(
                email=request.user.email,
                amount_subunit=to_subunit(record.amount),
                currency=record.currency,
                reference=record.reference,
                callback_url=request.build_absolute_uri(reverse("investors:deposit_callback")),
            )
        except paystack.PaystackError as exc:
            record.status = Deposit.Status.FAILED
            record.paystack_response = {"error": str(exc)}
            record.save(update_fields=["status", "paystack_response"])
            messages.error(request, "We couldn't start the payment. Please try again shortly.")
        else:
            return redirect(checkout_url)
    return render(
        request,
        "investors/deposit.html",
        {"form": form, "currency": settings.PAYSTACK_CURRENCY},
    )


@login_required
@investor_required
def deposit_callback(request):
    reference = request.GET.get("reference", "")
    if not Deposit.objects.filter(reference=reference, investor=request.user).exists():
        messages.error(request, "We couldn't find that payment.")
        return redirect("investors:dashboard")

    try:
        record = apply_paystack_result(reference, paystack.verify(reference))
    except paystack.PaystackError:
        messages.info(
            request,
            "We're still confirming your payment with Paystack. "
            "It will appear here once confirmed.",
        )
        return redirect("investors:dashboard")

    if record.status == Deposit.Status.SUCCESS:
        messages.success(
            request, f"Deposit of {record.currency} {record.amount:,.2f} received. Thank you!"
        )
    elif record.status == Deposit.Status.FAILED:
        messages.error(request, "The payment was not completed.")
    else:
        messages.info(request, "Your payment is still being processed.")
    return redirect("investors:dashboard")


@csrf_exempt
@require_POST
def paystack_webhook(request):
    signature = request.headers.get("X-Paystack-Signature", "")
    if not paystack.valid_signature(request.body, signature):
        return HttpResponseBadRequest("Invalid signature")
    try:
        event = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest("Invalid JSON")

    if event.get("event") == "charge.success":
        data = event.get("data") or {}
        apply_paystack_result(data.get("reference", ""), data)
    return HttpResponse(status=200)
