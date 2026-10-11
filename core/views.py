from django.contrib import messages
from django import forms
from django.db.models import Sum
from decimal import Decimal
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.contrib.auth.views import LoginView
from django.views.generic import View, ListView, CreateView, TemplateView, DeleteView, UpdateView
from django.urls import reverse_lazy
from django.shortcuts import render, get_object_or_404, redirect
from django.http import HttpResponse
from .models import Announcement, AnnouncementVote, AnnouncementComment, Student, ParentStudentRel, CustomUser, Transaction, FinancialGoal
from .forms import SignUpForm, AnnouncementForm, UserUpdateForm, TransactionForm, FinancialGoalForm

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
        return Announcement.objects.all().prefetch_related('votes').order_by('-created_at')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        for anuncio in context['anuncios']:
            anuncio.user_has_voted = anuncio.user_has_voted(self.request.user)
        context['goals'] = FinancialGoal.objects.all()
        return context
class TreasuryView(LoginRequiredMixin, TemplateView):
    template_name = 'treasury/treasury.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        income = Transaction.objects.filter(transaction_type='INCOME').aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0')
        expense = Transaction.objects.filter(transaction_type='EXPENSE').aggregate(Sum('amount_divisa'))['amount_divisa__sum'] or Decimal('0')
        
        context['income'] = income
        context['expense'] = expense
        context['balance'] = income - expense
        
        # Solo mostrar transacciones detalladas y metas si es Admin/Tesorero
        if self.request.user.role in ['ADMIN', 'TREASURER']:
            context['transactions'] = Transaction.objects.all().order_by('-created_at')[:10]
            context['goals'] = FinancialGoal.objects.all()
        else:
            context['transactions'] = None
            context['goals'] = None
            
        return context

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

    def form_valid(self, form):
        form.instance.recorded_by = self.request.user
        messages.success(self.request, "Transacción registrada exitosamente.")
        return super().form_valid(form)

class TransactionDetailView(LoginRequiredMixin, TemplateView):
    template_name = 'treasury/transaction_detail.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transaction'] = get_object_or_404(Transaction, pk=self.kwargs['pk'])
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

class CustomLoginView(LoginView):
    template_name = 'registration/login.html'
    def get_form(self, form_class=None):
        form = super().get_form(form_class)
        for field in form.fields.values():
            field.widget.attrs.update({'class': 'input input-bordered w-full'})
        return form

class HomeView(TemplateView):
    template_name = 'home.html'

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

class ParentProfileView(LoginRequiredMixin, TemplateView):
    template_name = 'registration/parent_profile.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['transactions'] = Transaction.objects.filter(parent=self.request.user).order_by('-created_at')
        context['goals'] = FinancialGoal.objects.filter(is_completed=True)
        return context

class ParentPaymentView(LoginRequiredMixin, CreateView):
    model = Transaction
    form_class = TransactionForm
    template_name = 'treasury/create_transaction.html'
    success_url = reverse_lazy('parent_profile')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['is_admin_view'] = False
        return kwargs

    def form_invalid(self, form):
        messages.error(self.request, f"Error al guardar: {form.errors}")
        return super().form_invalid(form)
    
    def form_valid(self, form):
        # Aseguramos que los campos ocultos se asignen correctamente
        form.instance.parent = self.request.user
        form.instance.transaction_type = 'INCOME' # Forzado a Ingreso
        form.instance.recorded_by = self.request.user
        
        # Validar límite máximo por padre en la meta seleccionada
        goal = form.cleaned_data.get('goal')
        if goal:
            total_user_contrib = Transaction.objects.filter(
                goal=goal, parent=self.request.user
            ).aggregate(total=Sum('amount_divisa'))['total'] or Decimal('0')
            
            amount = form.cleaned_data.get('amount') or 0
            tasa = form.cleaned_data.get('tasa_bcv') or 1
            new_amount = amount / tasa
            
            if total_user_contrib + new_amount > goal.max_per_parent:
                if total_user_contrib >= goal.max_per_parent:
                     messages.error(self.request, "Usted ya abonó lo que tenía que aportar para la meta.")
                else:
                     messages.error(self.request, f"Este abono supera el límite máximo permitido por padre para esta meta (${goal.max_per_parent}).")
                return self.form_invalid(form)

        messages.success(self.request, "Transacción guardada exitosamente.")
        return super().form_valid(form)
