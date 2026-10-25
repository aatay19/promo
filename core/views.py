from django.contrib import messages
from django import forms
from django.db.models import Sum
from decimal import Decimal
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import View, ListView, CreateView, TemplateView, DeleteView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse, JsonResponse
from django.core.paginator import Paginator
from .models import Announcement, AnnouncementVote, AnnouncementComment, Student, ParentStudentRel, CustomUser, Transaction, FinancialGoal
from .forms import SignUpForm, AnnouncementForm, UserUpdateForm, TransactionForm, FinancialGoalForm, ParentPaymentForm, ExpenseForm

class RoleRequiredMixin(UserPassesTestMixin):
    allowed_roles = []
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.role in self.allowed_roles

class UserListView(RoleRequiredMixin, ListView):
    model = CustomUser
    template_name = 'registration/user_list.html'
    context_object_name = 'usuarios'
    allowed_roles = ['ADMIN']

class UserDeleteView(RoleRequiredMixin, DeleteView):
    model = CustomUser
    template_name = 'registration/user_confirm_delete.html'
    success_url = reverse_lazy('user_list')
    allowed_roles = ['ADMIN']

class UserUpdateView(RoleRequiredMixin, UpdateView):
    model = CustomUser
    form_class = UserUpdateForm
    template_name = 'registration/user_form.html'
    success_url = reverse_lazy('user_list')
    allowed_roles = ['ADMIN']

class NoticiasView(LoginRequiredMixin, ListView):
    model = Announcement
    template_name = 'announcements/dashboard.html'
    context_object_name = 'anuncios'

    def get_queryset(self):
        # Limitamos a las 5 más recientes para el dashboard
        return Announcement.objects.all().prefetch_related('votes').order_by('-created_at')[:5]

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for anuncio in context['anuncios']:
            anuncio.user_has_voted = anuncio.user_has_voted(self.request.user)
        context['todas_las_noticias'] = Announcement.objects.all().order_by('-created_at')
        context['goals'] = FinancialGoal.objects.filter(is_completed=False)
        
        income = Transaction.objects.filter(transaction_type='INCOME', is_confirmed=True).aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0')
        expense = Transaction.objects.filter(transaction_type='EXPENSE', is_confirmed=True).aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0')
        context['income'] = income
        context['expense'] = expense
        context['balance'] = income - expense
        
        # Obtener todas las metas activas con su estado de abono por padre
        active_goals = FinancialGoal.objects.filter(is_completed=False)
        all_parents = CustomUser.objects.filter(role='PARENT').order_by('first_name')

        goals_with_parents = []
        for goal in active_goals:
            parents_with_status = []
            for parent in all_parents:
                status = 'none'
                total_paid = Decimal('0')
                confirmed = Transaction.objects.filter(
                    goal=goal, parent=parent, transaction_type='INCOME', is_confirmed=True
                ).first()
                pending = Transaction.objects.filter(
                    goal=goal, parent=parent, transaction_type='INCOME', is_confirmed=False
                ).first()
                if confirmed:
                    status = 'confirmed'
                    total_paid = confirmed.amount_divisa
                elif pending:
                    status = 'pending'
                    total_paid = pending.amount_divisa
                parents_with_status.append({
                    'id': parent.id,
                    'name': f"{parent.first_name} {parent.last_name}",
                    'status': status,
                    'total_paid': total_paid,
                })
            goals_with_parents.append({
                'goal': goal,
                'parents_status': parents_with_status,
            })
        context['goals_with_parents'] = goals_with_parents
        # Mantener active_goal para compatibilidad (primera meta activa)
        context['active_goal'] = active_goals.first()
        
        # Pagos pendientes para admin/tesorero
        if self.request.user.role in ['ADMIN', 'TREASURER']:
            context['pending_count'] = Transaction.objects.filter(is_confirmed=False, transaction_type='INCOME').count()
        else:
            context['pending_count'] = 0
        
        return context
