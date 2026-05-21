from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    path('', views.cartelera_publica, name='cartelera_publica'),
    path('registro/', views.registro_admin, name='registro_admin'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='cartelera_publica'), name='logout'),
    
    path('panel/', views.panel_control, name='panel_control'),
    path('panel/generar/', views.acc_generar_rol, name='acc_generar_rol'),
    path('panel/estado/<int:turno_id>/<str:nuevo_estado>/', views.acc_cambiar_estado, name='acc_cambiar_estado'),
    
    # Nuevas rutas añadidas
    path('panel/borrar/<int:turno_id>/', views.acc_borrar_turno, name='acc_borrar_turno'),
    path('panel/guardar-estudiante/', views.g_estudiante, name='g_estudiante'),
    path('panel/guardar-excepcion/', views.g_excepcion, name='g_excepcion'),
    path('panel/guardar-manual/', views.g_manual, name='g_manual'),
   
    path('panel/guardar-codigo/', views.g_codigo, name='g_codigo'),

    path('estudiante/editar/<int:estudiante_id>/', views.editar_estudiante, name='editar_estudiante'),
    path('estudiante/borrar/<int:estudiante_id>/', views.borrar_estudiante, name='borrar_estudiante'),
]