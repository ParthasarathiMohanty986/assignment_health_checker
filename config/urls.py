from django.urls import path
from django.http import HttpResponse
from django.contrib.auth import views as auth
from checker import views
urlpatterns = [
    path('health/', lambda request: HttpResponse('ok')), 
    path('local-login/',views.local_login,name='local_login'),
    path('login/',auth.LoginView.as_view(template_name='checker/login.html'),name='login'),
    path('logout/',auth.LogoutView.as_view(),name='logout'),
    path('',views.index,name='index'),path('upload/',views.upload,name='upload'),
    path('demo/',views.demo,name='demo'),
    path('assignments/<int:pk>/',views.detail,name='detail'),
    path('assignments/<int:pk>/review/',views.review,name='review'),
    path('assignments/<int:pk>/run/',views.run,name='run'),
    path('runs/<int:pk>/suggest/',views.suggest,name='suggest'),
    path('runs/<int:pk>/export/',views.export,name='export'),
]
