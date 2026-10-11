"""Red de seguridad de permisos (ADR-0020, paso 2.3 del plan
`docs/superpowers/plans/2026-10-09-esquema-permisos.md`).

Toda ruta `/api/*` exige exactamente un requisito: una pantalla con su nivel
(`requiere_pantalla`) o ser admin (`requiere_admin`). Las únicas que no lo
exigen son las de `LISTA_BLANCA`: piden sólo sesión o nada, y no entregan datos
de un módulo. Un endpoint nuevo sin permiso hace fallar este test, aunque su
módulo no tenga test de mapa.

Además, cada requisito nombra un módulo activo y pantallas de su catálogo, y
Editar sólo se pide en pantallas editables (las de sólo Ver no lo pueden dar).
"""
from fastapi.routing import APIRoute

from app.main import app

LISTA_BLANCA = {
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/me"),
    ("POST", "/api/auth/password"),
    ("GET", "/api/auth/modulos"),
    ("POST", "/api/asistente/chat"),
    ("GET", "/api/preliquidacion/generar/status"),  # app/main.py, sin sesión
}


def _dependencias_con_requisito(dependant, vistas):
    """Las dependencias con `.requisito` de toda la cadena, sin repetir el mismo
    objeto (FastAPI la ejecuta una sola vez aunque aparezca dos veces)."""
    for dep in dependant.dependencies:
        if hasattr(dep.call, "requisito") and not any(dep.call is v for v in vistas):
            vistas.append(dep.call)
        _dependencias_con_requisito(dep, vistas)
    return vistas


def _requisitos_por_ruta():
    """{(método, ruta): [requisito, ...]} de todas las rutas `/api/*`."""
    mapa = {}
    for ruta in app.routes:
        if not isinstance(ruta, APIRoute) or not ruta.path.startswith("/api/"):
            continue
        for metodo in ruta.methods:
            clave = (metodo, ruta.path)
            assert clave not in mapa, f"ruta repetida: {clave}"
            mapa[clave] = [d.requisito for d in _dependencias_con_requisito(ruta.dependant, [])]
    return mapa


def test_la_lista_blanca_existe_y_no_pide_permiso():
    mapa = _requisitos_por_ruta()
    sin_ruta = sorted(LISTA_BLANCA - set(mapa))
    assert not sin_ruta, f"rutas de la lista blanca que ya no existen: {sin_ruta}"
    con_permiso = sorted(clave for clave in LISTA_BLANCA if mapa[clave])
    assert not con_permiso, (
        f"rutas de la lista blanca que ahora piden permiso (sacarlas de la lista): {con_permiso}"
    )


def test_toda_ruta_api_fuera_de_la_lista_blanca_exige_un_requisito():
    mapa = _requisitos_por_ruta()
    sin_requisito = sorted(c for c, reqs in mapa.items() if c not in LISTA_BLANCA and not reqs)
    con_varios = sorted((c, reqs) for c, reqs in mapa.items() if len(reqs) > 1)
    assert not sin_requisito, f"rutas /api/* sin permiso de pantalla ni de admin: {sin_requisito}"
    assert not con_varios, f"rutas /api/* con más de un requisito: {con_varios}"


def test_cada_requisito_nombra_pantallas_del_catalogo():
    catalogo = {m.clave: {p.clave: p for p in m.pantallas} for m in app.state.modulos}
    errores = []
    for clave, reqs in sorted(_requisitos_por_ruta().items()):
        for req in reqs:
            if req == "admin":
                continue
            modulo, pantallas, nivel = req
            if modulo not in catalogo:
                errores.append((clave, f"módulo {modulo!r} no está entre los activos"))
                continue
            for pantalla in pantallas:
                info = catalogo[modulo].get(pantalla)
                if info is None:
                    errores.append((clave, f"pantalla {modulo}/{pantalla} no está en el catálogo"))
                elif nivel == "editar" and not info.editable:
                    errores.append((clave, f"pide Editar en {modulo}/{pantalla}, que es sólo Ver"))
    assert not errores, f"requisitos fuera del catálogo: {errores}"
