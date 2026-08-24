from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.forms import formset_factory
from .models import Department, AcademicSession, Teacher, Student, Course, Enrollment, Attendance
from .forms import (
    CourseEnrollmentForm, DepartmentForm, AcademicSessionForm, CourseForm, ExtraClassForm, 
    StudentForm, TeacherForm, AttendanceFilterForm, StudentAttendanceForm, BroadcastNotificationForm
)
from accounts.models import User
from .models import Notification,CourseApplication
from django.utils import timezone
import secrets
import string
from datetime import date
from .models import Timetable
from .forms import TimetableForm
from datetime import date, datetime, timedelta
from django.utils import timezone
from .models import Course, Enrollment, Attendance, Timetable
from django.http import JsonResponse
from django.views.decorators.http import require_POST

def admin_required(user):
    return user.is_authenticated and (user.role == User.Role.ADMIN or user.is_superuser)


def teacher_or_admin_required(user):
    return user.is_authenticated and (user.role in [User.Role.ADMIN, User.Role.TEACHER] or user.is_superuser)

@login_required
def dashboard(request):
    user = request.user
    context = {'user_role': user.role}

    if user.role == User.Role.ADMIN or user.is_superuser:
        context.update({
            'total_students': Student.objects.count(),
            'total_teachers': Teacher.objects.count(),
            'total_courses': Course.objects.count(),
            'total_departments': Department.objects.count(),
            'recent_students': Student.objects.select_related('user', 'department').order_by('-id')[:5],
            'recent_attendances': Attendance.objects.select_related('student__user', 'course').order_by('-date')[:5],
        })
    elif user.role == User.Role.TEACHER:
        teacher = getattr(user, 'teacher_profile', None)
        assigned_courses = Course.objects.filter(teacher=teacher) if teacher else Course.objects.none()
        context.update({
            'teacher': teacher,
            'courses': assigned_courses,
            'total_courses': assigned_courses.count(),
        })
    elif user.role == User.Role.STUDENT:
        student = getattr(user, 'student_profile', None)
        enrollments = Enrollment.objects.filter(student=student).select_related('course') if student else []
        attendance_stats = Attendance.objects.filter(student=student).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status=Attendance.Status.PRESENT))
        ) if student else {'total': 0, 'present': 0}
        
        pct = (attendance_stats['present'] / attendance_stats['total'] * 100) if attendance_stats['total'] > 0 else 0
        context.update({
            'student': student,
            'enrollments': enrollments,
            'attendance_percentage': round(pct, 2),
            'attendance_stats': attendance_stats,
        })

    return render(request, 'core/dashboard.html', context)

@login_required
def student_list(request):
    students = Student.objects.select_related('user', 'department', 'academic_session').all()
    return render(request, 'core/student_list.html', {'students': students})


@login_required
@user_passes_test(admin_required)
def student_create(request):
    if request.method == 'POST':
        form = StudentForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    password=form.cleaned_data['password'],
                    role=User.Role.STUDENT
                )
                student = form.save(commit=False)
                student.user = user
                student.save()

                Notification.objects.create(
                    recipient=user,
                    title="Account Created",
                    message=f"Welcome {user.first_name}! Your account has been registered with Roll Number {student.roll_number}.",
                    notification_type=Notification.NotificationType.VERIFICATION
                )

            messages.success(request, f"Student {user.get_full_name()} added successfully.")
            return redirect('core:student_list')
    else:
        form = StudentForm()
    return render(request, 'core/student_form.html', {'form': form, 'title': 'Add New Student'})

