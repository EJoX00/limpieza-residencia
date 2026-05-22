import os, django, datetime
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'
django.setup()
from django.test import Client
from django.contrib.auth.models import User
from core.models import Area, TurnoAsignado

c = Client()
user = User.objects.get(username='testadmin')
c.force_login(user)

area = Area.objects.get(nombre='BANOS_H')

response = c.post('/panel/generar/', {
    'area_id': area.id,
    'fecha': '2026-05-21',
    'turno_horario': 'NOCHE'
}, follow=True)

print(f'Status code: {response.status_code}')
print(f'Redirect chain: {response.redirect_chain}')

if response.status_code == 500:
    print('ERROR 500 - checking template errors...')
    # Try to find any error info
    if hasattr(response, 'context_data') and response.context_data:
        print('Context:', response.context_data)
    print('Response content (first 2000 chars):')
    print(response.content.decode('utf-8')[:2000])

print(f'Turnos creados: {TurnoAsignado.objects.count()}')

for t in TurnoAsignado.objects.all():
    print(f'  - {t.estudiante.nombre} -> {t.tarea.nombre_tarea} ({t.turno_horario})')
