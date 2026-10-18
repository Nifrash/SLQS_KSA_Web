from django.db import models


class ContactInquiry(models.Model):
    class Topic(models.TextChoices):
        GENERAL = 'GENERAL', 'General enquiry'
        MEMBERSHIP = 'MEMBERSHIP', 'Membership enquiry'
        EVENTS = 'EVENTS', 'Events and partnerships'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional collaboration'

    class Status(models.TextChoices):
        NEW = 'NEW', 'New'
        IN_PROGRESS = 'IN_PROGRESS', 'In progress'
        CLOSED = 'CLOSED', 'Closed'

    full_name = models.CharField(max_length=120)
    email = models.EmailField()
    topic = models.CharField(max_length=20, choices=Topic.choices, default=Topic.GENERAL)
    message = models.TextField(max_length=4000)
    privacy_consent = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name_plural = 'Contact inquiries'

    def __str__(self):
        return f'{self.full_name} — {self.get_topic_display()}'