@login_required
@user_passes_test(admin_required)
def student_update(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        form = StudentForm(request.POST, instance=student)
        if form.is_valid():
            with transaction.atomic():
                user = student.user
                user.username = form.cleaned_data['username']
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                if form.cleaned_data.get('password'):
                    user.set_password(form.cleaned_data['password'])
                user.save()
                form.save()
            messages.success(request, "Student updated successfully.")
            return redirect('core:student_list')
    else:
        form = StudentForm(instance=student)
    return render(request, 'core/student_form.html', {'form': form, 'title': 'Edit Student'})


@login_required
@user_passes_test(admin_required)
def student_delete(request, pk):
    student = get_object_or_404(Student, pk=pk)
    if request.method == 'POST':
        student.user.delete()
        messages.success(request, "Student deleted successfully.")
        return redirect('core:student_list')
    return render(request, 'core/confirm_delete.html', {'object': student, 'title': 'Delete Student'})

@login_required
def teacher_list(request):
    teachers = Teacher.objects.select_related('user', 'department').all()
    return render(request, 'core/teacher_list.html', {'teachers': teachers})


@login_required
@user_passes_test(admin_required)
def teacher_create(request):
    if request.method == 'POST':
        form = TeacherForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                user = User.objects.create_user(
                    username=form.cleaned_data['username'],
                    email=form.cleaned_data['email'],
                    first_name=form.cleaned_data['first_name'],
                    last_name=form.cleaned_data['last_name'],
                    password=form.cleaned_data['password'],
                    role=User.Role.TEACHER
                )
                teacher = form.save(commit=False)
                teacher.user = user
                teacher.save()

            messages.success(request, f"Teacher {user.get_full_name()} added successfully.")
            return redirect('core:teacher_list')
    else:
        form = TeacherForm()
    return render(request, 'core/teacher_form.html', {'form': form, 'title': 'Add New Teacher'})

@login_required
@user_passes_test(admin_required)
def teacher_update(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        form = TeacherForm(request.POST, instance=teacher)
        if form.is_valid():
            with transaction.atomic():
                user = teacher.user
                user.username = form.cleaned_data['username']
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['first_name']
                user.last_name = form.cleaned_data['last_name']
                if form.cleaned_data.get('password'):
                    user.set_password(form.cleaned_data['password'])
                user.save()
                form.save()
            messages.success(request, "Teacher details updated successfully.")
            return redirect('core:teacher_list')
    else:
        form = TeacherForm(instance=teacher)
    return render(request, 'core/teacher_form.html', {'form': form, 'title': 'Edit Teacher'})

@login_required
@user_passes_test(admin_required)
def teacher_delete(request, pk):
    teacher = get_object_or_404(Teacher, pk=pk)
    if request.method == 'POST':
        teacher.user.delete()
        messages.success(request, "Teacher deleted successfully.")
        return redirect('core:teacher_list')
    return render(request, 'core/confirm_delete.html', {'object': teacher, 'title': 'Delete Teacher'})

@login_required
def course_list(request):
    courses = Course.objects.select_related('department', 'teacher__user').all()
    return render(request, 'core/course_list.html', {'courses': courses})


@login_required
@user_passes_test(admin_required)
def course_create(request):
    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Course created successfully.")
            return redirect('core:course_list')
    else:
        form = CourseForm()
    return render(request, 'core/course_form.html', {'form': form, 'title': 'Add New Course'})


@login_required
@user_passes_test(admin_required)
def course_update(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, f"Course '{course.code}' updated successfully.")
            return redirect('core:course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'core/course_form.html', {'form': form, 'title': f'Edit Course: {course.code}'})


@login_required
@user_passes_test(admin_required)
def course_delete(request, pk):
    course = get_object_or_404(Course, pk=pk)
    if request.method == 'POST':
        course.delete()
        messages.success(request, "Course deleted successfully.")
        return redirect('core:course_list')
    return render(request, 'core/confirm_delete.html', {'object': course, 'title': 'Delete Course'})

@login_required
@user_passes_test(teacher_or_admin_required)
def mark_attendance(request):
    filter_form = AttendanceFilterForm(request.GET or None, user=request.user)
    AttendanceFormSet = formset_factory(StudentAttendanceForm, extra=0)

    course_id = request.GET.get('course')
    selected_date_str = request.GET.get('date')

    now = timezone.localtime(timezone.now())
    today = now.date()
    current_time = now.time()

    is_admin = request.user.role == User.Role.ADMIN or request.user.is_superuser
    is_teacher = request.user.role == User.Role.TEACHER

    course = None
    formset = None
    students_list = []
    is_locked_for_teacher = False
    is_too_early = False
    allowed_start_time = None

    if course_id and selected_date_str:
        try:
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except ValueError:
            selected_date = today

        # Rule 1: No future dates
        if selected_date > today:
            messages.error(request, "Attendance cannot be marked or viewed for future dates.")
            return redirect('core:mark_attendance')

        course = get_object_or_404(Course, id=course_id)

        # Fetch timetable slot to determine end time
        day_name = selected_date.strftime('%A').upper()
        schedule_slot = Timetable.objects.filter(course=course, day=day_name).first()

        # Rule 2: Enforce 10-minute early restriction on today's classes
        if selected_date == today and schedule_slot:
            end_dt = datetime.combine(today, schedule_slot.end_time)
            opening_dt = end_dt - timedelta(minutes=10)
            allowed_start_time = opening_dt.time()

            if current_time < allowed_start_time and not is_admin:
                is_too_early = True

        # Rule 3: Lock past dates for teachers
        is_past_date = selected_date < today
        if is_teacher and is_past_date:
            is_locked_for_teacher = True

        # Total Lock State
        is_disabled = is_locked_for_teacher or is_too_early

        enrollments = Enrollment.objects.filter(course=course).select_related('student__user').order_by('student__roll_number')
        existing_records = {
            att.student_id: att 
            for att in Attendance.objects.filter(course=course, date=selected_date)
        }

        if request.method == 'POST':
            if selected_date > today:
                messages.error(request, "Cannot submit attendance for future dates.")
                return redirect('core:mark_attendance')

            if is_too_early:
                messages.error(request, f"Too early! Attendance opens at {allowed_start_time.strftime('%I:%M %p')} (10 mins before class end).")
                return redirect(f"{request.path}?course={course_id}&date={selected_date_str}")

            if is_locked_for_teacher:
                messages.error(request, "Teachers can only mark attendance for today. Contact Admin for past changes.")
                return redirect(f"{request.path}?course={course_id}&date={selected_date_str}")

            formset = AttendanceFormSet(request.POST)
            if formset.is_valid():
                teacher_profile = getattr(request.user, 'teacher_profile', None)
                with transaction.atomic():
                    for form in formset:
                        student_id = form.cleaned_data['student_id']
                        status = form.cleaned_data['status']
                        remarks = form.cleaned_data['remarks']
                        Attendance.objects.update_or_create(
                            student_id=student_id,
                            course=course,
                            date=selected_date,
                            defaults={
                                'status': status,
                                'remarks': remarks,
                                'marked_by': teacher_profile,
                            }
                        )
                messages.success(request, f"Attendance saved for {course.code} on {selected_date_str}.")
                return redirect(f"{request.path}?course={course_id}&date={selected_date_str}")
        else:
            initial_data = []
            for enrollment in enrollments:
                student = enrollment.student
                rec = existing_records.get(student.id)
                initial_data.append({
                    'student_id': student.id,
                    'status': rec.status if rec else Attendance.Status.PRESENT,
                    'remarks': rec.remarks if rec else '',
                })
                students_list.append(student)
            formset = AttendanceFormSet(initial=initial_data)

    context = {
        'filter_form': filter_form,
        'formset': formset,
        'course': course,
        'selected_date': selected_date_str,
        'today': today.strftime('%Y-%m-%d'),
        'students_list': students_list,
        'form_and_students': zip(formset.forms, students_list) if formset else [],
        'is_locked_for_teacher': is_locked_for_teacher,
        'is_too_early': is_too_early,
        'allowed_start_time': allowed_start_time,
        'is_disabled': is_locked_for_teacher or is_too_early,
    }
    return render(request, 'core/mark_attendance.html', context)

@login_required
def attendance_report(request):
    user = request.user
    if user.role == User.Role.STUDENT:
        student = getattr(user, 'student_profile', None)
        records = Attendance.objects.filter(student=student).select_related('course').order_by('-date')
    else:
        records = Attendance.objects.select_related('student__user', 'course').order_by('-date')[:100]

    return render(request, 'core/attendance_report.html', {'records': records})

@login_required
@user_passes_test(admin_required)
def broadcast_notification(request):
    if request.method == 'POST':
        form = BroadcastNotificationForm(request.POST)
        if form.is_valid():
            notice = form.save(commit=False)
            notice.recipient = None
            notice.save()
            messages.success(request, f"Notice '{notice.title}' broadcasted to {notice.get_target_audience_display()}!")
            return redirect('core:notification_list')
    else:
        form = BroadcastNotificationForm()

    return render(request, 'core/broadcast_form.html', {'form': form})


@login_required
def notification_list(request):
    user = request.user
    query = Q(recipient=user)
    broadcast_role_filter = Q(target_audience=Notification.TargetAudience.ALL)

    if user.role == User.Role.TEACHER:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.TEACHERS)
        if hasattr(user, 'teacher_profile'):
            dept = user.teacher_profile.department
            broadcast_role_filter &= (Q(department=dept) | Q(department__isnull=True))

    elif user.role == User.Role.STUDENT:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STUDENTS)
        if hasattr(user, 'student_profile'):
            dept = user.student_profile.department
            broadcast_role_filter &= (Q(department=dept) | Q(department__isnull=True))

    elif user.role == User.Role.ADMIN or user.is_superuser:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STAFF)

    user_notifications = Notification.objects.filter(
        query | (Q(recipient__isnull=True) & broadcast_role_filter)
    ).distinct()

    Notification.objects.filter(recipient=request.user, is_read=False).update(is_read=True)

    return render(request, 'core/notifications.html', {'notifications': user_notifications})

