from django.urls import path
from . import views

app_name = 'core'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    
    path('students/', views.student_list, name='student_list'),
    path('students/create/', views.student_create, name='student_create'),
    path('students/<int:pk>/update/', views.student_update, name='student_update'),
    path('students/<int:pk>/delete/', views.student_delete, name='student_delete'),
    
    path('teachers/', views.teacher_list, name='teacher_list'),
    path('teachers/create/', views.teacher_create, name='teacher_create'),
    path('teachers/<int:pk>/update/', views.teacher_update, name='teacher_update'),
    path('teachers/<int:pk>/delete/', views.teacher_delete, name='teacher_delete'),
    
    path('courses/', views.course_list, name='course_list'),
    path('courses/create/', views.course_create, name='course_create'),
    path('courses/<int:pk>/update/', views.course_update, name='course_update'),
    path('courses/<int:pk>/delete/', views.course_delete, name='course_delete'),
    
    path('attendance/mark/', views.mark_attendance, name='mark_attendance'),
    path('attendance/report/', views.attendance_report, name='attendance_report'),

    path('notifications/', views.notification_list, name='notification_list'),
    path('notifications/broadcast/', views.broadcast_notification, name='broadcast_notification'),

    path('my-courses/', views.teacher_courses_dashboard, name='teacher_courses'),
    path('course/<int:course_id>/roster/', views.course_roster_view, name='course_roster'),
    path('course/<int:course_id>/attendance/take/', views.take_course_attendance, name='take_attendance'),

    path('my-enrolled-courses/', views.student_courses_view, name='student_courses'),
    path('my-enrolled-courses/<int:course_id>/detail/', views.student_course_attendance_detail, name='student_course_detail'),

    path('enrollments/manage/', views.manage_enrollments, name='manage_enrollments'),
    path('courses/applications/', views.admin_course_applications, name='admin_course_applications'),
    path('courses/apply/', views.student_course_registration, name='student_course_registration'),
]