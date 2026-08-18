from django.contrib.auth.models import AbstractUser
from django.db import models

# Create your models here.
class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = "ADMIN", "Admin"
        TEACHER = "TEACHER", "Teacher"
        STUDENT = "STUDENT", "Student"
        PARENT = "PARENT", "Parent"

    role = models.CharField(max_length=10, choices=Role.choices, default=Role.ADMIN)
    phone_number = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    password_change_count = models.PositiveIntegerField(
        default=0,
        help_text="Tracks number of times user changed password (Maximum 2 allowed)"
    )