@login_required
@user_passes_test(teacher_or_admin_required)
def teacher_courses_dashboard(request):
    if request.user.role == User.Role.ADMIN or request.user.is_superuser:
        courses = Course.objects.select_related('department', 'teacher__user').annotate(
            total_students=Count('enrollments', distinct=True),
            total_sessions=Count('attendance_records__date', distinct=True)
        )
    else:
        teacher = getattr(request.user, 'teacher_profile', None)
        courses = Course.objects.filter(teacher=teacher).select_related('department').annotate(
            total_students=Count('enrollments', distinct=True),
            total_sessions=Count('attendance_records__date', distinct=True)
        )

    return render(request, 'core/teacher_courses.html', {'courses': courses})

@login_required
@user_passes_test(teacher_or_admin_required)
def course_roster_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    if request.user.role == User.Role.TEACHER and course.teacher != getattr(request.user, 'teacher_profile', None):
        messages.error(request, "Unauthorized access to course roster.")
        return redirect('core:teacher_courses')
    total_classes = Attendance.objects.filter(course=course).values('date').distinct().count()
    enrollments = Enrollment.objects.filter(course=course).select_related('student__user', 'student__department')
    
    roster_data = []
    for enrollment in enrollments:
        student = enrollment.student
        attended = Attendance.objects.filter(
            course=course, 
            student=student, 
            status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]
        ).count()
        absent = Attendance.objects.filter(
            course=course, 
            student=student, 
            status=Attendance.Status.ABSENT
        ).count()
        
        pct = round((attended / total_classes * 100), 1) if total_classes > 0 else 0.0
        
        roster_data.append({
            'student': student,
            'enrolled_at': enrollment.enrolled_at,
            'attended_count': attended,
            'absent_count': absent,
            'attendance_pct': pct,
            'is_defaulter': pct < 75.0 and total_classes >= 3
        })

    context = {
        'course': course,
        'total_classes': total_classes,
        'roster_data': roster_data,
        'total_enrolled': len(roster_data),
    }
    return render(request, 'core/course_roster.html', context)

