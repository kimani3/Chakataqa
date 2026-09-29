from django.contrib import messages
from django.shortcuts import redirect, render
from django.urls import reverse

from . import content
from .forms import ContactForm


def index(request):
    if request.method == "POST":
        form = ContactForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(
                request, "Thanks for reaching out! We'll get back to you shortly."
            )
            return redirect(reverse("core:index") + "#contact")
    else:
        form = ContactForm()

    context = {
        "form": form,
        "stats": content.STATS,
        "steps": content.STEPS,
        "services": content.SERVICES,
        "testimonials": content.TESTIMONIALS,
    }
    return render(request, "core/index.html", context)
