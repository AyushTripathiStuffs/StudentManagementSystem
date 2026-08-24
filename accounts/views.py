from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .forms import LoginForm, RestrictedPasswordChangeForm, UserProfileForm
from core.models import Notification
from .models import User

def login_view(request):
    if request.user.is_authenticated:
        return redirect('core:dashboard')

    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f"Welcome back, {user.get_full_name() or user.username}!")
            return redirect('core:dashboard')
    else:
        form = LoginForm()

    return render(request, 'accounts/login.html', {'form': form})


def logout_view(request):
    logout(request)
    messages.info(request, "You have been logged out.")
    return redirect('accounts:login')


@login_required
def profile_view(request):
    if request.method == 'POST':
        old_email = request.user.email
        old_phone = getattr(request.user, 'phone_number', '')

        form = UserProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            user = form.save()

            # Check if email or phone changed
            changes = []
            if old_email != user.email:
                changes.append(f"Email changed to {user.email}")
            if old_phone != user.phone_number:
                changes.append(f"Phone number updated to {user.phone_number}")

            if changes:
                Notification.objects.create(
                    recipient=user,
                    title="Profile Details Updated",
                    message="Your contact info was updated: " + ", ".join(changes),
                    notification_type=Notification.NotificationType.SECURITY
                )

            messages.success(request, "Your profile and contact details have been successfully updated.")
            return redirect('accounts:profile')
    else:
        form = UserProfileForm(instance=request.user)

    return render(request, 'accounts/profile.html', {'form': form})

@login_required
def change_password_view(request):
    user = request.user
    
    # Maximum 2 changes allowed for non-admin users
    if user.role != User.Role.ADMIN and not user.is_superuser:
        if user.password_change_count >= 2:
            messages.error(request, "You have exhausted your maximum limit of 2 password changes. Contact the administrator for further resets.")
            return redirect('accounts:profile')

    if request.method == 'POST':
        form = RestrictedPasswordChangeForm(user=request.user, data=request.POST)
        if form.is_valid():
            form.save()
            update_session_auth_hash(request, form.user)  # Keep user logged in
            
            # Increment count
            user.password_change_count += 1
            user.save()

            # Create notification
            remaining_attempts = 2 - user.password_change_count
            Notification.objects.create(
                recipient=user,
                title="Security Alert: Password Changed",
                message=f"Your account password was successfully updated. Remaining allowed changes: {max(0, remaining_attempts)}.",
                notification_type=Notification.NotificationType.SECURITY
            )

            messages.success(request, f"Password successfully changed! ({user.password_change_count}/2 allowed changes used).")
            return redirect('accounts:profile')
    else:
        form = RestrictedPasswordChangeForm(user=request.user)

    remaining_changes = max(0, 2 - user.password_change_count) if (user.role != User.Role.ADMIN and not user.is_superuser) else "Unlimited"

    return render(request, 'accounts/change_password.html', {
        'form': form,
        'remaining_changes': remaining_changes,
        'used_changes': user.password_change_count
    })