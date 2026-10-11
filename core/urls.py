from django.urls import path
from .views import (
    AnnouncementVoteView, AnnouncementCommentView, SignUpView, CustomLoginView, 
    NoticiasView, AnnouncementCreateView, UserListView, UserDeleteView, UserUpdateView, TreasuryView, TransactionCreateView, TransactionUpdateView, TransactionDeleteView, TransactionDetailView, FinancialGoalCreateView, ParentProfileView, ParentPaymentView
)
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('login/', CustomLoginView.as_view(), name='login'),
    path('signup/', SignUpView.as_view(), name='signup'),
    path('logout/', LogoutView.as_view(), name='logout'),
    path('noticias/', NoticiasView.as_view(), name='noticias'),
    path('tesoreria/', TreasuryView.as_view(), name='treasury'),
    path('tesoreria/crear-transaccion/', TransactionCreateView.as_view(), name='create_transaction'),
    path('tesoreria/<int:pk>/', TransactionDetailView.as_view(), name='transaction_detail'),
    path('tesoreria/<int:pk>/editar/', TransactionUpdateView.as_view(), name='transaction_edit'),
    path('tesoreria/<int:pk>/eliminar/', TransactionDeleteView.as_view(), name='transaction_delete'),
    path('tesoreria/crear-meta/', FinancialGoalCreateView.as_view(), name='create_goal'),
    path('crear-noticia/', AnnouncementCreateView.as_view(), name='crear_noticia'),
    path('perfil/', ParentProfileView.as_view(), name='parent_profile'),
    path('abonar/', ParentPaymentView.as_view(), name='parent_payment'),
    path('usuarios/', UserListView.as_view(), name='user_list'),
    path('usuarios/<int:pk>/editar/', UserUpdateView.as_view(), name='user_edit'),
    path('usuarios/<int:pk>/eliminar/', UserDeleteView.as_view(), name='user_delete'),
    path('announcement/<int:pk>/vote/', AnnouncementVoteView.as_view(), name='vote'),
    path('announcement/<int:pk>/comment/', AnnouncementCommentView.as_view(), name='comment'),
]