@login_required
@user_passes_test(teacher_or_admin_required)
def take_course_attendance(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    now = timezone.localtime(timezone.now())
    today = now.date()
    current_time = now.time()

    selected_date_str = request.GET.get('date', today.strftime('%Y-%m-%d'))
    try:
        selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
    except ValueError:
        selected_date = today

    is_admin = request.user.role == User.Role.ADMIN or request.user.is_superuser
    is_teacher = request.user.role == User.Role.TEACHER

    if is_teacher and course.teacher != getattr(request.user, 'teacher_profile', None):
        messages.error(request, "Unauthorized access to course attendance.")
        return redirect('core:teacher_courses')

    day_name = selected_date.strftime('%A').upper()
    schedule_slot = Timetable.objects.filter(course=course, day=day_name).first()

    is_future_date = selected_date > today
    is_past_date = selected_date < today
    is_too_early = False
    allowed_start_time = None

    if selected_date == today and schedule_slot:
        end_dt = datetime.combine(today, schedule_slot.end_time)
        opening_dt = end_dt - timedelta(minutes=10)
        allowed_start_time = opening_dt.time()
        if current_time < allowed_start_time:
            is_too_early = True

    is_locked_for_teacher = (is_teacher and is_past_date) or is_too_early or is_future_date

    enrollments = Enrollment.objects.filter(course=course).select_related('student__user').order_by('student__roll_number')
    existing_attendance = {
        att.student_id: att 
        for att in Attendance.objects.filter(course=course, date=selected_date)
    }

    if request.method == 'POST':
        if is_future_date:
            messages.error(request, "Attendance cannot be submitted for future dates.")
            return redirect(f"{request.path}?date={today.strftime('%Y-%m-%d')}")

        if is_too_early:
            messages.error(request, f"Too early! Attendance opens at {allowed_start_time.strftime('%I:%M %p')} (10 mins before class end).")
            return redirect(f"{request.path}?date={selected_date_str}")

        if is_teacher and is_past_date:
            messages.error(request, "Teachers can only mark attendance for today's classes.")
            return redirect(f"{request.path}?date={selected_date_str}")

        with transaction.atomic():
            teacher = getattr(request.user, 'teacher_profile', None)
            for enrollment in enrollments:
                student_id = enrollment.student.id
                status = request.POST.get(f'status_{student_id}', Attendance.Status.PRESENT)
                remarks = request.POST.get(f'remarks_{student_id}', '')

                Attendance.objects.update_or_create(
                    student_id=student_id,
                    course=course,
                    date=selected_date,
                    defaults={
                        'status': status,
                        'remarks': remarks,
                        'marked_by': teacher,
                    }
                )

        messages.success(request, f"Attendance successfully saved for {course.code} on {selected_date_str}.")
        return redirect(f"{request.path}?date={selected_date_str}")

    student_records = []
    for enrollment in enrollments:
        student = enrollment.student
        existing = existing_attendance.get(student.id)
        student_records.append({
            'student': student,
            'status': existing.status if existing else Attendance.Status.PRESENT,
            'remarks': existing.remarks if existing else '',
        })

    context = {
        'course': course,
        'today': today.strftime('%Y-%m-%d'),
        'selected_date': selected_date_str,
        'schedule_slot': schedule_slot,
        'student_records': student_records,
        'status_choices': Attendance.Status.choices,
        'is_locked_for_teacher': is_locked_for_teacher,
        'is_too_early': is_too_early,
        'allowed_start_time': allowed_start_time,
        'is_past_date': is_past_date,
        'is_admin': is_admin,
    }
    return render(request, 'core/take_attendance.html', context)

@login_required
def student_courses_view(request):
    if not (request.user.role == User.Role.STUDENT or hasattr(request.user, 'student_profile')):
        messages.error(request, "Only registered students can access this portal.")
        return redirect('core:dashboard')

    student = request.user.student_profile
    enrollments = Enrollment.objects.filter(student=student).select_related(
        'course__department', 
        'course__teacher__user', 
        'academic_session'
    )

    enrolled_courses = []
    for enr in enrollments:
        course = enr.course
        total_classes = Attendance.objects.filter(course=course).values('date').distinct().count()
        attended = Attendance.objects.filter(
            course=course, 
            student=student, 
            status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]
        ).count()
        absent = Attendance.objects.filter(
            course=course, 
            student=student, 
            status=Attendance.Status.ABSENT
        ).count()
        
        pct = round((attended / total_classes * 100), 1) if total_classes > 0 else 0.0

        enrolled_courses.append({
            'enrollment': enr,
            'course': course,
            'total_classes': total_classes,
            'attended': attended,
            'absent': absent,
            'pct': pct,
            'status_alert': 'danger' if pct < 75.0 and total_classes >= 3 else 'success'
        })

    return render(request, 'core/student_courses.html', {'enrolled_courses': enrolled_courses})

