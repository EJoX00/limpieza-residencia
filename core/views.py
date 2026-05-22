from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count  # CORRECCIÓN: Agregamos Count para contar las faltas
from .models import TurnoAsignado, CodigoRegistro, PerfilAdministrador, Tarea, Estudiante, ExcepcionHorario, Area, HistorialAccion
from .forms import RegistroAdminForm, EstudianteForm, ExcepcionForm, AsignacionManualForm
from .services import generar_turnos_para_fecha
import datetime

def cartelera_publica(request):
    """Vista pública (Cartelera) abierta para toda la residencia."""
    turnos = TurnoAsignado.objects.all().order_by('-fecha', 'turno_horario')
    return render(request, 'core/cartelera.html', {'turnos': turnos})

def registro_admin(request):
    """Registro de nuevos administradores usando código de carnet."""
    if request.method == 'POST':
        form = RegistroAdminForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.save()

            codigo_str = form.cleaned_data['codigo_carnet']
            codigo_obj = CodigoRegistro.objects.get(codigo=codigo_str)
            codigo_obj.usado = True
            codigo_obj.usuario_creado = user
            codigo_obj.save()

            PerfilAdministrador.objects.create(
                user=user,
                area_asignada=codigo_obj.area_permitida
            )

            # Dejar registro en el historial global
            HistorialAccion.objects.create(
                usuario=user,
                accion=f"Registró su nuevo perfil de administrador para el área {codigo_obj.area_permitida.get_nombre_display()}",
                area_origen=codigo_obj.area_permitida.get_nombre_display()
            )

            messages.success(request, "¡Perfil creado con éxito! Ya puedes iniciar sesión.")
            return redirect('login')
    else:
        form = RegistroAdminForm()
    return render(request, 'core/registro.html', {'form': form})


@login_required
def panel_control(request):
    """Panel privado adaptativo completo con buscador de faltas e historial."""
    if request.user.is_superuser:
        areas_disponibles = Area.objects.all()
        area_id = request.GET.get('area_id')
        if area_id:
            area = get_object_or_404(Area, id=area_id)
        else:
            area = areas_disponibles.first()
    else:
        perfil = get_object_or_404(PerfilAdministrador, user=request.user)
        area = perfil.area_asignada
        areas_disponibles = None

    turnos = TurnoAsignado.objects.filter(tarea__area=area).order_by('-fecha', 'turno_horario')
    
    # SUGERENCIA: Buscador de estudiantes optimizado que cuenta las faltas de cada uno automáticamente
    query_busqueda = request.GET.get('buscar_estudiante', '')
    base_estudiantes = Estudiante.objects.annotate(
        total_faltas=Count('turnoasignado', filter=Q(turnoasignado__estado='FALTO'))
    )
    
    if query_busqueda == 'DEUDORES':
        # FILTRO ESPECIAL: Muestra solo a los que tienen 1 falta o más
        lista_estudiantes = base_estudiantes.filter(total_faltas__gt=0).order_by('-total_faltas', 'nombre')
    elif query_busqueda:
        lista_estudiantes = base_estudiantes.filter(
            Q(nombre__icontains=query_busqueda) | 
            Q(carnet__icontains=query_busqueda) | 
            Q(habitacion__icontains=query_busqueda)
        ).order_by('habitacion', 'nombre')
    else:
        # 🔥 EL CAMBIO DEFINITIVO: Traerlos directo del modelo Estudiante sin "annotate" para saltarnos el bug
        lista_estudiantes = Estudiante.objects.all().order_by('habitacion', 'nombre')[:50]

    form_estudiante = EstudianteForm()
    form_excepcion = ExcepcionForm()
    
    form_manual = AsignacionManualForm()
    form_manual.fields['tarea'].queryset = Tarea.objects.filter(area=area)

    codigos_registro = None
    if request.user.is_superuser:
        codigos_registro = CodigoRegistro.objects.all().order_by('-usado')

    # HISTORIAL: Traemos las últimas 15 acciones ejecutadas en el sistema para mostrarlas en el panel
    historial = HistorialAccion.objects.all().order_by('-fecha_hora')[:15]
    
    # SUGERENCIA: Fecha de hoy por defecto para el formulario del generador
    fecha_hoy = datetime.date.today().strftime('%Y-%m-%d')

    return render(request, 'core/dashboard.html', {
        'area': area,
        'turnos': turnos,
        'areas_disponibles': areas_disponibles,
        'lista_estudiantes': lista_estudiantes,
        'query_busqueda': query_busqueda,
        'form_estudiante': form_estudiante,
        'form_excepcion': form_excepcion,
        'form_manual': form_manual,
        'codigos_registro': codigos_registro,
        'historial': historial, # Enviamos la bitácora al HTML
        'fecha_hoy': fecha_hoy
    })


