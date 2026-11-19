from django.urls import path

from .views import AmarresView, BuquesView, CablesView, HistorialCableView, ReplayView, SellosView, ValidacionView

app_name = 'cables'

urlpatterns = [
    path('', CablesView.as_view(), name='cables'),
    path('amarres/', AmarresView.as_view(), name='amarres'),
    path('buques/', BuquesView.as_view(), name='buques'),
    path('validacion/', ValidacionView.as_view(), name='validacion'),
    path('replay/', ReplayView.as_view(), name='replay'),
    path('<slug:slug>/historial/', HistorialCableView.as_view(), name='historial'),
    path('sellos/', SellosView.as_view(), name='sellos'),
]
