from django.db import models


class ContactMessage(models.Model):
    """A message submitted through the landing page contact form."""

    name = models.CharField(max_length=120)
    email = models.EmailField()
    organisation = models.CharField(max_length=160, blank=True)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} <{self.email}>"
