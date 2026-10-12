"""Mapa de permisos de Facturación (ADR-0020): qué pantalla y qué nivel exige
cada endpoint de `/api/facturacion`.

`ESPERADO` copia las dos rutas del contrato 2.5 del plan de la E1
(`docs/superpowers/plans/2026-10-11-facturacion-e1.md`). El mapa real se lee
de `app.routes`: cada dependencia de `requiere_pantalla` expone `.requisito`.
Una ruta nueva sin su fila, una fila sin ruta o un permiso distinto del de la
tabla hacen fallar el test.
"""
from fastapi.routing import APIRoute

from app.main import app

PREFIJO = "/api/facturacion"

M = "facturacion"


def _exige(nivel, *pantallas):
    # Alcanza con una de las pantallas: el orden no importa.
    return (M, frozenset(pantallas), nivel)


VER_UNIDAD = _exige("ver", "unidad")
EDITAR_UNIDAD = _exige("editar", "unidad")

F = PREFIJO

ESPERADO = {
    ("GET", f"{F}/tareas"): VER_UNIDAD,
    ("PATCH", f"{F}/tareas/{{tarea_id}}"): EDITAR_UNIDAD,
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


def test_la_tabla_tiene_las_2_rutas():
    assert len(ESPERADO) == 2


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
