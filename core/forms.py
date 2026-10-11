from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Transaction, AnnouncementComment, CustomUser, Announcement, FinancialGoal, Student, ParentStudentRel

class SignUpForm(UserCreationForm):
    represented_student = forms.CharField(
        label="Nombre Completo del Representado (Estudiante)",
        help_text="Escribe el nombre y apellido de tu hijo/a representado/a."
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})
            if hasattr(field, 'error_messages'):
                for key in field.error_messages:
                    if key == 'required':
                        field.error_messages[key] = f"El campo {field.label} es obligatorio."
                    elif key == 'invalid':
                        field.error_messages[key] = f"El valor introducido en {field.label} no es válido."
        
        if 'password1' in self.fields:
            self.fields['password1'].help_text = "La contraseña debe tener al menos 8 caracteres."
            self.fields['password1'].error_messages['password_too_short'] = "La contraseña es demasiado corta."
            self.fields['password1'].error_messages['password_common'] = "Esta contraseña es muy común."

    class Meta:
        model = CustomUser
        fields = ['email', 'first_name', 'last_name']
        error_messages = {
            'email': {
                'unique': "Ya existe un usuario registrado con este correo electrónico.",
                'required': "El correo electrónico es obligatorio.",
            },
        }

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            student_full_name = self.cleaned_data.get('represented_student', '').strip()
            if student_full_name:
                parts = student_full_name.split(' ', 1)
                f_name = parts[0]
                l_name = parts[1] if len(parts) > 1 else ""
                
                student, created = Student.objects.get_or_create(
                    first_name=f_name,
                    last_name=l_name,
                    defaults={'section': '6to A'}
                )
                ParentStudentRel.objects.get_or_create(parent=user, student=student)
        return user

class TransactionForm(forms.ModelForm):
    # Campo calculado de solo lectura
    monto_divisas = forms.DecimalField(
        required=False, 
        disabled=True, 
        label="Monto en Divisas ($)",
        widget=forms.NumberInput(attrs={'class': 'input input-bordered w-full', 'readonly': 'readonly'})
    )

    def __init__(self, *args, **kwargs):
        is_admin_view = kwargs.pop('is_admin_view', False)
        super().__init__(*args, **kwargs)
        
        for name, field in self.fields.items():
            if name in ['parent', 'transaction_type', 'method', 'goal']:
                field.widget.attrs.update({'class': 'select select-bordered w-full'})
            elif name != 'monto_divisas':
                field.widget.attrs.update({'class': 'input input-bordered w-full'})
        
        if self.instance and self.instance.pk:
            self.fields['monto_divisas'].initial = self.instance.amount_divisa

        # Configuración del selector de padres
        if 'parent' in self.fields:
            self.fields['parent'].queryset = CustomUser.objects.filter(role='PARENT')
            self.fields['parent'].label_from_instance = lambda obj: f"{obj.first_name} {obj.last_name}"
            
            # Si no es vista de admin, ocultamos los campos
            if not is_admin_view:
                self.fields['parent'].widget = forms.HiddenInput()
                self.fields['parent'].required = False
                self.fields['transaction_type'].widget = forms.HiddenInput()
                self.fields['transaction_type'].required = False
            
        # Filtrar solo metas no completadas
        self.fields['goal'].queryset = FinancialGoal.objects.filter(is_completed=False)
        self.fields['goal'].label_from_instance = lambda obj: obj.title
    
    class Meta:
        model = Transaction
        fields = ['parent', 'transaction_type', 'amount', 'tasa_bcv', 'monto_divisas', 'method', 'reference', 'description', 'receipt_file', 'goal']

class CommentForm(forms.ModelForm):
    class Meta:
        model = AnnouncementComment
        fields = ['comment_text']

class UserUpdateForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})

    class Meta:
        model = CustomUser
        fields = ['first_name', 'last_name', 'email', 'role']

class AnnouncementForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})

    class Meta:
        model = Announcement
        fields = ['title', 'content', 'category', 'image']

class FinancialGoalForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})

    class Meta:
        model = FinancialGoal
        fields = ['title', 'target_amount', 'max_per_parent']
