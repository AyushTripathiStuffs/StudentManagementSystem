from django import forms
from django.forms import inlineformset_factory
from .models import Department, AcademicSession, Teacher, Student, Course, Enrollment, Attendance
from accounts.models import User
from .models import Notification
from .models import Timetable
from datetime import datetime, timedelta
from datetime import time


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }


class AcademicSessionForm(forms.ModelForm):
    class Meta:
        model = AcademicSession
        fields = ['name', 'start_date', 'end_date', 'is_current']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. 2026-2027'}),
            'start_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'end_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_current': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['code', 'title', 'department', 'teacher', 'credits', 'total_planned_classes']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'credits': forms.NumberInput(attrs={'class': 'form-control'}),
            'total_planned_classes': forms.NumberInput(attrs={'class': 'form-control', 'min': 1}),
        }

class ExtraClassForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['course', 'academic_session', 'specific_date', 'start_time', 'end_time', 'room_number']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'academic_session': forms.Select(attrs={'class': 'form-select'}),
            'specific_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Lab 401'}),
        }

class StudentForm(forms.ModelForm):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Required when creating. Leave blank when updating to keep existing password."
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    academic_session = forms.ModelChoiceField(
        queryset=AcademicSession.objects.all(),
        empty_label="Select Academic Session",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Student
        fields = ['roll_number', 'department', 'academic_session', 'admission_date']
        widgets = {
            'roll_number': forms.TextInput(attrs={'class': 'form-control'}),
            'admission_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['password'].required = False
        else:
            self.fields['password'].required = True

class TeacherForm(forms.ModelForm):
    username = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    first_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Required when creating. Leave blank when updating to keep existing password."
    )

    department = forms.ModelChoiceField(
        queryset=Department.objects.all(),
        empty_label="Select Department",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = Teacher
        fields = ['employee_id', 'department', 'designation', 'joining_date']
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-control'}),
            'designation': forms.TextInput(attrs={'class': 'form-control'}),
            'joining_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['email'].initial = self.instance.user.email
            self.fields['password'].required = False
        else:
            self.fields['password'].required = True

            
class AttendanceFilterForm(forms.Form):
    course = forms.ModelChoiceField(queryset=Course.objects.all(), widget=forms.Select(attrs={'class': 'form-select'}))
    date = forms.DateField(widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}))

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        if user and hasattr(user, 'teacher_profile'):
            self.fields['course'].queryset = Course.objects.filter(teacher=user.teacher_profile)


class StudentAttendanceForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput())
    status = forms.ChoiceField(
        choices=Attendance.Status.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Optional remarks'})
    )

class BroadcastNotificationForm(forms.ModelForm):
    class Meta:
        model = Notification
        fields = ['title', 'message', 'notification_type', 'target_audience', 'department']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Notice title or heading'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4, 'placeholder': 'Write your circular/announcement details here...'}),
            'notification_type': forms.Select(attrs={'class': 'form-select'}),
            'target_audience': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].empty_label = "All Departments (Global)"
        self.fields['department'].required = False

class CourseEnrollmentForm(forms.ModelForm):
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select select2', 'size': '8'}),
        help_text="Hold Ctrl (Windows) or Command (Mac) to select multiple students."
    )

    class Meta:
        model = Enrollment
        fields = ['course', 'academic_session', 'students']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'academic_session': forms.Select(attrs={'class': 'form-select'}),
        }


class AdvancedAttendanceForm(forms.Form):
    student_id = forms.IntegerField(widget=forms.HiddenInput())
    status = forms.ChoiceField(
        choices=Attendance.Status.choices,
        widget=forms.Select(attrs={'class': 'form-select form-select-sm status-selector'})
    )
    remarks = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control form-control-sm', 'placeholder': 'Optional remarks'})
    )

class TimetableForm(forms.ModelForm):
    # Field to pick starting hour (8 AM to 6 PM)
    start_hour = forms.ChoiceField(
        choices=[(f"{h:02d}", f"{h:02d}:00") for h in range(8, 19)],
        widget=forms.Select(attrs={'class': 'form-select', 'id': 'id_start_hour', 'onchange': 'calculateTiming()'}),
        help_text="Select starting hour. Minutes will auto-set to :15."
    )

    class Meta:
        model = Timetable
        fields = ['course', 'academic_session', 'class_type', 'day', 'start_time', 'end_time', 'room_number']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-select'}),
            'academic_session': forms.Select(attrs={'class': 'form-select'}),
            'class_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_class_type', 'onchange': 'calculateTiming()'}),
            'day': forms.Select(attrs={'class': 'form-select'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time', 'id': 'id_start_time', 'readonly': 'readonly'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time', 'id': 'id_end_time', 'readonly': 'readonly'}),
            'room_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Lab 302'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_hour_str = cleaned_data.get('start_hour')
        class_type = cleaned_data.get('class_type')

        if start_hour_str:
            start_h = int(start_hour_str)
            
            cleaned_data['start_time'] = time(hour=start_h, minute=15)

            duration_hours = 2 if class_type == Timetable.ClassType.PRACTICAL else 1
            end_h = (start_h + duration_hours) % 24
            
            cleaned_data['end_time'] = time(hour=end_h, minute=10)

        return cleaned_data


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. Computer Science & Engineering'}),
            'code': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g. CSE'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code', '').strip().upper()
        if Department.objects.filter(code=code).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError("A department with this code already exists.")
        return code