import datetime
from django.db import transaction
from django.db.models import Max
from .models import Estudiante, ExcepcionHorario, TurnoAsignado, Tarea

def generar_turnos_para_fecha(fecha, turno_horario, area):
    """
    Busca de forma automática y justa a los estudiantes necesarios 
    para cubrir las tareas de un área en una fecha y turno específicos.
    Soporta asignación múltiple (8 personas) para Áreas Verdes.
    """
    tareas = Tarea.objects.filter(area=area)
    if not tareas.exists():
        raise Exception(f"No hay tareas registradas para el área: {area}")
        
    dia_semana_num = fecha.isoweekday() # Lunes = 1, Domingo = 7
    turnos_creados = []

    with transaction.atomic():
        for tarea in tareas:
            # Determinamos cuántas personas necesitamos para esta tarea específica
            # Si es áreas verdes, el ciclo se ejecutará 8 veces para esa misma tarea
            repeticiones = 8 if area.nombre == 'AREAS_V' else 1
            
            for _ in range(repeticiones):
                # 1. Filtrar estudiantes según el tipo de área (Género o General)
                estudiantes_qs = Estudiante.objects.all()
                if area.nombre == 'BANOS_H':
                    estudiantes_qs = estudiantes_qs.filter(genero='M').order_by('posicion_cola_banos')
                elif area.nombre == 'BANOS_M':
                    estudiantes_qs = estudiantes_qs.filter(genero='F').order_by('posicion_cola_banos')
                else:
                    # Áreas Verdes: entran todos ordenados por su respectiva cola
                    estudiantes_qs = estudiantes_qs.order_by('posicion_cola_verdes')

                estudiante_elegido = None

                # 2. Evaluar quién cumple con los requisitos mínimos de disponibilidad
                for estudiante in estudiantes_qs:
                    # REGLA 1: Excepciones de horario de clases
                    tiene_excepcion = ExcepcionHorario.objects.filter(
                        estudiante=estudiante,
                        dia_semana=dia_semana_num,
                        turno=turno_horario
                    ).exists()
                    if tiene_excepcion:
                        continue 

                    # REGLA 2: Exclusión mutua (No repetir el mismo día en nada)
                    ya_limpia_hoy = TurnoAsignado.objects.filter(
                        estudiante=estudiante,
                        fecha=fecha
                    ).exists()
                    if ya_limpia_hoy:
                        continue 

                    # Si pasa los filtros, este estudiante se queda con el cupo
                    estudiante_elegido = estudiante
                    break

                if not estudiante_elegido:
                    raise Exception(
                        f"Falta de personal: No hay suficientes estudiantes disponibles para "
                        f"completar los cupos requeridos en '{tarea.nombre_tarea}' el {fecha} ({turno_horario})."
                    )

                # 3. Crear el turno asignado pendiente
                nuevo_turno = TurnoAsignado.objects.create(
                    estudiante=estudiante_elegido,
                    tarea=tarea,
                    fecha=fecha,
                    turno_horario=turno_horario,
                    estado='PENDIENTE'
                )
                turnos_creados.append(nuevo_turno)

                # 4. Rotación Justa: Mandar al estudiante seleccionado al final de la cola
                if area.nombre in ['BANOS_H', 'BANOS_M']:
                    max_pos = Estudiante.objects.all().aggregate(Max('posicion_cola_banos'))['posicion_cola_banos__max'] or 0
                    estudiante_elegido.posicion_cola_banos = max_pos + 1
                else:
                    max_pos = Estudiante.objects.all().aggregate(Max('posicion_cola_verdes'))['posicion_cola_verdes__max'] or 0
                    estudiante_elegido.posicion_cola_verdes = max_pos + 1
                
                estudiante_elegido.save()

    return turnos_creados