@login_required
def student_course_attendance_detail(request, course_id):
    student = get_object_or_404(Student, user=request.user)
    course = get_object_or_404(Course, id=course_id)
    
    # Verify enrollment
    enrollment = get_object_or_404(Enrollment, student=student, course=course)
    logs = Attendance.objects.filter(student=student, course=course).order_by('-date')

    total_classes = logs.count()
    attended = logs.filter(status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]).count()
    pct = round((attended / total_classes * 100), 1) if total_classes > 0 else 0.0

    context = {
        'course': course,
        'logs': logs,
        'total_classes': total_classes,
        'attended': attended,
        'pct': pct,
        'enrollment': enrollment,
    }
    return render(request, 'core/student_course_detail.html', context)

@login_required
@user_passes_test(admin_required)
def manage_enrollments(request):
    courses = Course.objects.select_related('department', 'teacher__user').all()
    sessions = AcademicSession.objects.all().order_by('-is_current', '-start_date')
    departments = Department.objects.all()

    selected_course_id = request.GET.get('course')
    selected_session_id = request.GET.get('session')
    dept_filter = request.GET.get('department')
    search_query = request.GET.get('q', '').strip()

    selected_course = None
    selected_session = None
    students_data = []

    if not selected_session_id:
        active_sess = AcademicSession.objects.filter(is_current=True).first()
        if active_sess:
            selected_session_id = str(active_sess.id)

    if selected_session_id:
        selected_session = AcademicSession.objects.filter(id=selected_session_id).first()

    if selected_course_id:
        selected_course = Course.objects.filter(id=selected_course_id).first()

    if selected_course and selected_session:
        enrolled_student_ids = set(
            Enrollment.objects.filter(
                course=selected_course,
                academic_session=selected_session
            ).values_list('student_id', flat=True)
        )

        students_qs = Student.objects.select_related('user', 'department', 'academic_session')
        
        if dept_filter:
            students_qs = students_qs.filter(department_id=dept_filter)
        elif selected_course.department:
            students_qs = students_qs.filter(department=selected_course.department)

        if search_query:
            students_qs = students_qs.filter(
                Q(roll_number__icontains=search_query) |
                Q(user__first_name__icontains=search_query) |
                Q(user__last_name__icontains=search_query) |
                Q(user__username__icontains=search_query)
            )

        for st in students_qs:
            students_data.append({
                'student': st,
                'is_enrolled': st.id in enrolled_student_ids
            })

    if request.method == 'POST' and selected_course and selected_session:
        action = request.POST.get('action')
        selected_student_ids = request.POST.getlist('selected_students')

        if not selected_student_ids:
            messages.warning(request, "No students were selected.")
            return redirect(f"{request.path}?course={selected_course.id}&session={selected_session.id}")

        selected_student_ids = [int(sid) for sid in selected_student_ids]

        with transaction.atomic():
            if action == 'enroll':
                created_count = 0
                for sid in selected_student_ids:
                    _, created = Enrollment.objects.get_or_create(
                        student_id=sid,
                        course=selected_course,
                        academic_session=selected_session
                    )
                    if created:
                        created_count += 1
                messages.success(request, f"Successfully enrolled {created_count} students in {selected_course.code}.")

            elif action == 'unenroll':
                deleted_count, _ = Enrollment.objects.filter(
                    student_id__in=selected_student_ids,
                    course=selected_course,
                    academic_session=selected_session
                ).delete()
                messages.info(request, f"Removed {deleted_count} student enrollments from {selected_course.code}.")

        return redirect(f"{request.path}?course={selected_course.id}&session={selected_session.id}")

    context = {
        'courses': courses,
        'sessions': sessions,
        'departments': departments,
        'selected_course': selected_course,
        'selected_session': selected_session,
        'selected_dept': dept_filter,
        'search_query': search_query,
        'students_data': students_data,
        'total_enrolled_count': sum(1 for s in students_data if s['is_enrolled']),
    }
    return render(request, 'core/manage_enrollments.html', context)

