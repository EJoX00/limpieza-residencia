from django.db import models
from django.contrib.auth.models import User

class Area(models.Model):
    NOMBRE_CHOICES = [
        ('BANOS_H', 'Baños Hombres'),
        ('BANOS_M', 'Baños Mujeres'),
        ('AREAS_V', 'Áreas Verdes'),
        ('JARDINES', 'Jardines Internos'),
    ]
    nombre = models.CharField(max_length=10, choices=NOMBRE_CHOICES, unique=True)

    def __str__(self):
        return self.get_nombre_display()


class PerfilAdministrador(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='perfil')
    area_asignada = models.ForeignKey(Area, on_delete=models.PROTECT)

    def __str__(self):
        return f"Admin: {self.user.username} | Área: {self.area_asignada}"


class CodigoRegistro(models.Model):
    codigo = models.CharField(max_length=20, unique=True)
    area_permitida = models.ForeignKey(Area, on_delete=models.CASCADE)
    usado = models.BooleanField(default=False)
    usuario_creado = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='codigo_origen')

    def __str__(self):
        estado = "Usado" if self.usado else "Disponible"
        return f"Código: {self.codigo} | Área: {self.area_permitida} ({estado})"


class Estudiante(models.Model):
    GENERO_CHOICES = [('M', 'Masculino'), ('F', 'Femenino')]
    nombre = models.CharField(max_length=150)
    genero = models.CharField(max_length=1, choices=GENERO_CHOICES)
    carnet = models.CharField(max_length=30) 
    carrera = models.CharField(max_length=100)
    habitacion = models.CharField(max_length=20) 
    
    posicion_cola_banos = models.IntegerField(default=0)
    posicion_cola_verdes = models.IntegerField(default=0)

    def __str__(self):
        return f"{self.nombre} (Carnet: {self.carnet} | Hab: {self.habitacion})"


class ExcepcionHorario(models.Model):
    DIA_CHOICES = [
        (0, 'Todos (Lunes a Viernes)'),  # 🚀 Opción masiva inyectada con éxito
        (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'),
        (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')
    ]
    TURNO_CHOICES = [
        ('MANANA', 'Mañana (8:00 AM)'),
        ('TARDE', 'Tarde (2:00 PM)'),
        ('NOCHE', 'Noche')
    ]
    
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE, related_name='excepciones')
    dia_semana = models.IntegerField(choices=DIA_CHOICES)
    turno = models.CharField(max_length=10, choices=TURNO_CHOICES)

    class Meta:
        unique_together = ('estudiante', 'dia_semana', 'turno')

    def __str__(self):
        return f"Excepción: {self.estudiante.nombre} - {self.get_dia_semana_display()} ({self.turno})"


class Tarea(models.Model):
    area = models.ForeignKey(Area, on_delete=models.CASCADE)
    nombre_tarea = models.CharField(max_length=50)

    def __str__(self):
        return f"{self.area.get_nombre_display()} - {self.nombre_tarea}"


class TurnoAsignado(models.Model):
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('CUMPLIDO', 'Cumplido'),
        ('FALTO', 'No Cumplido')
    ]
    estudiante = models.ForeignKey(Estudiante, on_delete=models.CASCADE)
    tarea = models.ForeignKey(Tarea, on_delete=models.CASCADE)
    fecha = models.DateField()
    turno_horario = models.CharField(max_length=10, choices=ExcepcionHorario.TURNO_CHOICES)
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE')

    def __str__(self):
        return f"{self.fecha} | {self.turno_horario} | {self.estudiante.nombre} -> {self.tarea.nombre_tarea}"
    

class HistorialAccion(models.Model):
    usuario = models.ForeignKey(User, on_delete=models.CASCADE)
    accion = models.CharField(max_length=255)
    fecha_hora = models.DateTimeField(auto_now_add=True)
    area_origen = models.CharField(max_length=50, blank=True, null=True)

    def __str__(self):
        formato_fecha = self.fecha_hora.strftime('%d/%m %H:%M')
        return f"{formato_fecha} | {self.usuario.username} -> {self.accion}"