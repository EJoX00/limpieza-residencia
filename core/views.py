from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q, Count
from django.db.models.functions import Cast   
from django.db.models import IntegerField      
from .models import TurnoAsignado, CodigoRegistro, PerfilAdministrador, Tarea, Estudiante, ExcepcionHorario, Area, HistorialAccion
from .forms import RegistroAdminForm, EstudianteForm, ExcepcionForm, AsignacionManualForm
from .services import generar_turnos_para_fecha
import datetime

def cartelera_publica(request):
    """Vista pública (Cartelera) abierta para toda la residencia."""
    turnos = TurnoAsignado.objects.all().annotate(
        habitacion_int=Cast('estudiante__habitacion', output_field=IntegerField())
    ).order_by('-fecha', 'habitacion_int', 'estudiante__nombre')
    
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
    
    query_busqueda = request.GET.get('buscar_estudiante', '')
    base_estudiantes = Estudiante.objects.annotate(
        total_faltas=Count('turnoasignado', filter=Q(turnoasignado__estado='FALTO'))
    )
    
    if query_busqueda == 'DEUDORES':
        lista_estudiantes = base_estudiantes.filter(total_faltas__gt=0).order_by('-total_faltas', 'nombre')
    elif query_busqueda:
        lista_estudiantes = base_estudiantes.filter(
            Q(nombre__icontains=query_busqueda) | 
            Q(carnet__icontains=query_busqueda) | 
            Q(habitacion__icontains=query_busqueda)
        ).order_by('habitacion', 'nombre')
    else:
        lista_estudiantes = Estudiante.objects.all().order_by('habitacion', 'nombre')[:50]

    form_estudiante = EstudianteForm()
    form_excepcion = ExcepcionForm()
    
    form_manual = AsignacionManualForm()
    form_manual.fields['tarea'].queryset = Tarea.objects.filter(area=area)
    
    estudiantes_manual_qs = Estudiante.objects.all()
    
    if area.nombre == 'BANOS_H':
        estudiantes_manual_qs = estudiantes_manual_qs.filter(genero='M')
    elif area.nombre == 'BANOS_M':
        estudiantes_manual_qs = estudiantes_manual_qs.filter(genero='F')
        
    estudiantes_manual_qs = estudiantes_manual_qs.exclude(
        turnoasignado__estado='CUMPLIDO'
    ).annotate(
        habitacion_num=Cast('habitacion', output_field=IntegerField())  
    ).distinct().order_by('habitacion_num', 'nombre')  
    
    form_manual.fields['estudiante'].queryset = estudiantes_manual_qs
    
    codigos_registro = None
    if request.user.is_superuser:
        codigos_registro = CodigoRegistro.objects.all().order_by('-usado')

    historial = HistorialAccion.objects.all().order_by('-fecha_hora')[:15]
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
        'historial': historial,
        'fecha_hoy': fecha_hoy
    })


@login_required
def acc_generar_rol(request):
    if request.method == 'POST':
        area_id = request.POST.get('area_id')
        if request.user.is_superuser:
            if area_id and area_id.isdigit():
                area = get_object_or_404(Area, id=int(area_id))
            else:
                area = Area.objects.first()
        else:
            perfil = get_object_or_404(PerfilAdministrador, user=request.user)
            area = perfil.area_asignada
        
        fecha_str = request.POST.get('fecha')
        turno_horario = request.POST.get('turno_horario')
        
        if not fecha_str or not turno_horario:
            messages.error(request, "Error: Por favor selecciona una fecha y un turno válidos.")
            return redirect(f'/panel/?area_id={area.id}' if request.user.is_superuser else 'panel_control')
            
        try:
            fecha = datetime.datetime.strptime(fecha_str, '%Y-%m-%d').date()
        except ValueError:
            messages.error(request, f"Error: El formato de fecha recibido ('{fecha_str}') no es válido.")
            return redirect(f'/panel/?area_id={area.id}' if request.user.is_superuser else 'panel_control')
        
        try:
            generar_turnos_para_fecha(fecha, turno_horario, area)
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Generó automáticamente el rol del {fecha_str} ({turno_horario})",
                area_origen=area.get_nombre_display()
            )
            messages.success(request, f"¡Rol generado con éxito para el día {fecha_str}!")
        except Exception as e:
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
        fecha_str = request.POST.get('fecha_contexto')
        turno_horario = request.POST.get('turno_contexto')
        post_data = request.POST.copy()
        
        if fecha_str:
            post_data['fecha'] = fecha_str
        else:
            post_data['fecha'] = datetime.date.today().strftime('%Y-%m-%d')
            
        if turno_horario:
            post_data['turno_horario'] = turno_horario
        else:
            post_data['turno_horario'] = 'NOCHE'
            
        form = AsignacionManualForm(post_data)
        if form.is_valid():
            turno = form.save()
            area_obj = turno.tarea.area
            HistorialAccion.objects.create(
                usuario=request.user,
                accion=f"Asignó MANUALMENTE a {turno.estudiante.nombre} para la tarea '{turno.tarea.nombre_tarea}'",
                area_origen=str(area_obj)
            )
            messages.success(request, "¡Asignación manual registrada con éxito!")
            if request.user.is_superuser:
                return redirect(f'/panel/?area_id={area_obj.id}')
        else:
            errores = ", ".join([f"{k}: {v[0]}" for k, v in form.errors.items()])
            messages.error(request, f"No se pudo asignar a dedo. Errores: {errores}")
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
                HistorialAccion.objects.create(
                    usuario=request.user,
                    accion=f"Generó el código de acceso '{codigo}' para reclutar un admin de {area_obj.get_nombre_display()}",
                    area_origen="Control Global"
                )
                messages.success(request, f"Código '{codigo}' generado con éxito.")
    return redirect(request.META.get('HTTP_REFERER', 'panel_control'))


@login_required
def editar_estudiante(request, estudiante_id):
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
    estudiante = get_object_or_404(Estudiante, id=estudiante_id)
    HistorialAccion.objects.create(
        usuario=request.user,
        accion=f"ELIMINÓ permanentemente al estudiante {estudiante.nombre} del sistema.",
        area_origen="Control Global"
    )
    messages.warning(request, f"El estudiante {estudiante.nombre} fue eliminado de las listas.")
    estudiante.delete()
    return redirect('panel_control')