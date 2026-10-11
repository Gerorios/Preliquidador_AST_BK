"""Mapa de permisos de Liquidación Terceros (ADR-0020): qué pantalla y qué nivel
exige cada endpoint de `/api/terceros`.

`ESPERADO` copia las filas 22 a 34 de la tabla 2.4 del plan
(`docs/superpowers/plans/2026-10-09-esquema-permisos.md`). El mapa real se lee
de `app.routes`: cada dependencia de `requiere_pantalla` expone `.requisito`.
Una ruta nueva sin su fila, una fila sin ruta o un permiso distinto del de la
tabla hacen fallar el test.
"""
from fastapi.routing import APIRoute

from app.main import app

PREFIJO = "/api/terceros"

M = "terceros"


def _exige(nivel, *pantallas):
    # Alcanza con una de las pantallas: el orden no importa.
    return (M, frozenset(pantallas), nivel)


VER_CUALQUIERA = _exige("ver", "inicio", "quincena", "tarifario", "estaciones", "verificaciones")
VER_INICIO = _exige("ver", "inicio")
EDITAR_INICIO = _exige("editar", "inicio")
VER_INICIO_O_QUINCENA = _exige("ver", "inicio", "quincena")
VER_QUINCENA = _exige("ver", "quincena")
EDITAR_QUINCENA = _exige("editar", "quincena")
VER_TARIFARIO_O_ESTACIONES = _exige("ver", "tarifario", "estaciones")
VER_TARIFARIO = _exige("ver", "tarifario")
EDITAR_TARIFARIO = _exige("editar", "tarifario")
VER_ESTACIONES = _exige("ver", "estaciones")
EDITAR_ESTACIONES = _exige("editar", "estaciones")
VER_VERIFICACIONES = _exige("ver", "verificaciones")

T = PREFIJO

ESPERADO = {
    # 22
    ("GET", f"{T}/quincenas"): VER_CUALQUIERA,
    ("GET", f"{T}/"): VER_CUALQUIERA,
    # 23
    ("GET", f"{T}/liquidaciones"): VER_INICIO,
    # 24
    ("POST", f"{T}/liquidaciones/generar"): EDITAR_INICIO,
    ("POST", f"{T}/liquidaciones/calcular"): EDITAR_INICIO,
    # 25
    ("GET", f"{T}/liquidaciones/totales"): VER_INICIO_O_QUINCENA,
    ("GET", f"{T}/liquidaciones/pendientes"): VER_INICIO_O_QUINCENA,
    # 26
    ("GET", f"{T}/liquidaciones/lineas"): VER_QUINCENA,
    ("GET", f"{T}/repuestos/{{id_}}/cuotas"): VER_QUINCENA,
    # 27
    ("PATCH", f"{T}/hechos/{{concepto}}/{{id_}}/quincena"): EDITAR_QUINCENA,
    ("PUT", f"{T}/repuestos/{{id_}}/cuotas"): EDITAR_QUINCENA,
    ("DELETE", f"{T}/repuestos/{{id_}}/cuotas"): EDITAR_QUINCENA,
    # 28
    ("GET", f"{T}/viajes"): VER_QUINCENA,
    ("GET", f"{T}/combustible"): VER_QUINCENA,
    ("GET", f"{T}/repuestos"): VER_QUINCENA,
    ("GET", f"{T}/horas-servicio"): VER_QUINCENA,
    ("GET", f"{T}/horas-reparacion"): VER_QUINCENA,
    # 29
    ("GET", f"{T}/bienes"): VER_TARIFARIO_O_ESTACIONES,
    # 30
    ("GET", f"{T}/tarifario/resumen"): VER_TARIFARIO,
    ("GET", f"{T}/tarifario/{{tipo}}"): VER_TARIFARIO,
    ("GET", f"{T}/tarifario/{{tipo}}/combinaciones"): VER_TARIFARIO,
    # 31
    ("POST", f"{T}/tarifario/copiar"): EDITAR_TARIFARIO,
    ("POST", f"{T}/tarifario/{{tipo}}"): EDITAR_TARIFARIO,
    ("POST", f"{T}/tarifario/{{tipo}}/lote"): EDITAR_TARIFARIO,
    ("PATCH", f"{T}/tarifario/{{tipo}}/lote"): EDITAR_TARIFARIO,
    ("PATCH", f"{T}/tarifario/{{tipo}}/{{id_}}"): EDITAR_TARIFARIO,
    ("POST", f"{T}/tarifario/{{tipo}}/confirmar-lote"): EDITAR_TARIFARIO,
    ("POST", f"{T}/tarifario/{{tipo}}/{{id_}}/confirmar"): EDITAR_TARIFARIO,
    ("DELETE", f"{T}/tarifario/{{tipo}}/{{id_}}"): EDITAR_TARIFARIO,
    # 32
    ("GET", f"{T}/estaciones"): VER_ESTACIONES,
    ("GET", f"{T}/estaciones/cruce"): VER_ESTACIONES,
    ("GET", f"{T}/estaciones/{{id_}}/lineas"): VER_ESTACIONES,
    # 33
    ("POST", f"{T}/estaciones/{{id_}}/subir"): EDITAR_ESTACIONES,
    ("POST", f"{T}/estaciones/{{id_}}/lineas"): EDITAR_ESTACIONES,
    ("DELETE", f"{T}/estaciones/lineas/{{id_}}"): EDITAR_ESTACIONES,
    ("PATCH", f"{T}/estaciones/{{id_}}"): EDITAR_ESTACIONES,
    # 34
    ("GET", f"{T}/verificaciones"): VER_VERIFICACIONES,
    ("GET", f"{T}/alertas"): VER_VERIFICACIONES,
}


def _normalizar(requisito):
    if isinstance(requisito, tuple):
        modulo, pantallas, nivel = requisito
        return (modulo, frozenset(pantallas), nivel)
    return requisito  # "admin"


def _dependencias_con_requisito(dependant, vistas):
    """Las dependencias con `.requisito` de toda la cadena, sin repetir el mismo
    objeto (FastAPI la ejecuta una sola vez aunque aparezca dos veces)."""
    for dep in dependant.dependencies:
        if hasattr(dep.call, "requisito") and not any(dep.call is v for v in vistas):
            vistas.append(dep.call)
        _dependencias_con_requisito(dep, vistas)
    return vistas


def _mapa_real():
    mapa = {}
    for ruta in app.routes:
        if not isinstance(ruta, APIRoute) or not ruta.path.startswith(PREFIJO):
            continue
        for metodo in ruta.methods:
            clave = (metodo, ruta.path)
            assert clave not in mapa, f"ruta repetida: {clave}"
            mapa[clave] = [
                _normalizar(d.requisito)
                for d in _dependencias_con_requisito(ruta.dependant, [])
            ]
    return mapa


def test_la_tabla_tiene_las_38_rutas():
    assert len(ESPERADO) == 38


def test_cada_endpoint_exige_la_pantalla_y_el_nivel_de_la_tabla():
    real = _mapa_real()

    sin_fila = sorted(set(real) - set(ESPERADO))
    sin_ruta = sorted(set(ESPERADO) - set(real))
    assert not sin_fila, f"rutas sin fila en la tabla: {sin_fila}"
    assert not sin_ruta, f"filas de la tabla sin ruta: {sin_ruta}"

    distintas = {
        clave: real[clave]
        for clave, esperado in ESPERADO.items()
        if real[clave] != [esperado]
    }
    assert not distintas, (
        f"{len(distintas)} de {len(ESPERADO)} rutas no exigen exactamente lo de la tabla: "
        f"{sorted(distintas.items())}"
    )
