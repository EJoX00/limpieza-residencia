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
        carnet = self.cleaned_data.get('carnet').strip().upper()
        if carnet == 'N/A':
            return carnet
        if Estudiante.objects.filter(carnet=carnet).exists():
            raise forms.ValidationError("Este número de carnet ya está registrado con otro estudiante.")
        return carnet


class ExcepcionForm(forms.ModelForm):
    # Definimos el campo de forma segura para aceptar texto ('TODOS') o números individuales
    dia_semana = forms.ChoiceField(
        choices=[('', '---------'), ('TODOS', 'Todos (Lunes a Viernes)')] + [
            (1, 'Lunes'), (2, 'Martes'), (3, 'Miércoles'),
            (4, 'Jueves'), (5, 'Viernes'), (6, 'Sábado'), (7, 'Domingo')
        ],
        label='Día de la Semana Ocupado'
    )

    class Meta:
        model = ExcepcionHorario
        fields = ['estudiante', 'dia_semana', 'turno']
        labels = {
            'estudiante': 'Selecciona el Estudiante',
            'turno': 'Turno Bloqueado',
        }


class AsignacionManualForm(forms.ModelForm):
    class Meta:
        model = TurnoAsignado
        fields = ['estudiante', 'tarea', 'fecha', 'turno_horario']
        widgets = {
            'fecha': forms.HiddenInput(),
            'turno_horario': forms.HiddenInput(),
        }
        labels = {
            'estudiante': 'Estudiante a Asignar',
            'tarea': 'Tarea Específica',
        }