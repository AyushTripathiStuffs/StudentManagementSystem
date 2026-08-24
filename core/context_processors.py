from .models import Notification
from django.db.models import Q
from accounts.models import User

def notification_context(request):
    if request.user.is_authenticated:
        user = request.user
        query = Q(recipient=user)

        broadcast_filter = Q(target_audience=Notification.TargetAudience.ALL)

        if user.role == User.Role.TEACHER:
            broadcast_filter |= Q(target_audience=Notification.TargetAudience.TEACHERS)
            if hasattr(user, 'teacher_profile'):
                dept = user.teacher_profile.department
                broadcast_filter &= (Q(department=dept) | Q(department__isnull=True))

        elif user.role == User.Role.STUDENT:
            broadcast_filter |= Q(target_audience=Notification.TargetAudience.STUDENTS)
            if hasattr(user, 'student_profile'):
                dept = user.student_profile.department
                broadcast_filter &= (Q(department=dept) | Q(department__isnull=True))

        elif user.role == User.Role.ADMIN or user.is_superuser:
            broadcast_filter |= Q(target_audience=Notification.TargetAudience.STAFF)

        user_notifications = Notification.objects.filter(
            (query | (Q(recipient__isnull=True) & broadcast_filter)) & Q(is_hidden=False)
        ).distinct()

        unread_count = user_notifications.filter(is_read=False).count()
        return {
            'unread_notifications_count': unread_count,
            'latest_notifications': user_notifications[:5]
        }
    return {'unread_notifications_count': 0, 'latest_notifications': []}