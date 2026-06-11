# retail_chile/urls.py
from django.contrib import admin
from django.urls import path
from retail_app import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('ingestar/', views.ingestar_venta_manual, name='ingestar_venta_manual'),
    path('dashboard/', views.dashboard_analitico, name='dashboard_analitico'),
]
