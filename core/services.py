import datetime
from django.db import transaction
from django.db.models import Count, Q
from .models import Estudiante, ExcepcionHorario, TurnoAsignado, Tarea

def generar_turnos_para_fecha(fecha, turno_horario, area):
    """
    Busca de forma automática, justa e infinita a los estudiantes necesarios 
    para cubrir las tareas de un área en una fecha y turno específicos.
    Respeta estrictamente los géneros por baños, balancea 4H/4M en Áreas Verdes
    y obliga una patrulla mixta de 2H/2M en Jardines Internos.
    Aplica descarte cruzado inteligente de 3 turnos (MAÑANA, TARDE, NOCHE).
    """
    # Validar si existen tareas en esta área antes de hacer nada
    tareas = Tarea.objects.filter(area=area)
    if not tareas.exists():
        raise Exception(f"No hay tareas registradas en la base de datos para el área: {area}. Debes crearlas primero.")
        
    # 📆 CORRECCIÓN DE DESFASE: Django (0=Lunes, 6=Domingo) -> Tu DB (1=Lunes, 7=Domingo)
    dia_semana_django = fecha.weekday() 
    dia_semana_db = dia_semana_django + 1
    
    turnos_creados = []

    with transaction.atomic():
        for tarea in tareas:
            # 🚀 AJUSTE DE GÉNEROS Y REPETICIONES AUTOMÁTICAS
            if area.nombre == 'AREAS_V':
                # Si es áreas verdes, obligamos al bot a buscar 4 varones (M) y 4 mujeres (F)
                cupos_requeridos = [{'genero': 'M'} for _ in range(4)] + [{'genero': 'F'} for _ in range(4)]
            elif area.nombre == 'JARDINES':
                # 🏡 Si es Jardines Internos, obligamos una patrulla de 2 varones y 2 mujeres
                cupos_requeridos = [{'genero': 'M'} for _ in range(2)] + [{'genero': 'F'} for _ in range(2)]
            else:
                # Si son baños, se necesita 1 sola persona por tarea y el género va amarrado al baño correspondiente
                genero_baño = 'M' if area.nombre == 'BANOS_H' else 'F'
                cupos_requeridos = [{'genero': genero_baño}]
            
            # El ciclo se ejecutará la cantidad de cupos definidos arriba
            for cupo in cupos_requeridos:
                # 🚀 LÓGICA DE RONDAS INFINITAS POR COLA DE ROTACIÓN JUSTA
                estudiantes_qs = Estudiante.objects.annotate(
                    total_turnos=Count('turnoasignado')
                ).filter(genero=cupo['genero']).order_by('total_turnos', '?')

                estudiante_elegido = None

                # 🔍 Evaluar la disponibilidad real de cada muchacho
                for estudiante in estudiantes_qs:
                    
                    # REGLA 1: Excepciones de horario de clases (Descarte Inteligente Cruzado de 3 Turnos)
                    tiene_excepcion = ExcepcionHorario.objects.filter(
                        estudiante=estudiante,
                        dia_semana=dia_semana_db,
                        turno=turno_horario  # Filtra exactamente por el turno evaluado (MANANA, TARDE, NOCHE)
                    ).exists()
                    
                    if tiene_excepcion:
                        continue # Tiene clases en este turno, pasamos al siguiente estudiante libre

                    # REGLA 2: Exclusión mutua (No repetir al mismo estudiante el mismo día en distintas tareas)
                    ya_limpia_hoy = TurnoAsignado.objects.filter(
                        estudiante=estudiante, 
                        fecha=fecha
                    ).exists() or any(t.estudiante == estudiante for t in turnos_creados)
                    
                    if ya_limpia_hoy:
                        continue 

                    # Candidato ideal encontrado que cumple con el género, no limpia hoy y no tiene clases
                    estudiante_elegido = estudiante
                    break

                # Si el bucle termina y nadie de ese género pudo cubrir el puesto por choques de horario
                if not estudiante_elegido:
                    genero_texto = "Varones" if cupo['genero'] == 'M' else "Mujeres"
                    raise Exception(
                        f"Falta de personal: No hay suficientes estudiantes del género [{genero_texto}] disponibles "
                        f"(sin clases ni asignaciones hoy) para cubrir el cupo de '{tarea.nombre_tarea}' en el turno {turno_horario} el {fecha}."
                    )

                # 3. Crear el turno asignado de forma segura
                nuevo_turno = TurnoAsignado.objects.create(
                    estudiante=estudiante_elegido,
                    tarea=tarea,
                    fecha=fecha,
                    turno_horario=turno_horario,
                    estado='PENDIENTE'
                )
                turnos_creados.append(nuevo_turno)

    return turnos_creados