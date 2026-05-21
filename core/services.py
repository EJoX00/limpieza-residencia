import datetime
from django.db import transaction
from django.db.models import Count, Q
from .models import Estudiante, ExcepcionHorario, TurnoAsignado, Tarea

def generar_turnos_para_fecha(fecha, turno_horario, area):
    """
    Busca de forma automática, justa e infinita a los estudiantes necesarios 
    para cubrir las tareas de un área en una fecha y turno específicos.
    """
    # Validar si existen tareas en esta área antes de hacer nada
    tareas = Tarea.objects.filter(area=area)
    if not tareas.exists():
        raise Exception(f"No hay tareas registradas en la base de datos para el área: {area.get_nombre_display()}. Debes crearlas primero.")
        
    # Formato estándar de Django para días de la semana (0=Lunes, 1=Martes, ..., 6=Domingo)
    dia_semana_django = fecha.weekday() 
    turnos_creados = []

    with transaction.atomic():
        for tarea in tareas:
            # Si es áreas verdes, el ciclo se ejecutará 8 veces para esa misma tarea
            repeticiones = 8 if area.nombre == 'AREAS_V' else 1
            
            for _ in range(repeticiones):
                # 🚀 LÓGICA DE RONDAS INFINITAS: Contamos las asistencias totales de cada estudiante
                estudiantes_qs = Estudiante.objects.annotate(
                    total_turnos=Count('turnoasignado')
                )

                # Filtrar según el género requerido por el Área o traerlos todos
                if area.nombre == 'BANOS_H':
                    estudiantes_qs = estudiantes_qs.filter(genero='M').order_by('total_turnos', '?')
                elif area.nombre == 'BANOS_M':
                    estudiantes_qs = estudiantes_qs.filter(genero='F').order_by('total_turnos', '?')
                else:
                    estudiantes_qs = estudiantes_qs.order_by('total_turnos', '?')

                estudiante_elegido = None

                # 2. Evaluar la disponibilidad real de cada muchacho
                for estudiante in estudiantes_qs:
                    # REGLA 1: Excepciones de horario de clases (Probamos con el número y con el string por si acaso)
                    tiene_excepcion = ExcepcionHorario.objects.filter(
                        Q(dia_semana=str(dia_semana_django)) | Q(dia_semana=dia_semana_django),
                        estudiante=estudiante,
                        turno=turno_horario
                    ).exists()
                    if tiene_excepcion:
                        continue 

                    # REGLA 2: Exclusión mutua (No repetir al mismo estudiante hoy)
                    ya_limpia_hoy = TurnoAsignado.objects.filter(
                        estudiante=estudiante,
                        fecha=fecha
                    ).exists() or any(t.estudiante == estudiante for t in turnos_creados)
                    
                    if ya_limpia_hoy:
                        continue 

                    # Candidato ideal encontrado
                    estudiante_elegido = estudiante
                    break

                # Si el bucle termina y nadie pudo cubrir el puesto
                if not estudiante_elegido:
                    raise Exception(
                        f"Falta de personal: No hay suficientes estudiantes disponibles (que no tengan clases o turnos hoy) "
                        f"para completar los cupos de '{tarea.nombre_tarea}' el {fecha}."
                    )

                # 3. Crear el turno asignado
                nuevo_turno = TurnoAsignado.objects.create(
                    estudiante=estudiante_elegido,
                    tarea=tarea,
                    fecha=fecha,
                    turno_horario=turno_horario,
                    estado='PENDIENTE'
                )
                turnos_creados.append(nuevo_turno)

    return turnos_creados