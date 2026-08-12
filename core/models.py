from django.db import models
from django.conf import settings
from django.core.exceptions import ValidationError

# Create your models here.
User = settings.AUTH_USER_MODEL


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=10, unique=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class AcademicSession(models.Model):
    name = models.CharField(max_length=20, help_text="e.g., 2025-2026")
    start_date = models.DateField()
    end_date = models.DateField()
    is_current = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if self.is_current:
            AcademicSession.objects.filter(is_current=True).exclude(pk=self.pk).update(is_current=False)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher_profile')
    employee_id = models.CharField(max_length=20, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='teachers')
    designation = models.CharField(max_length=50, blank=True)
    joining_date = models.DateField()

    class Meta:
        indexes = [
            models.Index(fields=['employee_id']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.employee_id})"

class Student(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student_profile')
    roll_number = models.CharField(max_length=30, unique=True)
    department = models.ForeignKey(Department, on_delete=models.PROTECT, related_name='students')
    admission_date = models.DateField()
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.PROTECT, related_name='students')

    class Meta:
        indexes = [
            models.Index(fields=['roll_number']),
        ]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.username} ({self.roll_number})"


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    title = models.CharField(max_length=150)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name='courses')
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True, related_name='courses')
    credits = models.PositiveSmallIntegerField(default=3)
    prerequisites = models.ManyToManyField('self', symmetrical=False, blank=True, related_name='prerequisite_for')

    def __str__(self):
        return f"{self.code} - {self.title}"


class Enrollment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_session')

    def __str__(self):
        return f"{self.student.roll_number} enrolled in {self.course.code}"


class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'PRESENT', 'Present'
        ABSENT = 'ABSENT', 'Absent'
        LATE = 'LATE', 'Late'
        EXCUSED = 'EXCUSED', 'Excused'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_records')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='attendance_records')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PRESENT)
    marked_by = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, related_name='marked_attendances')
    remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('student', 'course', 'date')
        indexes = [
            models.Index(fields=['course', 'date']),
            models.Index(fields=['student', 'status']),
        ]

    def __str__(self):
        return f"{self.student.roll_number} - {self.course.code} - {self.date}: {self.status}"