from django.db import migrations

def insertar_jardines_y_tareas(apps, schema_editor):
    Area = apps.get_model('core', 'Area')
    Tarea = apps.get_model('core', 'Tarea')

    # 🚀 BLINDAJE ANTI-CHOQUES: Buscamos por el campo único 'nombre' 
    # para evitar que intente duplicar llaves primarias en Supabase
    area_jardines, created = Area.objects.get_or_create(
        nombre='JARDINES'
    )

    # Creamos su primera tarea correspondiente de forma segura
    Tarea.objects.get_or_create(
        nombre_tarea='Limpieza y riego de maceteros internos',
        area=area_jardines
    )

def revertir_jardines(apps, schema_editor):
    Area = apps.get_model('core', 'Area')
    Area.objects.filter(nombre='JARDINES').delete()

class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_alter_area_nombre'), 
    ]

    operations = [
        migrations.RunPython(insertar_jardines_y_tareas, revertir_jardines),
    ]