@login_required
def student_course_registration(request):
    if not (request.user.role == User.Role.STUDENT or hasattr(request.user, 'student_profile')):
        messages.error(request, "Only registered students can apply for courses.")
        return redirect('core:dashboard')

    student = request.user.student_profile
    active_session = AcademicSession.objects.filter(is_current=True).first()

    if not active_session:
        messages.error(request, "No active academic session found for application.")
        return redirect('core:student_courses')
    department_courses = Course.objects.filter(
        department=student.department
    ).select_related('teacher__user', 'department')
    existing_applications = {
        app.course_id: app 
        for app in CourseApplication.objects.filter(student=student, academic_session=active_session)
    }

    courses_status = []
    for course in department_courses:
        app = existing_applications.get(course.id)
        courses_status.append({
            'course': course,
            'application': app,
            'status': app.status if app else 'NOT_APPLIED',
        })

    if request.method == 'POST':
        course_id = request.POST.get('course_id')
        target_course = get_object_or_404(Course, id=course_id, department=student.department)

        app, created = CourseApplication.objects.get_or_create(
            student=student,
            course=target_course,
            academic_session=active_session,
            defaults={'status': CourseApplication.Status.PENDING}
        )

        if created:
            Notification.objects.create(
                recipient=None,
                target_audience=Notification.TargetAudience.STAFF,
                title="New Course Application Submitted",
                message=f"Student {student.user.get_full_name()} ({student.roll_number}) applied for {target_course.code}: {target_course.title}.",
                notification_type=Notification.NotificationType.GENERAL
            )
            messages.success(request, f"Application for {target_course.code} submitted. Awaiting administrative approval.")
        elif app.status == CourseApplication.Status.REJECTED:
            app.status = CourseApplication.Status.PENDING
            app.admin_remarks = ''
            app.applied_at = timezone.now()
            app.save()
            messages.success(request, f"Re-applied for {target_course.code}. Awaiting review.")
        else:
            messages.info(request, f"You have already applied for {target_course.code}.")

        return redirect('core:student_course_registration')

    context = {
        'student': student,
        'active_session': active_session,
        'courses_status': courses_status,
        'total_applied': len(existing_applications),
        'approved_count': sum(1 for a in existing_applications.values() if a.status == CourseApplication.Status.APPROVED),
    }
    return render(request, 'core/student_course_registration.html', context)

@login_required
@user_passes_test(admin_required)
def admin_course_applications(request):
    sessions = AcademicSession.objects.all().order_by('-is_current', '-start_date')
    selected_session_id = request.GET.get('session')
    status_filter = request.GET.get('status', 'PENDING')
    search_query = request.GET.get('q', '').strip()

    if not selected_session_id:
        active_sess = AcademicSession.objects.filter(is_current=True).first()
        selected_session_id = str(active_sess.id) if active_sess else None

    applications = CourseApplication.objects.select_related(
        'student__user', 'student__department', 'course', 'academic_session', 'reviewed_by'
    )

    if selected_session_id:
        applications = applications.filter(academic_session_id=selected_session_id)

    if status_filter and status_filter != 'ALL':
        applications = applications.filter(status=status_filter)

    if search_query:
        applications = applications.filter(
            Q(student__roll_number__icontains=search_query) |
            Q(student__user__first_name__icontains=search_query) |
            Q(student__user__last_name__icontains=search_query) |
            Q(course__code__icontains=search_query) |
            Q(course__title__icontains=search_query)
        )

    # Handle Actions (Approve / Reject)
    if request.method == 'POST':
        app_id = request.POST.get('application_id')
        action = request.POST.get('action')
        remarks = request.POST.get('remarks', '').strip()
        
        application = get_object_or_404(CourseApplication, id=app_id)

        with transaction.atomic():
            if action == 'approve':
                application.status = CourseApplication.Status.APPROVED
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.admin_remarks = remarks
                application.save()

                Enrollment.objects.get_or_create(
                    student=application.student,
                    course=application.course,
                    academic_session=application.academic_session
                )

                Notification.objects.create(
                    recipient=application.student.user,
                    title="Course Application Approved",
                    message=f"Your application for {application.course.code}: {application.course.title} has been approved. You are now officially enrolled.",
                    notification_type=Notification.NotificationType.GENERAL
                )
                messages.success(request, f"Approved application for {application.student.roll_number} ({application.course.code}).")

            elif action == 'reject':
                application.status = CourseApplication.Status.REJECTED
                application.reviewed_by = request.user
                application.reviewed_at = timezone.now()
                application.admin_remarks = remarks
                application.save()

                Enrollment.objects.filter(
                    student=application.student,
                    course=application.course,
                    academic_session=application.academic_session
                ).delete()

                reason_text = f" Reason: {remarks}" if remarks else ""
                Notification.objects.create(
                    recipient=application.student.user,
                    title="Course Application Rejected",
                    message=f"Your application for {application.course.code}: {application.course.title} was declined.{reason_text}",
                    notification_type=Notification.NotificationType.GENERAL
                )
                messages.warning(request, f"Rejected application for {application.student.roll_number}.")

        return redirect(f"{request.path}?session={selected_session_id}&status={status_filter}")

    context = {
        'applications': applications,
        'sessions': sessions,
        'selected_session_id': selected_session_id,
        'status_filter': status_filter,
        'search_query': search_query,
        'pending_count': CourseApplication.objects.filter(status=CourseApplication.Status.PENDING).count(),
    }
    return render(request, 'core/admin_course_applications.html', context)

def generate_temp_password(length=5):
    """Generates a random 5-character alphanumeric temporary password."""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