class TreasuryView(LoginRequiredMixin, View):
    template_name = 'treasury/treasury.html'

    def get(self, request, *args, **kwargs):
        income = Transaction.objects.filter(transaction_type='INCOME', is_confirmed=True).aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0')
        expense = Transaction.objects.filter(transaction_type='EXPENSE', is_confirmed=True).aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0')

        total_parents = CustomUser.objects.filter(role='PARENT').count()

        context = {
            'income': income,
            'expense': expense,
            'balance': income - expense,
            'total_parents': total_parents,
        }

        # Solo mostrar transacciones detalladas y metas si es Admin/Tesorero
        if request.user.role in ['ADMIN', 'TREASURER']:
            search_query = request.GET.get('q', '').strip()
            all_transactions = Transaction.objects.filter(is_confirmed=True).order_by('-created_at')

            if search_query:
                from django.db.models import Q
                all_transactions = all_transactions.filter(
                    Q(parent__first_name__icontains=search_query) |
                    Q(parent__last_name__icontains=search_query) |
                    Q(parent__parentstudentrel__student__first_name__icontains=search_query) |
                    Q(parent__parentstudentrel__student__last_name__icontains=search_query)
                ).distinct()

            paginator = Paginator(all_transactions, 15)
            page_number = request.GET.get('page')
            page_obj = paginator.get_page(page_number)

            context['transactions'] = page_obj
            context['page_obj'] = page_obj
            context['is_paginated'] = paginator.num_pages > 1
            context['goals'] = FinancialGoal.objects.all()
            context['search_query'] = search_query
        else:
            context['transactions'] = None
            context['goals'] = None

        return render(request, self.template_name, context)


class FinancialGoalCreateView(RoleRequiredMixin, CreateView):
    model = FinancialGoal
    form_class = FinancialGoalForm
    template_name = 'treasury/create_goal.html'
    success_url = reverse_lazy('treasury')
    allowed_roles = ['TREASURER', 'ADMIN']

