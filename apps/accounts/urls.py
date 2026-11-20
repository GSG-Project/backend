from django.urls import path

from . import views

app_name = 'accounts'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.LoginView.as_view(), name='login'),
    path('login/verify/', views.verify_login_code, name='login-verify'),
    path('login/resend/', views.resend_login_code, name='login-resend'),
    path('refresh/', views.RefreshView.as_view(), name='refresh'),
    path('me/', views.MeView.as_view(), name='me'),
    path('change-password/', views.change_password, name='change-password'),
    path('password-reset/', views.password_reset_request, name='password-reset'),
    path('password-reset/confirm/', views.password_reset_confirm, name='password-reset-confirm'),
    path('two-factor/enable/', views.two_factor_enable, name='two-factor-enable'),
    path('two-factor/confirm/', views.two_factor_confirm, name='two-factor-confirm'),
    path('two-factor/disable/', views.two_factor_disable, name='two-factor-disable'),
]
