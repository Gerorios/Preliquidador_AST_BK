"""La migración a roles no cambia el acceso de nadie, salvo los cambios a
propósito (ADR-0020, paso 2.3 y sección 2.4 del plan
`docs/superpowers/plans/2026-10-09-esquema-permisos.md`).

Para cada rol de `SEMILLA` (los que crea `core/002` y asigna desde
`usuario_modulo`), se calcula a qué endpoints de los módulos llega ahora,
corriendo las dependencias de permiso reales de cada ruta. Se compara con lo
que alcanzaba su par del esquema anterior.

La matriz "de hoy" (`HOY`) está escrita a mano desde los routers anteriores al
BK2 (`git show a801f1e^` y `c3a98d8^`), no derivada de los requisitos nuevos:
- `/api/preliquidacion` (`api/preliquidacion.py` y `api/export.py`): todo el
  router pedía `requiere_operativo` = operador de Preliquidación.
- `/api/precios` (`api/precios.py`): el router pedía sólo sesión; las cinco
  escrituras sumaban `requiere_conceptos` = operador o gerente de Preliquidación.
  Es decir, los GET los alcanzaba cualquier persona con sesión.
- `/api/gerencial` (`api/gerencial.py`): `requiere_gerencial` = gerente de
  Preliquidación.
- `/api/terceros` (`api/terceros.py`): `requiere_operativo` = operador de
  Terceros. `terceros`/`gerente` no pasaba ningún endpoint y no recibe rol.

Los únicos cambios aceptados (`GANA` y `PIERDE`) son los de la sección 2.4:
- Preliquidador suma `GET /api/gerencial/quincenas` (pregunta 4).
- Liquidador de terceros y quien no tiene roles pierden los 11 GET de
  `/api/precios`, que antes pasaban con sólo sesión.

`GET /api/preliquidacion/generar/status` queda afuera: no pide sesión, ni antes
ni ahora (lo cubre `test_endpoints_con_permiso.py`).
"""
import pytest
from fastapi import HTTPException
from fastapi.routing import APIRoute

from app.main import app
from tests.roles_de_prueba import SEMILLA, usuario_con

P = "/api/preliquidacion"
C = "/api/precios"
G = "/api/gerencial"
T = "/api/terceros"

FUERA = {("GET", f"{P}/generar/status")}


def _bajo(ruta, prefijo):
    return ruta == prefijo or ruta.startswith(prefijo + "/")


# Esquema anterior: qué endpoints alcanzaba cada par de `usuario_modulo`.
def _operador_preliquidacion(metodo, ruta):
    return _bajo(ruta, P) or _bajo(ruta, C)


def _gerente_preliquidacion(metodo, ruta):
    return _bajo(ruta, G) or _bajo(ruta, C)


def _operador_terceros(metodo, ruta):
    return _bajo(ruta, T) or (metodo == "GET" and _bajo(ruta, C))


def _sin_modulos(metodo, ruta):
    return metodo == "GET" and _bajo(ruta, C)


# Rol de la semilla (o persona sin roles) → par de usuario_modulo que lo
# origina en `core/002` (el CASE de la migración).
HOY = {
    "Preliquidador": _operador_preliquidacion,
    "Gerente": _gerente_preliquidacion,
    "Liquidador de terceros": _operador_terceros,
    None: _sin_modulos,
}

LOS_11_GET_DE_PRECIOS = {
    ("GET", f"{C}/maestro/clientes"),
    ("GET", f"{C}/maestro/fincas"),
    ("GET", f"{C}/maestro/tareas"),
    ("GET", f"{C}/conceptos"),
    ("GET", f"{C}/conceptos/quincenas"),
    ("GET", f"{C}/conceptos/supervisores"),
    ("GET", f"{C}/conceptos/panel"),
    ("GET", f"{C}/conceptos/solapamientos"),
    ("GET", f"{C}/conceptos/faltantes"),
    ("GET", f"{C}/grupos-pago"),
    ("GET", f"{C}/conceptos/buscar"),
}

GANA = {
    "Preliquidador": {("GET", f"{G}/quincenas")},
}

PIERDE = {
    "Liquidador de terceros": LOS_11_GET_DE_PRECIOS,
    None: LOS_11_GET_DE_PRECIOS,
}


def _dependencias_con_requisito(dependant, vistas):
    """Las dependencias con `.requisito` de toda la cadena, sin repetir el mismo
    objeto (FastAPI la ejecuta una sola vez aunque aparezca dos veces)."""
    for dep in dependant.dependencies:
        if hasattr(dep.call, "requisito") and not any(dep.call is v for v in vistas):
            vistas.append(dep.call)
        _dependencias_con_requisito(dep, vistas)
    return vistas


def _rutas_de_modulos():
    """{(método, ruta): [dependencia de permiso, ...]} bajo los cuatro prefijos."""
    rutas = {}
    for ruta in app.routes:
        if not isinstance(ruta, APIRoute) or not any(_bajo(ruta.path, p) for p in (P, C, G, T)):
            continue
        for metodo in ruta.methods:
            clave = (metodo, ruta.path)
            if clave not in FUERA:
                rutas[clave] = _dependencias_con_requisito(ruta.dependant, [])
    return rutas


def _llega(usuario, dependencias):
    """Corre las dependencias de permiso reales. Una ruta sin ninguna cuenta como
    abierta: así un endpoint que perdió su permiso aparece como acceso de más."""
    for dependencia in dependencias:
        try:
            dependencia(usuario=usuario)
        except HTTPException as exc:
            assert exc.status_code == 403
            return False
    return True


def _alcance_nuevo(usuario):
    return {clave for clave, deps in _rutas_de_modulos().items() if _llega(usuario, deps)}


def _alcance_de_hoy(rol):
    return {(m, r) for m, r in _rutas_de_modulos() if HOY[rol](m, r)}


def test_la_matriz_cubre_todos_los_roles_de_la_semilla():
    assert {r for r, *_ in SEMILLA} == {r for r in HOY if r is not None}


def test_los_cambios_aceptados_son_cambios_reales():
    # Lo que gana no lo tenía; lo que pierde sí lo tenía.
    for rol, gana in GANA.items():
        assert not gana & _alcance_de_hoy(rol), rol
    for rol, pierde in PIERDE.items():
        assert len(pierde) == 11
        assert pierde <= _alcance_de_hoy(rol), rol


@pytest.mark.parametrize("rol", list(HOY), ids=lambda r: r or "sin roles")
def test_el_rol_migrado_llega_a_lo_mismo_que_hoy(rol):
    usuario = usuario_con(rol) if rol else usuario_con()
    esperado = (_alcance_de_hoy(rol) | GANA.get(rol, set())) - PIERDE.get(rol, set())
    real = _alcance_nuevo(usuario)

    de_mas = sorted(real - esperado)
    de_menos = sorted(esperado - real)
    assert not de_mas and not de_menos, (
        f"{rol or 'sin roles'}: llega a {len(de_mas)} endpoints que hoy no "
        f"({de_mas}) y pierde {len(de_menos)} que hoy sí ({de_menos})"
    )