@login_required
@user_passes_test(admin_required)
def manage_timetable(request):
    sessions = AcademicSession.objects.all().order_by('-is_current', '-start_date')
    selected_session_id = request.GET.get('session')

    if not selected_session_id:
        active_sess = AcademicSession.objects.filter(is_current=True).first()
        selected_session_id = str(active_sess.id) if active_sess else None

    schedules = Timetable.objects.select_related('course__teacher__user', 'course__department', 'academic_session')
    if selected_session_id:
        schedules = schedules.filter(academic_session_id=selected_session_id)

    if request.method == 'POST':
        form = TimetableForm(request.POST)
        if form.is_valid():
            timetable = form.save()
            if timetable.course.teacher:
                Notification.objects.create(
                    recipient=timetable.course.teacher.user,
                    title="New Class Schedule Assigned",
                    message=f"You have been assigned {timetable.course.code} on {timetable.get_day_display()} ({timetable.start_time.strftime('%H:%M')} - {timetable.end_time.strftime('%H:%M')}) in Room {timetable.room_number}.",
                    notification_type=Notification.NotificationType.GENERAL
                )
            messages.success(request, "Class timetable slot added successfully.")
            return redirect(f"{request.path}?session={selected_session_id}")
    else:
        form = TimetableForm()

    context = {
        'form': form,
        'schedules': schedules,
        'sessions': sessions,
        'selected_session_id': selected_session_id,
        'days': Timetable.DayOfWeek.choices,
    }
    return render(request, 'core/manage_timetable.html', context)

@login_required
def teacher_schedule_view(request):
    if not (request.user.role == User.Role.TEACHER or hasattr(request.user, 'teacher_profile')):
        messages.error(request, "Only faculty members can access this schedule.")
        return redirect('core:dashboard')

    teacher = request.user.teacher_profile
    schedules = Timetable.objects.filter(
        course__teacher=teacher
    ).select_related('course__department', 'academic_session').order_by('day', 'start_time')

    schedule_by_day = {}
    for day_code, day_label in Timetable.DayOfWeek.choices:
        schedule_by_day[day_label] = [s for s in schedules if s.day == day_code]

    return render(request, 'core/teacher_schedule.html', {'schedule_by_day': schedule_by_day})

@login_required
def student_timetable_view(request):
    if not (request.user.role == User.Role.STUDENT or hasattr(request.user, 'student_profile')):
        messages.error(request, "Only enrolled students can view this schedule.")
        return redirect('core:dashboard')

    student = request.user.student_profile
    active_session = AcademicSession.objects.filter(is_current=True).first()

    enrolled_course_ids = Enrollment.objects.filter(
        student=student,
        academic_session=active_session
    ).values_list('course_id', flat=True)

    schedules = Timetable.objects.filter(
        course_id__in=enrolled_course_ids,
        academic_session=active_session
    ).select_related('course__teacher__user', 'course__department').order_by('day', 'start_time')

    attendance_records = Attendance.objects.filter(student=student)
    
    latest_status_by_course = {}
    for att in attendance_records.order_by('date'):
        latest_status_by_course[att.course_id] = att.status

    timetable_grid = []
    for sched in schedules:
        st = latest_status_by_course.get(sched.course_id, 'NO_RECORD')
        
        if st in [Attendance.Status.PRESENT, Attendance.Status.LATE]:
            indicator = 'green'
        elif st == Attendance.Status.ABSENT:
            indicator = 'red'
        else:
            indicator = 'gray'

        timetable_grid.append({
            'schedule': sched,
            'status_color': indicator,
            'status_label': st,
        })

    schedule_by_day = {}
    for day_code, day_label in Timetable.DayOfWeek.choices:
        schedule_by_day[day_label] = [item for item in timetable_grid if item['schedule'].day == day_code]

    context = {
        'student': student,
        'active_session': active_session,
        'schedule_by_day': schedule_by_day,
    }
    return render(request, 'core/student_timetable.html', context)

@login_required
@user_passes_test(admin_required)
def schedule_extra_class(request):
    if request.method == 'POST':
        form = ExtraClassForm(request.POST)
        if form.is_valid():
            extra_slot = form.save(commit=False)
            extra_slot.is_extra_class = True
            
            day_name = extra_slot.specific_date.strftime('%A').upper()
            extra_slot.day = day_name
            extra_slot.save()

            if extra_slot.course.teacher:
                Notification.objects.create(
                    recipient=extra_slot.course.teacher.user,
                    title="Extra / Makeup Class Scheduled",
                    message=f"An extra class for {extra_slot.course.code} is scheduled on {extra_slot.specific_date} ({extra_slot.start_time.strftime('%H:%M')} - {extra_slot.end_time.strftime('%H:%M')}) in Room {extra_slot.room_number}.",
                    notification_type=Notification.NotificationType.GENERAL
                )

            enrolled_student_users = User.objects.filter(
                student_profile__enrollments__course=extra_slot.course,
                student_profile__enrollments__academic_session=extra_slot.academic_session
            )
            
            notifications = [
                Notification(
                    recipient=user,
                    title=f"Extra Class Notice: {extra_slot.course.code}",
                    message=f"A makeup class for {extra_slot.course.title} has been scheduled for {extra_slot.specific_date} at {extra_slot.start_time.strftime('%H:%M')} in Room {extra_slot.room_number}.",
                    notification_type=Notification.NotificationType.GENERAL
                )
                for user in enrolled_student_users
            ]
            Notification.objects.bulk_create(notifications)

            messages.success(request, f"Extra class for {extra_slot.course.code} scheduled on {extra_slot.specific_date}. Notifications sent!")
            return redirect('core:manage_timetable')
    else:
        form = ExtraClassForm()

    return render(request, 'core/schedule_extra_class.html', {'form': form})

