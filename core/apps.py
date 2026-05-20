from django.apps import AppConfig
from django.db.models.signals import post_migrate

def crear_superusuario_automatico(sender, **kwargs):
    from django.contrib.auth.models import User
    # Cambia 'admin_eliel' y 'TuContraseña123' por lo que tú quieras usar para entrar
    if not User.objects.filter(username='E.Rios').exists():
        User.objects.create_superuser(
            username='E.Rios',
            email='elielrios@gmail.com',
            password='residencia321'
        )
        print("¡Superusuario maestro creado con éxito en producción!")


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    def ready(self):
            # Esto ejecuta la función automáticamente justo después de que terminan las migraciones
            post_migrate.connect(crear_superusuario_automatico, sender=self)