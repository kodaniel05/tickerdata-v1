from django.urls import path

from .views import stock_summary

urlpatterns = [
    path('<str:ticker>/', stock_summary, name='stock-summary'),
]
