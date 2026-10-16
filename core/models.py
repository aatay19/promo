from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.validators import FileExtensionValidator
from django.utils.text import slugify
from django.db.models import Sum
from decimal import Decimal

# --- UserManager ---
class CustomUserManager(BaseUserManager):
    def create_user(self, username, password=None, **extra_fields):
        if not username:
            raise ValueError('El nombre de usuario es obligatorio')
        user = self.model(username=username, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', 'ADMIN')
        return self.create_user(username, password, **extra_fields)

# --- Usuarios ---
class CustomUser(AbstractUser):
    ROLE_CHOICES = [('PARENT', 'Padre'), ('TREASURER', 'Tesorero'), ('ADMIN', 'Admin')]
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='PARENT')
    
    USERNAME_FIELD = 'username'
    REQUIRED_FIELDS = []
    
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
    CATEGORY_CHOICES = [('GENERAL', 'General'), ('REUNION', 'Reunión'), ('PAGO', 'Pago'), ('TESORERIA', 'Tesorería')]
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
            base_slug = slugify(self.title)
            slug = base_slug
            counter = 1
            while Announcement.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1
            self.slug = slug
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
    is_completed = models.BooleanField(default=False)
    
    @property
    def current_amount(self):
        return self.transactions.filter(transaction_type='INCOME').aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0.00')

    @property
    def progress_percentage(self):
        return (self.current_amount / self.target_amount) * 100 if self.target_amount > 0 else 0

class Transaction(models.Model):
    TYPE_CHOICES = [('INCOME', 'Ingreso'), ('EXPENSE', 'Gasto')]
    METHOD_CHOICES = [('DIVISA', 'Divisa efectivo $'), ('TRANSFER', 'Transferencia - BS'), ('PAGOMOVIL', 'Pago Movil - BS'), ('ZELLER', 'Zeller'), ('USDT', 'USDT')]
    
    transaction_type = models.CharField(max_length=10, choices=TYPE_CHOICES)
    parent = models.ForeignKey(CustomUser, on_delete=models.CASCADE, default=1, verbose_name="Padre/Representante")
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True, verbose_name="Monto (BS o $)")
    tasa_bcv = models.DecimalField(max_digits=10, decimal_places=2, default=1, null=True, blank=True, verbose_name="Tasa BCV")
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
    is_confirmed = models.BooleanField(default=False, verbose_name="Confirmado")
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        amount = self.amount or Decimal('0')
        tasa = self.tasa_bcv or Decimal('1')
        self.amount_divisa = amount / tasa if tasa != 0 else Decimal('0')
        super().save(*args, **kwargs)
