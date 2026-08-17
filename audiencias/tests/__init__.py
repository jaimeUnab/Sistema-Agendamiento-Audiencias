"""
Paquete de pruebas de la aplicación Audiencias.

Antes existía un único archivo audiencias/tests.py; se reorganizó
en este paquete para separar claramente, según pide el proyecto de
título, las pruebas UNITARIAS de las pruebas de INTEGRACIÓN (Django
descubre igual los archivos "test_*.py" dentro de un paquete
"tests/" que dentro de un módulo "tests.py" -mismo mecanismo de
DiscoverRunner-, así que esta reorganización no cambia qué se
ejecuta ni cómo).

- test_models.py: pruebas de modelo (creación directa vía el ORM,
  sin lógica de negocio). Ya existían antes de esta tarea; se
  movieron aquí tal cual.
- test_services_unit.py: pruebas UNITARIAS de la lógica de negocio
  de audiencias/services.py (ValidadorAgendamiento,
  GeneradorPropuestaFecha y las funciones internas que ambos
  comparten), llamadas directamente en Python, sin pasar por
  ninguna vista HTTP.
- test_forms_unit.py: pruebas UNITARIAS de AudienciaForm
  (audiencias/forms.py), construido y validado directamente, sin
  vistas HTTP.
- test_integration.py: pruebas de INTEGRACIÓN que recorren el flujo
  HTTP completo (login, formulario, disponibilidad, reglas de
  agendamiento, registro, agenda, propuestas, trazabilidad)
  mediante el cliente de pruebas de Django (self.client).
"""
