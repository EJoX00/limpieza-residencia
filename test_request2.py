import os, django, datetime
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()

from django.test import Client, RequestFactory
from django.contrib.auth.models import User
from core.models import Area, TurnoAsignado, PerfilAdministrador
from core.views import acc_generar_rol
from django.contrib.messages.middleware import MessageMiddleware
from django.contrib.sessions.middleware import SessionMiddleware
from django.test.client import RequestFactory

# Test 1: Direct function call - different areas
from core.services import generar_turnos_para_fecha

for area_name in ['BANOS_H', 'BANOS_M', 'AREAS_V']:
    try:
        area = Area.objects.get(nombre=area_name)
        fecha = datetime.date.today()
        result = generar_turnos_para_fecha(fecha, 'NOCHE', area)
        print(f'{area_name}: OK - {len(result)} turnos')
    except Exception as e:
        print(f'{area_name}: ERROR - {e}')

# Clean up test data
TurnoAsignado.objects.all().delete()
print(f'\nDeleted test data. Turnos remaining: {TurnoAsignado.objects.count()}')

# Test 2: Simulate full view with RequestFactory
from django.http import HttpRequest

print('\n--- Testing full view flow ---')
user = User.objects.get(username='testadmin')
area = Area.objects.get(nombre='BANOS_H')

# Build a POST request
factory = RequestFactory()
request = factory.post('/panel/generar/', {
    'area_id': area.id,
    'fecha': '2026-05-21',
    'turno_horario': 'NOCHE'
})
request.user = user

# Add session and message middleware
session_middleware = SessionMiddleware(lambda req: None)
session_middleware.process_request(request)
request.session.save()

message_middleware = MessageMiddleware(lambda req: None)
message_middleware.process_request(request)

# Call the view
try:
    response = acc_generar_rol(request)
    print(f'View response status: {response.status_code}')
    print(f'View response url: {response.url}')
except Exception as e:
    import traceback
    traceback.print_exc()

print(f'\nTurnos creados: {TurnoAsignado.objects.count()}')
