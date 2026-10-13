"""Mapa de permisos de Facturación (ADR-0020): qué pantalla y qué nivel exige
cada endpoint de `/api/facturacion`.

`ESPERADO` copia la tabla de la sección 3.2 del plan de la E2
(`docs/superpowers/plans/2026-10-11-facturacion-e2.md`): las filas 1 a 5
(Comprobantes), 6 a 8 (adjuntos), 9 a 11 (clientes, fincas y empresas) y
`GET /tareas`, todas de la pantalla `comprobantes`. Las dos
rutas de la E1 (`/tareas`, pantalla `unidad`) salieron el 2026-10-12 con su
pantalla (`docs/superpowers/plans/2026-10-12-unidad-desde-campo.md`); la E2
vuelve a crear `GET /tareas`, ahora en `comprobantes`. El mapa real se lee
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


F = PREFIJO

VER_COMPROBANTES = _exige("ver", "comprobantes")
EDITAR_COMPROBANTES = _exige("editar", "comprobantes")

# Los números son los de la tabla 3.2 del plan de la E2.
ESPERADO = {
    # 1 y 2
    ("GET", f"{F}/comprobantes"): VER_COMPROBANTES,
    ("GET", f"{F}/comprobantes/{{comprobante_id}}"): VER_COMPROBANTES,
    # 3 a 5
    ("POST", f"{F}/comprobantes"): EDITAR_COMPROBANTES,
    ("PUT", f"{F}/comprobantes/{{comprobante_id}}"): EDITAR_COMPROBANTES,
    ("DELETE", f"{F}/comprobantes/{{comprobante_id}}"): EDITAR_COMPROBANTES,
    # 6 a 8: los adjuntos. Abrir es de quien ve; subir y quitar, de quien edita.
    ("POST", f"{F}/comprobantes/{{comprobante_id}}/adjuntos"): EDITAR_COMPROBANTES,
    ("GET", f"{F}/comprobantes/{{comprobante_id}}/adjuntos/{{adjunto_id}}"): VER_COMPROBANTES,
    ("DELETE", f"{F}/comprobantes/{{comprobante_id}}/adjuntos/{{adjunto_id}}"): EDITAR_COMPROBANTES,
    # 9 a 11: las lecturas del campo y de sueldos que usa el alta.
    ("GET", f"{F}/clientes"): VER_COMPROBANTES,
    ("GET", f"{F}/clientes/{{cliente_id}}/fincas"): VER_COMPROBANTES,
    ("GET", f"{F}/empresas"): VER_COMPROBANTES,
    # Las tareas del campo, con su Unidad sugerida (la crea la E2, paso A6).
    ("GET", f"{F}/tareas"): VER_COMPROBANTES,
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


def test_la_tabla_tiene_las_12_rutas():
    assert len(ESPERADO) == 12


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
