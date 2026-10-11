"""Mapa de permisos de Preliquidación (ADR-0020): qué pantalla y qué nivel exige
cada endpoint de `/api/preliquidacion`, `/api/precios` y `/api/gerencial`.

`ESPERADO` copia las filas 1 a 21 de la tabla 2.4 del plan
(`docs/superpowers/plans/2026-10-09-esquema-permisos.md`). El mapa real se lee
de `app.routes`: cada dependencia de `requiere_pantalla` expone `.requisito`.
Una ruta nueva sin su fila, una fila sin ruta o un permiso distinto del de la
tabla hacen fallar el test.

`GET /api/preliquidacion/generar/status` queda afuera: vive en `app/main.py`,
no pide sesión y no entrega datos.
"""
from fastapi.routing import APIRoute

from app.main import app

PREFIJOS = ("/api/preliquidacion", "/api/precios", "/api/gerencial")
FUERA = {("GET", "/api/preliquidacion/generar/status")}

M = "preliquidacion"


def _exige(nivel, *pantallas):
    # Alcanza con una de las pantallas: el orden no importa.
    return (M, frozenset(pantallas), nivel)


EDITAR_INICIO = _exige("editar", "inicio")
VER_QUINCENAS = _exige("ver", "inicio", "revision", "verificacion", "mantenimiento")
VER_REVISION = _exige("ver", "revision")
VER_LINEAS = _exige("ver", "revision", "verificacion")
EDITAR_REVISION = _exige("editar", "revision")
VER_VERIFICACION = _exige("ver", "verificacion")
EDITAR_VERIFICACION = _exige("editar", "verificacion")
VER_MANTENIMIENTO = _exige("ver", "mantenimiento")
EDITAR_MANTENIMIENTO = _exige("editar", "mantenimiento")
VER_CONCEPTOS = _exige("ver", "conceptos")
VER_REVISION_O_CONCEPTOS = _exige("ver", "revision", "conceptos")
EDITAR_CONCEPTOS = _exige("editar", "conceptos")
VER_GERENCIAL_O_CONCEPTOS = _exige("ver", "gerencial", "conceptos")
VER_GERENCIAL = _exige("ver", "gerencial")

P = "/api/preliquidacion"
C = "/api/precios"
G = "/api/gerencial"

