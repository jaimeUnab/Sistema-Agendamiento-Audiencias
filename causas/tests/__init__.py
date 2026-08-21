"""
Paquete de pruebas de la aplicación Causas.

Mismo criterio que audiencias/tests/: separa las pruebas UNITARIAS
de ServicioImportacionCausas (test_services_unit.py, llamado
directamente en Python, sin pasar por ninguna vista HTTP) de las
pruebas de INTEGRACIÓN (test_integration.py, que recorren el flujo
HTTP completo -incluida la subida real de un archivo .xlsx- con el
cliente de pruebas de Django).
"""