class TransactionCreateView(RoleRequiredMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'treasury/create_transaction.html'
    success_url = reverse_lazy('treasury')
    allowed_roles = ['TREASURER', 'ADMIN']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['is_admin_view'] = True
        return kwargs

    def get_initial(self):
        initial = super().get_initial()
        from_payment = self.request.GET.get('from_payment')
        if from_payment:
            try:
                payment = Transaction.objects.get(pk=from_payment)
                initial['parent'] = payment.parent
                initial['goal'] = payment.goal
            except Transaction.DoesNotExist:
                pass
        return initial

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        messages.success(self.request, "Transacción registrada exitosamente.")
        return super().form_valid(form)

class ParentPendingReceiptView(RoleRequiredMixin, View):
    allowed_roles = ['TREASURER', 'ADMIN']

    def get(self, request, pk):
        transaction = Transaction.objects.filter(
            parent_id=pk, transaction_type='INCOME', is_confirmed=False
        ).exclude(receipt_file='').order_by('-created_at').first()
        if not transaction:
            return JsonResponse({'found': False})
        return JsonResponse({
            'found': True,
            'id': transaction.pk,
            'url': transaction.receipt_file.url,
            'amount': str(transaction.amount or ''),
            'goal': transaction.goal.title if transaction.goal else 'Sin meta',
            'date': transaction.created_at.strftime('%d/%m/%Y %H:%M'),
            'detail_url': reverse_lazy('transaction_detail', kwargs={'pk': transaction.pk}),
        })

class ExpenseCreateView(RoleRequiredMixin, CreateView):
    model = Transaction
    form_class = ExpenseForm
    template_name = 'treasury/create_expense.html'
    success_url = reverse_lazy('treasury')
    allowed_roles = ['TREASURER', 'ADMIN']

    def form_valid(self, form):
        form.instance.transaction_type = 'EXPENSE'
        form.instance.recorded_by = self.request.user
        form.instance.goal = None
        form.instance.is_confirmed = True
        messages.success(self.request, "Gasto registrado exitosamente.")
        return super().form_valid(form)

class FinancialGoalDeleteView(RoleRequiredMixin, DeleteView):
    model = FinancialGoal
    template_name = 'treasury/goal_confirm_delete.html'
    success_url = reverse_lazy('treasury')
    allowed_roles = ['TREASURER', 'ADMIN']

class TransactionDetailView(LoginRequiredMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'treasury/transaction_detail.html'

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['is_admin_view'] = True
        return kwargs

    def get_success_url(self):
        return reverse_lazy('treasury')

    def form_valid(self, form):
        if not self.object.receipt_file:
            form.add_error('receipt_file', 'El padre no ha subido el comprobante.')
            return self.form_invalid(form)
        self.object.is_confirmed = True
        messages.success(self.request, "Pago confirmado exitosamente.")
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction'] = self.object
        return context

class TransactionDeleteView(RoleRequiredMixin, DeleteView):
    model = Transaction
    template_name = 'treasury/transaction_confirm_delete.html'
    success_url = reverse_lazy('treasury')
    allowed_roles = ['ADMIN', 'TREASURER']

class TransactionUpdateView(RoleRequiredMixin, UpdateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'treasury/create_transaction.html'
    success_url = reverse_lazy('treasury')
    allowed_roles = ['ADMIN', 'TREASURER']

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['is_admin_view'] = True
        return kwargs

class AnnouncementCreateView(RoleRequiredMixin, CreateView):
    model = Announcement
    form_class = AnnouncementForm
    template_name = 'announcements/create_announcement.html'
    success_url = reverse_lazy('noticias')
    allowed_roles = ['ADMIN', 'TREASURER']

    def form_valid(self, form):
        form.instance.created_by = self.request.user
        return super().form_valid(form)

class SignUpView(CreateView):
    form_class = SignUpForm
    template_name = 'registration/signup.html'
    success_url = reverse_lazy('login')

    def form_valid(self, form):
        messages.success(self.request, "Usuario creado exitosamente. Ahora puede iniciar sesión.")
        return super().form_valid(form)

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})
        if 'username' in form.fields:
            form.fields['username'].widget.attrs.update({'placeholder': 'Ej: juanito2024'})
        if 'password' in form.fields:
            form.fields['password'].widget.attrs.update({'placeholder': 'Su contraseña'})
        return form

    def form_valid(self, form):
        messages.success(self.request, "Sesión iniciada exitosamente.")
        return super().form_valid(form)

    def form_invalid(self, form):
        messages.error(self.request, "Revise usuario y contraseña.")
        return super().form_invalid(form)

class AnnouncementVoteView(LoginRequiredMixin, View):
    def post(self, request, pk):
        announcement = get_object_or_404(Announcement, pk=pk)
        if announcement.user_has_voted(request.user):
            return HttpResponse("Ya has votado anteriormente.", status=403)
        vote_type = request.POST.get('vote_type')
        AnnouncementVote.objects.create(announcement=announcement, user=request.user, vote_type=vote_type)
        announcement.user_has_voted = True
        return render(request, 'partials/vote_section.html', {'anuncio': announcement})

class AnnouncementCommentView(LoginRequiredMixin, CreateView):
    model = AnnouncementComment
    fields = ['comment_text']
    template_name = 'partials/comment_item.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        form.instance.announcement_id = self.kwargs['pk']
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('noticias')

class ParentProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/parent_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = Transaction.objects.filter(parent=self.request.user).order_by('-created_at')
        context['goals'] = FinancialGoal.objects.filter(is_completed=True)
        return context

class ParentPaymentView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = ParentPaymentForm
    template_name = 'treasury/parent_payment.html'
    success_url = reverse_lazy('noticias')

    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        form.fields['goal'].queryset = FinancialGoal.objects.filter(is_completed=False)
        return form

    def form_invalid(self, form):
        messages.error(self.request, f"Error al guardar: {form.errors}")
        return super().form_invalid(form)

    def form_valid(self, form):
        form.instance.parent = self.request.user
        form.instance.transaction_type = 'INCOME'
        form.instance.recorded_by = self.request.user
        form.instance.is_confirmed = False
        messages.success(self.request, "Abono enviado. Pendiente de confirmación por tesorería.")
        return super().form_valid(form)

class PendingPaymentsView(RoleRequiredMixin, ListView):
    model = Transaction
    template_name = 'treasury/pending_payments.html'
    context_object_name = 'pending_payments'
    allowed_roles = ['TREASURER', 'ADMIN']

    def get_queryset(self):
        return Transaction.objects.filter(is_confirmed=False, transaction_type='INCOME').order_by('-created_at')

class ConfirmPaymentView(RoleRequiredMixin, View):
    allowed_roles = ['TREASURER', 'ADMIN']

    def post(self, request, pk):
        return redirect('transaction_detail', pk=pk)
