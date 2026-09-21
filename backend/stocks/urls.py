from django.urls import path

from .views import stock_compare, stock_history, stock_summary

urlpatterns = [
    path('stocks/<str:ticker>/', stock_summary, name='stock-summary'),
    path('stocks/<str:ticker>/history/', stock_history, name='stock-history'),
    path('compare/', stock_compare, name='stock-compare'),
]
