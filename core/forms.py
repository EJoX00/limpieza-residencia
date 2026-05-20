from django import forms
from django.contrib.auth.models import User
from .models import CodigoRegistro, Estudiante, ExcepcionHorario, TurnoAsignado, Tarea

class RegistroAdminForm(forms.ModelForm):
    codigo_carnet = forms.CharField(max_length=20, required=True, label="Código de Carnet Autorizado")
    password = forms.CharField(widget=forms.PasswordInput, required=True, label="Contraseña")

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name']

    def clean_codigo_carnet(self):
        codigo = self.cleaned_data.get('codigo_carnet')
        try:
            registro = CodigoRegistro.objects.get(codigo=codigo, usado=False)
        except CodigoRegistro.DoesNotExist:
            raise forms.ValidationError("El código de carnet no es válido o ya fue utilizado por otra persona.")
        return codigo


class EstudianteForm(forms.ModelForm):
    class Meta:
        model = Estudiante
        fields = ['nombre', 'genero', 'carnet', 'carrera', 'habitacion']
        labels = {
            'nombre': 'Nombre Completo del Estudiante',
            'genero': 'Género',
            'carnet': 'Número de Carnet Universitario (Poner N/A si no tiene)',
            'carrera': 'Carrera',
            'habitacion': 'Número de Habitación',
        }

    def clean_carnet(self):
        carnet = self.cleaned_data.get('carnet').strip().upper() # Limpiamos espacios y pasamos a mayúsculas
        
        # Si es N/A, lo dejamos pasar sin importar cuántos haya
        if carnet == 'N/A':
            return carnet
            
        # Si es un carnet real, verificamos que no esté duplicado en el sistema
        if Estudiante.objects.filter(carnet=carnet).exists():
            raise forms.ValidationError("Este número de carnet ya está registrado con otro estudiante.")
            
        return carnet


class ExcepcionForm(forms.ModelForm):
    class Meta:
        model = ExcepcionHorario
        fields = ['estudiante', 'dia_semana', 'turno']
        labels = {
            'estudiante': 'Selecciona el Estudiante',
            'dia_semana': 'Día de la Semana Ocupado',
            'turno': 'Turno Bloqueado',
        }


class AsignacionManualForm(forms.ModelForm):
    class Meta:
        model = TurnoAsignado
        fields = ['estudiante', 'tarea', 'fecha', 'turno_horario']
        labels = {
            'estudiante': 'Estudiante a Asignar',
            'tarea': 'Tarea Específica',
            'fecha': 'Fecha Planificada',
            'turno_horario': 'Horario del Turno',
        }