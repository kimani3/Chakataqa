from django import forms
from django.contrib import admin, messages
from django.utils import timezone

from .models import Deposit, ProfitAllocation, ProfitDistribution
from .services import capital_by_investor, distribute_profit


@admin.register(Deposit)
class DepositAdmin(admin.ModelAdmin):
    list_display = ("reference", "investor", "amount", "currency", "status", "created_at", "paid_at")
    list_filter = ("status", "currency")
    search_fields = ("reference", "investor__username", "investor__email")
    date_hierarchy = "created_at"

    # Deposit status only ever comes from Paystack.
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class ProfitAllocationInline(admin.TabularInline):
    model = ProfitAllocation
    extra = 0
    can_delete = False
    fields = ("investor", "capital_at_time", "share_percent", "amount", "status", "paid_at")
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


class ProfitDistributionForm(forms.ModelForm):
    class Meta:
        model = ProfitDistribution
        fields = ["title", "total_profit", "as_of", "notes"]

    def clean(self):
        cleaned = super().clean()
        as_of = cleaned.get("as_of")
        if self.instance.pk is None and as_of and not capital_by_investor(as_of):
            raise forms.ValidationError(
                "No investor had confirmed capital on that date, so there is no one to share this profit with."
            )
        return cleaned


@admin.register(ProfitDistribution)
class ProfitDistributionAdmin(admin.ModelAdmin):
    form = ProfitDistributionForm
    list_display = ("title", "total_profit", "as_of", "created_at")
    inlines = [ProfitAllocationInline]

    def get_readonly_fields(self, request, obj=None):
        # Once allocated, the numbers must not change under investors' feet.
        return ("title", "total_profit", "as_of") if obj else ()

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        if not change:
            # The admin wraps this in a transaction, so a failure rolls back the save too.
            allocations = distribute_profit(obj)
            self.message_user(
                request, f"Profit allocated to {len(allocations)} investor(s).", messages.SUCCESS
            )

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(ProfitAllocation)
class ProfitAllocationAdmin(admin.ModelAdmin):
    list_display = ("investor", "distribution", "share_percent", "amount", "status", "paid_at")
    list_filter = ("status", "distribution")
    search_fields = ("investor__username", "investor__email")
    actions = ["mark_paid"]
    readonly_fields = ("distribution", "investor", "capital_at_time", "share_percent", "amount", "status", "paid_at")

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Mark selected allocations as paid")
    def mark_paid(self, request, queryset):
        updated = queryset.filter(status=ProfitAllocation.Status.OWED).update(
            status=ProfitAllocation.Status.PAID, paid_at=timezone.now()
        )
        self.message_user(request, f"{updated} allocation(s) marked as paid.")
