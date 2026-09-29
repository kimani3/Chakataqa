from django.test import TestCase
from django.urls import reverse

from .models import ContactMessage


class IndexViewTests(TestCase):
    def test_index_renders(self):
        response = self.client.get(reverse("core:index"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "core/index.html")
        self.assertContains(response, 'id="contact"')

    def test_valid_contact_submission_saves_and_redirects(self):
        response = self.client.post(
            reverse("core:index"),
            {
                "name": "Amina",
                "email": "amina@example.com",
                "organisation": "Green Estate",
                "message": "We'd like weekly pickups.",
            },
        )
        self.assertRedirects(response, reverse("core:index") + "#contact")
        self.assertEqual(ContactMessage.objects.count(), 1)

    def test_invalid_contact_submission_shows_errors(self):
        response = self.client.post(
            reverse("core:index"), {"name": "", "email": "not-an-email"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ContactMessage.objects.count(), 0)
        self.assertTrue(response.context["form"].errors)
