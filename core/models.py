from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
from django.db.models import Sum
from decimal import Decimal

# --- UserManager ---
class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('El email es obligatorio')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

# --- Usuarios ---
class CustomUser(AbstractUser):
    username = None
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    ROLE_CHOICES = [('PARENT', 'Padre'), ('TREASURER', 'Tesorero'), ('ADMIN', 'Admin')]
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='PARENT')
    
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']
    
    objects = CustomUserManager()

class Student(models.Model):
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    section = models.CharField(max_length=10)
    is_active = models.BooleanField(default=True)

class ParentStudentRel(models.Model):
    parent = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    student = models.ForeignKey(Student, on_delete=models.CASCADE)

# --- Anuncios ---
class Announcement(models.Model):
    CATEGORY_CHOICES = [('GENERAL', 'General'), ('REUNION', 'Reunión'), ('PAGO', 'Pago')]
    title = models.CharField(max_length=200, verbose_name="Título")
    slug = models.SlugField(unique=True, blank=True)
    content = models.TextField(verbose_name="Contenido")
    category = models.CharField(max_length=10, choices=CATEGORY_CHOICES, verbose_name="Categoría")
    image = models.FileField(
        upload_to='announcements/',
        blank=True,
        null=True,
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'pdf'])]
    )
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(CustomUser, on_delete=models.CASCADE)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)
        super().save(*args, **kwargs)

    @property
    def agree_count(self):
        return self.votes.filter(vote_type='AGREE').count()

    @property
    def disagree_count(self):
        return self.votes.filter(vote_type='DISAGREE').count()
    
    def user_has_voted(self, user):
        return self.votes.filter(user=user).exists()

class AnnouncementVote(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='votes')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    vote_type = models.CharField(max_length=10, choices=[('AGREE', 'Acuerdo'), ('DISAGREE', 'Desacuerdo')])
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['announcement', 'user'], name='unique_vote')]

class AnnouncementComment(models.Model):
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE, related_name='comments')
    user = models.ForeignKey(CustomUser, on_delete=models.CASCADE)
    comment_text = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

# --- Tesorería ---
class FinancialGoal(models.Model):
    title = models.CharField(max_length=200, verbose_name="Título de la Meta")
    target_amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto Meta (Divisa)")
    max_per_parent = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name="Máximo por Padre (Divisa)")
    is_completed = models.BooleanField(default=False)
    
    @property
    def current_amount(self):
        return self.transactions.filter(transaction_type='INCOME').aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0.00')

    @property
    def progress_percentage(self):
        return (self.current_amount / self.target_amount) * 100 if self.target_amount > 0 else 0

class Transaction(models.Model):
    TYPE_CHOICES = [('INCOME', 'Ingreso'), ('EXPENSE', 'Gasto')]
    METHOD_CHOICES = [('DIVISA', 'Divisa'), ('TRANSFER', 'Transferencia'), ('PAGOMOVIL', 'Pago Móvil'), ('USDT', 'USDT')]
    
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    parent = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=1, verbose_name="Padre/Representante")
    amount = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Monto (BS o $)")
    tasa_bcv = models.DecimalField(max_digits=10, decimal_places=2, default=1, verbose_name="Tasa BCV")
    amount_divisa = models.DecimalField(max_digits=10, decimal_places=2, default=0, editable=False, verbose_name="Monto (Divisa)")
    method = models.CharField(max_length=20, choices=METHOD_CHOICES, default='DIVISA', verbose_name="Método")
    reference = models.CharField(max_length=100, blank=True, null=True, verbose_name="Referencia")
    description = models.TextField(blank=True)
    receipt_file = models.FileField(
        upload_to='receipts/',
        validators=[FileExtensionValidator(allowed_extensions=['png', 'jpg', 'jpeg', 'pdf'])]
    )
    goal = models.ForeignKey(FinancialGoal, on_delete=models.SET_NULL, null=True, related_name='transactions')
    recorded_by = models.ForeignKey(CustomUser, on_delete=models.PROTECT, related_name='recorded_transactions')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        self.amount_divisa = self.amount / self.tasa_bcv if self.tasa_bcv else 0
        super().save(*args, **kwargs)
