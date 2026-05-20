from django.contrib import admin
from .models import Area, PerfilAdministrador, CodigoRegistro, Estudiante, ExcepcionHorario, Tarea, TurnoAsignado

admin.site.register(Area)
admin.site.register(PerfilAdministrador)
admin.site.register(CodigoRegistro)
admin.site.register(Estudiante)
admin.site.register(ExcepcionHorario)
admin.site.register(Tarea)
admin.site.register(TurnoAsignado)