ESPERADO = {
    # 1-2
    ("POST", f"{P}/generar"): EDITAR_INICIO,
    ("POST", f"{P}/refrescar-sueldos"): EDITAR_INICIO,
    # 3
    ("GET", f"{P}/"): VER_QUINCENAS,
    # 4-5
    ("GET", f"{P}/empresas"): VER_REVISION,
    ("GET", f"{P}/{{preliq_id}}/estadisticas"): VER_REVISION,
    # 6
    ("GET", f"{P}/{{preliq_id}}/lineas"): VER_LINEAS,
    # 7
    ("GET", f"{P}/linea/{{linea_id}}/legajos-disponibles"): VER_REVISION,
    ("POST", f"{P}/lineas/legajos-por-cuil"): VER_REVISION,
    # 8
    ("GET", f"{P}/{{preliq_id}}/export-excel"): VER_REVISION,
    # 9
    ("PATCH", f"{P}/linea/{{linea_id}}"): EDITAR_REVISION,
    ("POST", f"{P}/linea/{{linea_id}}/conceptos/por-codigo"): EDITAR_REVISION,
    ("DELETE", f"{P}/linea/concepto/{{concepto_id}}"): EDITAR_REVISION,
    ("POST", f"{P}/lineas/concepto-masivo"): EDITAR_REVISION,
    ("POST", f"{P}/lineas/concepto-masivo/eliminar"): EDITAR_REVISION,
    ("POST", f"{P}/lineas/reasignar-empresa"): EDITAR_REVISION,
    # 10
    ("POST", f"{P}/linea/{{linea_id}}/concepto"): EDITAR_REVISION,
    # 11
    ("GET", f"{P}/{{preliq_id}}/control-plantas-jornal"): VER_VERIFICACION,
    ("GET", f"{P}/{{preliq_id}}/control-tancadas-jornal"): VER_VERIFICACION,
    # 12
    ("GET", f"{P}/{{preliq_id}}/dashboard-verificacion"): VER_VERIFICACION,
    # 13
    ("PATCH", f"{P}/{{preliq_id}}/valor-hora-pulv"): EDITAR_VERIFICACION,
    ("PATCH", f"{P}/{{preliq_id}}/valor-hora-tractorista"): EDITAR_VERIFICACION,
    # 14
    ("GET", f"{P}/{{preliq_id}}/operarios-mantenimiento"): VER_MANTENIMIENTO,
    # 15
    ("PUT", f"{P}/{{preliq_id}}/categoria-operario"): EDITAR_MANTENIMIENTO,
    ("POST", f"{P}/{{preliq_id}}/categorias-operario/heredar"): EDITAR_MANTENIMIENTO,
    # 16
    ("GET", f"{C}/maestro/clientes"): VER_CONCEPTOS,
    ("GET", f"{C}/maestro/fincas"): VER_CONCEPTOS,
    ("GET", f"{C}/maestro/tareas"): VER_CONCEPTOS,
    ("GET", f"{C}/conceptos"): VER_CONCEPTOS,
    ("GET", f"{C}/conceptos/quincenas"): VER_CONCEPTOS,
    ("GET", f"{C}/conceptos/supervisores"): VER_CONCEPTOS,
    ("GET", f"{C}/conceptos/panel"): VER_CONCEPTOS,
    ("GET", f"{C}/conceptos/solapamientos"): VER_CONCEPTOS,
    ("GET", f"{C}/conceptos/faltantes"): VER_CONCEPTOS,
    # 17
    ("GET", f"{C}/grupos-pago"): VER_CONCEPTOS,
    # 18
    ("GET", f"{C}/conceptos/buscar"): VER_REVISION_O_CONCEPTOS,
    # 19
    ("POST", f"{C}/conceptos"): EDITAR_CONCEPTOS,
    ("PATCH", f"{C}/conceptos/{{concepto_id}}"): EDITAR_CONCEPTOS,
    ("DELETE", f"{C}/conceptos/{{concepto_id}}"): EDITAR_CONCEPTOS,
    ("PATCH", f"{C}/conceptos/precio-masivo"): EDITAR_CONCEPTOS,
    ("POST", f"{C}/conceptos/copiar"): EDITAR_CONCEPTOS,
    # 20
    ("GET", f"{G}/quincenas"): VER_GERENCIAL_O_CONCEPTOS,
    # 21
    ("GET", f"{G}/empresas"): VER_GERENCIAL,
    ("GET", f"{G}/resumen"): VER_GERENCIAL,
    ("GET", f"{G}/evolucion"): VER_GERENCIAL,
    ("GET", f"{G}/por-cliente"): VER_GERENCIAL,
    ("GET", f"{G}/por-grupo-tarea"): VER_GERENCIAL,
    ("GET", f"{G}/desvios-persona"): VER_GERENCIAL,
    ("GET", f"{G}/indicadores"): VER_GERENCIAL,
    ("GET", f"{G}/desvios-cliente"): VER_GERENCIAL,
    ("GET", f"{G}/control-plantas"): VER_GERENCIAL,
    ("GET", f"{G}/control-tancadas"): VER_GERENCIAL,
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
        if not isinstance(ruta, APIRoute) or not ruta.path.startswith(PREFIJOS):
            continue
        for metodo in ruta.methods:
            clave = (metodo, ruta.path)
            if clave in FUERA:
                continue
            assert clave not in mapa, f"ruta repetida: {clave}"
            mapa[clave] = [
                _normalizar(d.requisito)
                for d in _dependencias_con_requisito(ruta.dependant, [])
            ]
    return mapa


def test_la_tabla_tiene_las_51_rutas():
    assert len(ESPERADO) == 51  # 24 de /api/preliquidacion + 16 de /api/precios + 11 de /api/gerencial


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