@login_required
def acc_generar_rol(request):
    if request.method == 'POST':
        # 1. Capturar el área de forma ultra-segura contra nulos o vacíos
        area_id = request.POST.get('area_id')
        
        if request.user.is_superuser:
            if area_id and area_id.isdigit():
                area = get_object_or_404(Area, id=int(area_id))
            else:
                # Si viene vacío o dañado, agarramos la primera área disponible para que no estalle
                area = Area.objects.first()
        else:
            perfil = get_object_or_404(PerfilAdministrador, user=request.user)
            area = perfil.area_asignada
        
        fecha_str = request.POST.get('fecha')
        turno_horario = request.POST.get('turno_horario')
        
        # 2. Validar campos obligatorios
        if not fecha_str or not turno_horario:
            messages.error(request, "Error: Por favor selecciona una fecha y un turno válidos.")
            return redirect(f'/panel/?area_id={area.id}' if request.user.is_superuser else 'panel_control')
            
        try:
            fecha = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, f"Error: El formato de fecha recibido ('{fecha_str}') no es válido.")
            return redirect(f'/panel/?area_id={area.id}' if request.user.is_superuser else 'panel_control')
        
        # 3. Ejecutar el robot atrapando fallos internos
        try:
            generar_turnos_para_fecha(fecha, turno_horario, area)
            
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Generó automáticamente el rol del {fecha_str} ({turno_horario})",
                area_origen=area.get_nombre_display()
            )
            
            messages.success(request, f"¡Rol generado con éxito para el día {fecha_str}!")
        except Exception as e:
            # Cualquier aviso del service.py se mostrará aquí limpiamente
            messages.error(request, f"Aviso del sistema: {str(e)}")
            
        if request.user.is_superuser:
            return redirect(f'/panel/?area_id={area.id}')
            
    return redirect('panel_control')


@login_required
def acc_cambiar_estado(request, turno_id, nuevo_estado):
    turno = get_object_or_404(TurnoAsignado, id=turno_id)
    
    if not request.user.is_superuser:
        perfil = get_object_or_404(PerfilAdministrador, user=request.user)
        if turno.tarea.area != perfil.area_asignada:
            messages.error(request, "No tienes permisos para modificar turnos de otra área.")
            return redirect('panel_control')
        
    if nuevo_estado in ['PENDIENTE', 'CUMPLIDO', 'FALTO']:
        turno.estado = nuevo_estado
        turno.save()
        
        # AUDITORÍA: Guardar qué administrador modificó la asistencia
        HistorialAccion.objects.create(
            usuario=request.user,
            accion=f"Modificó asistencia de {turno.estudiante.nombre} a [{turno.get_estado_display()}] para el turno del {turno.fecha}",
            area_origen=turno.tarea.area.get_nombre_display()
        )
        
        messages.success(request, f"Estado del turno actualizado a {turno.get_estado_display()}.")
        
    if request.user.is_superuser:
        return redirect(f'/panel/?area_id={turno.tarea.area.id}')
    return redirect('panel_control')


@login_required
def acc_borrar_turno(request, turno_id):
    turno = get_object_or_404(TurnoAsignado, id=turno_id)
    area_id = turno.tarea.area.id
    
    if not request.user.is_superuser:
        perfil = get_object_or_404(PerfilAdministrador, user=request.user)
        if turno.tarea.area != perfil.area_asignada:
            messages.error(request, "No tienes permisos para borrar turnos de otra área.")
            return redirect('panel_control')
            
    # AUDITORÍA: Guardar quién eliminó la asignación
    HistorialAccion.objects.create(
        usuario=request.user,
        accion=f"Eliminó la asignación de {turno.estudiante.nombre} del día {turno.fecha} ({turno.tarea.nombre_tarea})",
        area_origen=turno.tarea.area.get_nombre_display()
    )
    
    turno.delete()
    messages.success(request, "Asignación eliminada. El cupo está libre nuevamente.")
    
    if request.user.is_superuser:
        return redirect(f'/panel/?area_id={area_id}')
    return redirect('panel_control')


