from django.db import migrations

def insertar_jardines_y_tareas(apps, schema_editor):
    # Obtenemos los modelos dinámicamente desde el historial
    Area = apps.get_model('core', 'Area')
    Tarea = apps.get_model('core', 'Tarea')

    # 1. Creamos o actualizamos el Área de JARDINES
    area_jardines, created = Area.objects.update_or_create(
        nombre='JARDINES',
        defaults={}
    )

    # 2. Le creamos su primera tarea correspondiente
    Tarea.objects.update_or_create(
        nombre_tarea='Limpieza y riego de maceteros internos',
        area=area_jardines,
        defaults={}
    )

def revertir_jardines(apps, schema_editor):
    Area = apps.get_model('core', 'Area')
    Area.objects.filter(nombre='JARDINES').delete()

class Migration(migrations.Migration):

    dependencies = [
        # 🎯 CORRECCIÓN: Ahora depende estrictamente de tu última migración real
        ('core', '0005_alter_area_nombre'), 
    ]

    operations = [
        migrations.RunPython(insertar_jardines_y_tareas, revertir_jardines),
    ]