from django.urls import reverse

from . import content


def site_nav(request):
    """Nav links for every page; landing-page anchors work from any URL."""
    home = reverse("core:index")
    links = [(f"{home}{anchor}", label) for anchor, label in content.NAV_LINKS]
    links.append((reverse("investors:dashboard"), "Investors"))
    return {"nav_links": links}
