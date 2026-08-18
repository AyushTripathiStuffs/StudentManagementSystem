from django.contrib import admin
from .models import Department, AcademicSession, Teacher, Student, Course, Enrollment, Attendance, CourseApplication


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(AcademicSession)
class AcademicSessionAdmin(admin.ModelAdmin):
    list_display = ('name', 'start_date', 'end_date', 'is_current')
    list_filter = ('is_current',)
    search_fields = ('name',)


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('employee_id', 'get_full_name', 'department', 'designation', 'joining_date')
    list_filter = ('department', 'designation')
    search_fields = ('employee_id', 'user__first_name', 'user__last_name', 'user__username', 'user__email')
    raw_id_fields = ('user',)

    @admin.display(description='Name')
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class EnrollmentInline(admin.TabularInline):
    model = Enrollment
    extra = 1
    raw_id_fields = ('course', 'academic_session')


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('roll_number', 'get_full_name', 'department', 'academic_session', 'admission_date')
    list_filter = ('department', 'academic_session')
    search_fields = ('roll_number', 'user__first_name', 'user__last_name', 'user__username', 'user__email')
    raw_id_fields = ('user',)
    inlines = [EnrollmentInline]

    @admin.display(description='Name')
    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ('code', 'title', 'department', 'teacher', 'credits')
    list_filter = ('department', 'credits')
    search_fields = ('code', 'title')
    filter_horizontal = ('prerequisites',)
    raw_id_fields = ('teacher',)


@admin.register(Enrollment)
class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'academic_session', 'enrolled_at')
    list_filter = ('academic_session', 'course__department')
    search_fields = ('student__roll_number', 'student__user__first_name', 'student__user__last_name', 'course__code', 'course__title')
    raw_id_fields = ('student', 'course')


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'date', 'status', 'marked_by')
    list_filter = ('status', 'date', 'course')
    search_fields = ('student__roll_number', 'student__user__first_name', 'student__user__last_name', 'course__code')
    date_hierarchy = 'date'
    raw_id_fields = ('student', 'course', 'marked_by')

@admin.register(CourseApplication)
class CourseApplicationAdmin(admin.ModelAdmin):
    list_display = ('student', 'course', 'academic_session', 'status', 'applied_at', 'reviewed_by')
    list_filter = ('status', 'academic_session', 'course__department')
    search_fields = ('student__roll_number', 'student__user__first_name', 'course__code', 'course__title')
    raw_id_fields = ('student', 'course', 'reviewed_by')