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
    title = models.CharField(max_length=200)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.SET_NULL, null=True, blank=True)
    credits = models.IntegerField(default=3)
    total_planned_classes = models.PositiveIntegerField(
        default=40,
        help_text="Total number of sessions required to complete the curriculum"
    )

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

class Notification(models.Model):
    class NotificationType(models.TextChoices):
        GENERAL = 'GENERAL', 'General Notice'
        VERIFICATION = 'VERIFICATION', 'Verification & Registration'
        SECURITY = 'SECURITY', 'Security & Profile Update'
        ATTENDANCE = 'ATTENDANCE', 'Attendance Alert'
        URGENT = 'URGENT', 'Urgent Announcement'

    class TargetAudience(models.TextChoices):
        ALL = 'ALL', 'Everyone'
        TEACHERS = 'TEACHERS', 'Faculty / Teachers Only'
        STUDENTS = 'STUDENTS', 'Students Only'
        STAFF = 'STAFF', 'Admin / Staff Only'

    recipient = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="If blank, broadcasted to the selected Target Audience."
    )
    target_audience = models.CharField(
        max_length=20,
        choices=TargetAudience.choices,
        default=TargetAudience.ALL
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Leave blank to broadcast across all departments."
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(
        max_length=20,
        choices=NotificationType.choices,
        default=NotificationType.GENERAL
    )
    is_read = models.BooleanField(default=False)
    is_hidden = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.target_audience}] {self.title}"

class CourseApplication(models.Model):
    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Approval'
        APPROVED = 'APPROVED', 'Approved'
        REJECTED = 'REJECTED', 'Rejected'

    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='course_applications')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='applications')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='course_applications')
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    applied_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_remarks = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = ('student', 'course', 'academic_session')
        ordering = ['-applied_at']

    def __str__(self):
        return f"{self.student.roll_number} - {self.course.code} ({self.status})"

class Timetable(models.Model):
    class DayOfWeek(models.TextChoices):
        MONDAY = 'MONDAY', 'Monday'
        TUESDAY = 'TUESDAY', 'Tuesday'
        WEDNESDAY = 'WEDNESDAY', 'Wednesday'
        THURSDAY = 'THURSDAY', 'Thursday'
        FRIDAY = 'FRIDAY', 'Friday'
        SATURDAY = 'SATURDAY', 'Saturday'

    class ClassType(models.TextChoices):
        LECTURE = 'LECTURE', 'Lecture (1 Hour)'
        PRACTICAL = 'PRACTICAL', 'Practical Lab (2 Hours)'

    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='schedules')
    academic_session = models.ForeignKey(AcademicSession, on_delete=models.CASCADE, related_name='schedules')
    class_type = models.CharField(
        max_length=15, 
        choices=ClassType.choices, 
        default=ClassType.LECTURE
    )
    day = models.CharField(max_length=10, choices=DayOfWeek.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room_number = models.CharField(max_length=30)
    is_extra_class = models.BooleanField(
        default=False, 
        help_text="Designates this session as an extra/makeup class"
    )
    specific_date = models.DateField(
        null=True, 
        blank=True, 
        help_text="Required if scheduling an extra class on a specific date"
    )

    class Meta:
        ordering = ['day', 'start_time']

    def __str__(self):
        extra_tag = f" [EXTRA CLASS: {self.specific_date}]" if self.is_extra_class else ""
        return f"{self.course.code} | {self.get_day_display()} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')}) - Room {self.room_number}{extra_tag}"