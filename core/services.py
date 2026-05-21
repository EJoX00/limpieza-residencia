import datetime
from django.db import transaction
from django.db.models import Count, Q
from .models import Estudiante, ExcepcionHorario, TurnoAsignado, Tarea

def generar_turnos_para_fecha(fecha, turno_horario, area):
    """
    Busca de forma automática, justa e infinita a los estudiantes necesarios 
    para cubrir las tareas de un área en una fecha y turno específicos.
    Implementa reinicio automático de rondas basado en conteo acumulativo.
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
                # 1. 🚀 LÓGICA DE RONDAS INFINITAS: Contamos las asistencias totales de cada estudiante
                # Se ordena primero al que menos veces ha limpiado en la historia del sistema.
                # El '?' baraja aleatoriamente a los estudiantes que estén empatados (ej: al inicio con 0 faltas/turnos).
                estudiantes_qs = Estudiante.objects.annotate(
                    total_turnos=Count('turnoasignado')
                )

                # Filtrar según las reglas de Género o General del Área
                if area.nombre == 'BANOS_H':
                    estudiantes_qs = estudiantes_qs.filter(genero='M').order_by('total_turnos', '?')
                elif area.nombre == 'BANOS_M':
                    estudiantes_qs = estudiantes_qs.filter(genero='F').order_by('total_turnos', '?')
                else:
                    # Áreas Verdes: entran todos por igual ordenados por carga de trabajo acumulada
                    estudiantes_qs = estudiantes_qs.order_by('total_turnos', '?')

                estudiante_elegido = None

                # 2. Evaluar quién cumple con los requisitos mínimos de disponibilidad
                for estudiante in estudiantes_qs:
                    # REGLA 1: Excepciones de horario de clases (Evita que limpien si están en la universidad)
                    tiene_excepcion = ExcepcionHorario.objects.filter(
                        estudiante=estudiante,
                        dia_semana=str(dia_semana_num),
                        turno=turno_horario
                    ).exists()
                    if tiene_excepcion:
                        continue 

                    # REGLA 2: Exclusión mutua (No repetir al mismo estudiante en varias tareas el mismo día)
                    # OJO: Excluimos de la validación a los ya asignados en ESTA misma iteración para que no se dupliquen
                    ya_limpia_hoy = TurnoAsignado.objects.filter(
                        estudiante=estudiante,
                        fecha=fecha
                    ).exists() or any(t.estudiante == estudiante for t in turnos_creados)
                    
                    if ya_limpia_hoy:
                        continue 

                    # Si pasa los filtros, este estudiante se queda con el cupo
                    estudiante_elegido = estudiante
                    break

                # Si recorrió todo el universo de estudiantes y nadie puede (caso extremo de bloqueos masivos)
                if not estudiante_elegido:
                    raise Exception(
                        f"Falta de personal: No hay suficientes estudiantes disponibles para "
                        f"completar los cupos requeridos en '{tarea.nombre_tarea}' el {fecha} ({turno_horario})."
                    )

                # 3. Crear el turno asignado pendiente directo en Supabase
                nuevo_turno = TurnoAsignado.objects.create(
                    estudiante=estudiante_elegido,
                    tarea=tarea,
                    fecha=fecha,
                    turno_horario=turno_horario,
                    estado='PENDIENTE'
                )
                turnos_creados.append(nuevo_turno)

                # NOTA: Ya no hace falta modificar ni guardar la 'posicion_cola' de forma manual,
                # ya que Django calculará la prioridad en tiempo real en la siguiente vuelta contando los turnos.

    return turnos_creados