@login_required
def notification_list(request):
    user = request.user
    query = Q(recipient=user)
    broadcast_role_filter = Q(target_audience=Notification.TargetAudience.ALL)

    if user.role == User.Role.TEACHER:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.TEACHERS)
        if hasattr(user, 'teacher_profile'):
            dept = user.teacher_profile.department
            broadcast_role_filter &= (Q(department=dept) | Q(department__isnull=True))

    elif user.role == User.Role.STUDENT:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STUDENTS)
        if hasattr(user, 'student_profile'):
            dept = user.student_profile.department
            broadcast_role_filter &= (Q(department=dept) | Q(department__isnull=True))

    elif user.role == User.Role.ADMIN or user.is_superuser:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STAFF)

    user_notifications = Notification.objects.filter(
        (query | (Q(recipient__isnull=True) & broadcast_role_filter)) & Q(is_hidden=False)
    ).distinct()

    user_notifications.filter(is_read=False).update(is_read=True)

    return render(request, 'core/notifications.html', {'notifications': user_notifications})


@login_required
@require_POST
def hide_notification(request, pk):
    notification = get_object_or_404(Notification, pk=pk)
    
    if notification.recipient and notification.recipient != request.user:
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    notification.is_hidden = True
    notification.is_read = True
    notification.save()

    user = request.user
    query = Q(recipient=user)
    broadcast_role_filter = Q(target_audience=Notification.TargetAudience.ALL)

    if user.role == User.Role.TEACHER:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.TEACHERS)
    elif user.role == User.Role.STUDENT:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STUDENTS)
    elif user.role == User.Role.ADMIN or user.is_superuser:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STAFF)

    remaining_unread = Notification.objects.filter(
        (query | (Q(recipient__isnull=True) & broadcast_role_filter)) & Q(is_hidden=False, is_read=False)
    ).distinct().count()

    return JsonResponse({'status': 'success', 'unread_count': remaining_unread})

@login_required
@require_POST
def hide_all_notifications(request):
    user = request.user
    query = Q(recipient=user)
    broadcast_role_filter = Q(target_audience=Notification.TargetAudience.ALL)

    if user.role == User.Role.TEACHER:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.TEACHERS)
    elif user.role == User.Role.STUDENT:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STUDENTS)
    elif user.role == User.Role.ADMIN or user.is_superuser:
        broadcast_role_filter |= Q(target_audience=Notification.TargetAudience.STAFF)

    Notification.objects.filter(
        (query | (Q(recipient__isnull=True) & broadcast_role_filter)) & Q(is_hidden=False)
    ).update(is_hidden=True, is_read=True)

    messages.success(request, "All notifications cleared.")
    return redirect('core:notification_list')


@login_required
@user_passes_test(admin_required)
def department_list(request):
    departments = Department.objects.annotate(
        student_count=Count('students', distinct=True),
        teacher_count=Count('teachers', distinct=True),
        course_count=Count('course', distinct=True)
    ).order_by('name')

    if request.method == 'POST':
        form = DepartmentForm(request.POST)
        if form.is_valid():
            dept = form.save()
            messages.success(request, f"Department '{dept.name} ({dept.code})' created successfully.")
            return redirect('core:department_list')
    else:
        form = DepartmentForm()

    context = {
        'departments': departments,
        'form': form,
    }
    return render(request, 'core/department_list.html', context)

@login_required
@user_passes_test(admin_required)
def department_update(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    if request.method == 'POST':
        form = DepartmentForm(request.POST, instance=dept)
        if form.is_valid():
            form.save()
            messages.success(request, f"Department '{dept.code}' updated successfully.")
            return redirect('core:department_list')
    else:
        form = DepartmentForm(instance=dept)
    return render(request, 'core/department_form.html', {'form': form, 'title': f'Edit Department: {dept.code}'})

@login_required
@user_passes_test(admin_required)
def department_delete(request, pk):
    dept = get_object_or_404(Department, pk=pk)
    
    if dept.students.exists() or dept.teachers.exists() or dept.course_set.exists():
        messages.error(request, f"Cannot delete '{dept.code}'! It has active students, teachers, or courses attached.")
        return redirect('core:department_list')

    if request.method == 'POST':
        dept.delete()
        messages.success(request, f"Department '{dept.name}' deleted successfully.")
        return redirect('core:department_list')
        
    return render(request, 'core/confirm_delete.html', {'object': dept, 'title': f'Delete Department {dept.code}'})