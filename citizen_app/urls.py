from django.urls import path
from .import views
from django.views.decorators.csrf import csrf_exempt

app_name = 'citizen_app'

urlpatterns = [
    path('', views.news, name='news'),
    path('register/', views.register_request, name='register'),
    path('login/', views.login_request, name='login'),
    path('logout/', views.logout_request, name='logout'),
    path('password_reset/', views.password_reset_request, name='password_reset'),
    path('pdf/', views.GeneratePdf.as_view(), name='pdf'),
    path('showreadmore/<title>', csrf_exempt(views.showReadMore), name='showreadmore'),
    path('report/', views.report, name='report'),
    path('payment/', views.payment, name='payment'),
]