@login_required
def g_estudiante(request):
    if request.method == 'POST':
        form = EstudianteForm(request.POST)
        if form.is_valid():
            estudiante = form.save()
            
            # AUDITORÍA: Guardar el alta del nuevo alumno
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Ingresó al estudiante {estudiante.nombre} (Habitación: {estudiante.habitacion}) al sistema general.",
                area_origen="Control Global"
            )
            
            messages.success(request, "Estudiante agregado exitosamente a las listas.")
    return redirect(request.META.get('HTTP_REFERER', 'panel_control'))


@login_required
def g_excepcion(request):
    if request.method == 'POST':
        form = ExcepcionForm(request.POST)
        if form.is_valid():
            ex = form.save()
            
            # AUDITORÍA: Guardar el bloqueo horario
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Creó un bloqueo horario académico para {ex.estudiante.nombre} los días {ex.get_dia_semana_display()}",
                area_origen="Control Global"
            )
            
            messages.success(request, "Excepción de horario académica guardada.")
        else:
            messages.error(request, "Error: Es posible que este alumno ya tenga esa excepción registrada.")
    return redirect(request.META.get('HTTP_REFERER', 'panel_control'))


@login_required
def g_manual(request):
    if request.method == 'POST':
        form = AsignacionManualForm(request.POST)
        if form.is_valid():
            turno = form.save()
            
            # AUDITORÍA: Guardar asignación a dedo
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Asignó MANUALMENTE a {turno.estudiante.nombre} para la tarea '{turno.tarea.nombre_tarea}' el {turno.fecha}",
                area_origen=turno.tarea.area.get_nombre_display()
            )
            
            messages.success(request, "Asignación manual registrada con éxito.")
        else:
            messages.error(request, "Datos inválidos en la asignación manual.")
    return redirect(request.META.get('HTTP_REFERER', 'panel_control'))


@login_required
def g_codigo(request):
    if not request.user.is_superuser:
        messages.error(request, "Acceso denegado.")
        return redirect('panel_control')
        
    if request.method == 'POST':
        codigo = request.POST.get('codigo', '').strip()
        area_id = request.POST.get('area_permitida')
        
        if codigo and area_id:
            area_obj = get_object_or_404(Area, id=area_id)
            if CodigoRegistro.objects.filter(codigo=codigo).exists():
                messages.error(request, "Este código ya existe.")
            else:
                CodigoRegistro.objects.create(codigo=codigo, area_permitida=area_obj)
                
                # AUDITORÍA: Guardar la creación del cupón de invitación
                HistorialAccion.objects.create(
                    usuario=request.user,
                    accion=f"Generó el código de acceso '{codigo}' para reclutar un admin de {area_obj.get_nombre_display()}",
                    area_origen="Control Global"
                )
                
                messages.success(request, f"Código '{codigo}' generado con éxito.")
                
    return redirect(request.META.get('HTTP_REFERER', 'panel_control'))

@login_required
def editar_estudiante(request, estudiante_id):
    """Vista para modificar los datos de un becado."""
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    if request.method == 'POST':
        form = EstudianteForm(request.POST, instance=estudiante)
        if form.is_valid():
            form.save()
            
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Editó los datos del estudiante {estudiante.nombre}.",
                area_origen="Control Global"
            )
            messages.success(request, f"Datos de {estudiante.nombre} actualizados con éxito.")
            return redirect('panel_control')
    else:
        form = EstudianteForm(instance=estudiante)
    
    return render(request, 'core/editar_estudiante.html', {'form': form, 'estudiante': estudiante})


@login_required
def borrar_estudiante(request, estudiante_id):
    """Vista para eliminar por completo a un becado del sistema."""
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    
    HistorialAccion.objects.create(
        usuario=request.user,
        accion=f"ELIMINÓ permanentemente al estudiante {estudiante.nombre} del sistema.",
        area_origen="Control Global"
    )
    
    messages.warning(request, f"El estudiante {estudiante.nombre} fue eliminado de las listas.")
    estudiante.delete()
    return redirect('panel_control')