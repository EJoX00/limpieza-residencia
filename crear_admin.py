import os
import django

# Indicamos formalmente dónde están las configuraciones
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth.models import User

# Creamos tu perfil si no existe
if not User.objects.filter(username='E.Rios').exists():
    User.objects.create_superuser('E.Rios', 'elielrios@gmail.com', 'residencia321')
    print("¡Superusuario E.Rios creado exitosamente en internet!")
else:
    print("El usuario E.Rios ya existía.")