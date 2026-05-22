import datetime
from django.db import transaction
from django.db.models import Count, Q
from .models import Estudiante, ExcepcionHorario, TurnoAsignado, Tarea

def generar_turnos_para_fecha(fecha, turno_horario, area):
    """
    Busca de forma automática, justa e infinita a los estudiantes necesarios 
    para cubrir las tareas de un área en una fecha y turno específicos.
    Respeta estrictamente los géneros por baños y balancea 4H/4M en Áreas Verdes.
    """
    # Validar si existen tareas en esta área antes de hacer nada
    # CORRECCIÓN: Quitamos .get_nombre_display() directo de la excepción para evitar bugs de atributos
    tareas = Tarea.objects.filter(area=area)
    if not tareas.exists():
        raise Exception(f"No hay tareas registradas en la base de datos para el área: {area}. Debes crearlas primero.")
        
    # Formato estándar de Django para días de la semana (0=Lunes, 1=Martes, ..., 6=Domingo)
    dia_semana_django = fecha.weekday() 
    turnos_creados = []

    with transaction.atomic():
        for tarea in tareas:
            # 🚀 AJUSTE DE GÉNEROS Y REPETICIONES AUTOMÁTICAS
            # Creamos una lista de diccionarios que le dice al robot exactamente el género que ocupamos en cada cupo
            if area.nombre == 'AREAS_V':
                # Si es áreas verdes, obligamos al bot a buscar 4 varones (M) y 4 mujeres (F)
                cupos_requeridos = [{'genero': 'M'} for _ in range(4)] + [{'genero': 'F'} for _ in range(4)]
            else:
                # Si son baños, se necesita 1 sola persona por tarea y el género va amarrado al baño correspondiente
                genero_baño = 'M' if area.nombre == 'BANOS_H' else 'F'
                cupos_requeridos = [{'genero': genero_baño}]
            
            # El ciclo se ejecutará la cantidad de cupos definidos arriba (8 veces en áreas verdes, 1 en baños)
            for cupo in cupos_requeridos:
                # 🚀 LÓGICA DE RONDAS INFINITAS: Contamos las asistencias totales filtrando por el género del cupo actual
                estudiantes_qs = Estudiante.objects.annotate(
                    total_turnos=Count('turnoasignado')
                ).filter(genero=cupo['genero']).order_by('total_turnos', '?')

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

                    # Candidato ideal encontrado que cumple con el género y el horario
                    estudiante_elegido = estudiante
                    break

                # Si el bucle termina y nadie de ese género pudo cubrir el puesto
                if not estudiante_elegido:
                    genero_texto = "Varones" if cupo['genero'] == 'M' else "Mujeres"
                    raise Exception(
                        f"Falta de personal: No hay suficientes estudiantes del género [{genero_texto}] disponibles "
                        f"(sin clases ni asignaciones hoy) para cubrir el cupo de '{tarea.nombre_tarea}' el {fecha}."
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