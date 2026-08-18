from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db import transaction
from django.db.models import Count, Q
from django.forms import formset_factory
from .models import Department, AcademicSession, Teacher, Student, Course, Enrollment, Attendance
from .forms import (
    CourseEnrollmentForm, DepartmentForm, AcademicSessionForm, CourseForm, 
    StudentForm, TeacherForm, AttendanceFilterForm, StudentAttendanceForm, BroadcastNotificationForm
)
from accounts.models import User
from .models import Notification,CourseApplication
from django.utils import timezone
import secrets
import string
from django.core.mail import send_mail
from django.conf import settings


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
                temp_password = generate_temp_password(5)
                username = form.cleaned_data['username']
                email = form.cleaned_data['email']
                first_name = form.cleaned_data['first_name']

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=form.cleaned_data['last_name'],
                    password=temp_password,
                    role=User.Role.STUDENT
                )

                student = form.save(commit=False)
                student.user = user
                student.save()

                subject = "Your iSchool Student Portal Account Details"
                message = (
                    f"Hello {first_name},\n\n"
                    f"Your student account has been created by the administrator.\n\n"
                    f"Username: {username}\n"
                    f"Temporary Password: {temp_password}\n\n"
                    f"Please log in and update your password from your profile settings. "
                    f"Note: Password changes are strictly limited to 2 times for account security."
                )
                try:
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
                except Exception:
                    pass

                Notification.objects.create(
                    recipient=user,
                    title="Account Created & Temporary Credentials",
                    message=f"Welcome {first_name}! Your roll number is {student.roll_number}. You may change your temporary password up to 2 times.",
                    notification_type=Notification.NotificationType.VERIFICATION
                )

            messages.success(request, f"Student account created. Temporary 5-char password ({temp_password}) generated and dispatched to {email}.")
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
                user.save()
                form.save()
            messages.success(request, "Student details updated.")
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
                temp_password = generate_temp_password(5)
                username = form.cleaned_data['username']
                email = form.cleaned_data['email']
                first_name = form.cleaned_data['first_name']

                user = User.objects.create_user(
                    username=username,
                    email=email,
                    first_name=first_name,
                    last_name=form.cleaned_data['last_name'],
                    password=temp_password,
                    role=User.Role.TEACHER
                )

                teacher = form.save(commit=False)
                teacher.user = user
                teacher.save()

                subject = "Your iSchool Faculty Account Details"
                message = (
                    f"Hello {first_name},\n\n"
                    f"Your faculty account has been created by the administrator.\n\n"
                    f"Username: {username}\n"
                    f"Temporary Password: {temp_password}\n\n"
                    f"Please log in and update your password from your profile settings. "
                    f"Note: Password changes are limited to 2 times for security."
                )
                try:
                    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email], fail_silently=True)
                except Exception:
                    pass

            messages.success(request, f"Faculty account created. Temporary password ({temp_password}) sent to {email}.")
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
                user.save()
                form.save()
            messages.success(request, "Faculty details updated.")
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
            messages.success(request, "Course updated successfully.")
            return redirect('core:course_list')
    else:
        form = CourseForm(instance=course)
    return render(request, 'core/course_form.html', {'form': form, 'title': 'Edit Course'})


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
    selected_date = request.GET.get('date')

    course = None
    formset = None
    students_list = []

    if course_id and selected_date:
        course = get_object_or_404(Course, id=course_id)
        enrollments = Enrollment.objects.filter(course=course).select_related('student__user')
        existing_records = {att.student_id: att for att in Attendance.objects.filter(course=course, date=selected_date)}

        if request.method == 'POST':
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
                messages.success(request, f"Attendance saved for {course.code} on {selected_date}.")
                return redirect(f"{request.path}?course={course_id}&date={selected_date}")
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
        'selected_date': selected_date,
        'students_list': students_list,
        'form_and_students': zip(formset.forms, students_list) if formset else [],
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
    selected_date = request.GET.get('date', timezone.now().strftime('%Y-%m-%d'))
    
    enrollments = Enrollment.objects.filter(course=course).select_related('student__user').order_by('student__roll_number')
    existing_attendance = {
        att.student_id: att 
        for att in Attendance.objects.filter(course=course, date=selected_date)
    }

    if request.method == 'POST':
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
        messages.success(request, f"Attendance saved for {course.code} on {selected_date}.")
        return redirect(f"{request.path}?date={selected_date}")
    
    student_records = []
    for enrollment in enrollments:
        student = enrollment.student
        existing = existing_attendance.get(student.id)
        
        # Calculate current cumulative percentage
        total_course_classes = Attendance.objects.filter(course=course).values('date').distinct().count()
        attended = Attendance.objects.filter(course=course, student=student, status__in=[Attendance.Status.PRESENT, Attendance.Status.LATE]).count()
        pct = round((attended / total_course_classes * 100), 1) if total_course_classes > 0 else 100.0

        student_records.append({
            'student': student,
            'status': existing.status if existing else Attendance.Status.PRESENT,
            'remarks': existing.remarks if existing else '',
            'current_pct': pct
        })

    context = {
        'course': course,
        'selected_date': selected_date,
        'student_records': student_records,
        'status_choices': Attendance.Status.choices,
        'is_already_marked': bool(existing_attendance),
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

                # Send rejection notification with remarks
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