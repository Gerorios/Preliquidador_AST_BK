"""API de roles de Administración (ADR-0020): alta, cambio y borrado de roles,
roles de cada persona, y que un cambio valga en el pedido siguiente.

Con login real, como `test_administracion.py`. El catálogo es el de los
módulos activos que `app/main.py` deja en `app.state.modulos`. Los textos de los
rechazos son los de `app/core/roles_service.py` (los mismos del editor del
front).
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core import roles_service
from app.core.auth import invalidar_cache_usuarios, pwd_context
from app.core.database import Base, get_db_propia
from app.core.models import Rol, RolPermiso, Usuario, UsuarioModulo, UsuarioRol
from app.main import app

CONCEPTOS_VER = {"preliquidacion": {"conceptos": "ver"}}


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    adm = Usuario(nombre="Adm", email="adm@t.com", password=pwd_context.hash("x"), rol="admin", activo=True)
    ana = Usuario(nombre="Ana", email="ana@t.com", password=pwd_context.hash("x"), rol="usuario", activo=True)
    beto = Usuario(nombre="Beto", email="beto@t.com", password=pwd_context.hash("x"), rol="usuario", activo=False)
    ana.modulos.append(UsuarioModulo(modulo="preliquidacion", rol="operador"))
    s.add_all([adm, ana, beto]); s.commit()

    app.dependency_overrides[get_db_propia] = lambda: s
    yield s
    app.dependency_overrides.clear(); s.close()
    # Los ids de esta base en memoria arrancan de nuevo en 1 en cada test: sin
    # esto, el cache de proceso de get_usuario_actual le puede devolver a otro
    # test un Usuario de esta base ya cerrada.
    invalidar_cache_usuarios()


def _token(c, email):
    r = c.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _id(db, email):
    return db.query(Usuario).filter(Usuario.email == email).one().id


def _crear(c, h, nombre, permisos):
    r = c.post("/api/admin/roles", json={"nombre": nombre, "permisos": permisos}, headers=h)
    assert r.status_code == 201, r.text
    return r.json()


def _permisos_en_la_base(db, rol_id) -> dict:
    db.expire_all()
    salida: dict = {}
    for p in db.query(RolPermiso).filter(RolPermiso.rol_id == rol_id).all():
        salida.setdefault(p.modulo, {})[p.pantalla] = p.nivel
    return salida


# ─── Sólo admin ───────────────────────────────────────────────────────────────

def test_un_no_admin_recibe_403_en_los_endpoints_de_roles(db):
    c = TestClient(app)
    h_adm = _token(c, "adm@t.com")
    rol = _crear(c, h_adm, "Gerente", CONCEPTOS_VER)
    h = _token(c, "ana@t.com")
    ana_id = _id(db, "ana@t.com")
    llamadas = [
        c.get("/api/admin/roles", headers=h),
        c.post("/api/admin/roles", json={"nombre": "Otro", "permisos": CONCEPTOS_VER}, headers=h),
        c.put(f"/api/admin/roles/{rol['id']}", json={"nombre": "X", "permisos": CONCEPTOS_VER}, headers=h),
        c.delete(f"/api/admin/roles/{rol['id']}", headers=h),
        c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": [rol["id"]]}, headers=h),
    ]
    assert [r.status_code for r in llamadas] == [403] * 5
    # Nada cambió.
    db.expire_all()
    assert [r.nombre for r in db.query(Rol).all()] == ["Gerente"]
    assert db.query(UsuarioRol).count() == 0


# ─── Alta, cambio y borrado ───────────────────────────────────────────────────

def test_alta_de_rol_responde_201_con_el_rol(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    permisos = {"preliquidacion": {"inicio": "ver", "revision": "editar", "gerencial": "ver"}}
    r = c.post("/api/admin/roles", json={"nombre": "  Supervisor  ", "permisos": permisos}, headers=h)
    assert r.status_code == 201, r.text
    rol = r.json()
    assert rol["nombre"] == "Supervisor"
    assert rol["permisos"] == permisos
    assert rol["personas"] == []
    assert _permisos_en_la_base(db, rol["id"]) == permisos

    lista = c.get("/api/admin/roles", headers=h)
    assert lista.status_code == 200
    assert lista.json() == [rol]


def test_lista_de_roles_con_sus_personas(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    rol = _crear(c, h, "Gerente", CONCEPTOS_VER)
    otro = _crear(c, h, "Auditor", {"preliquidacion": {"verificacion": "ver"}})
    for email in ("ana@t.com", "beto@t.com"):
        r = c.put(f"/api/admin/usuarios/{_id(db, email)}/roles", json={"roles": [rol["id"]]}, headers=h)
        assert r.status_code == 200, r.text

    r = c.get("/api/admin/roles", headers=h)
    assert r.status_code == 200
    por_nombre = {x["nombre"]: x for x in r.json()}
    assert por_nombre["Gerente"]["personas"] == [
        {"id": _id(db, "ana@t.com"), "nombre": "Ana", "activo": True},
        {"id": _id(db, "beto@t.com"), "nombre": "Beto", "activo": False},
    ]
    assert por_nombre["Auditor"] == {**otro, "personas": []}


def test_cambio_de_rol(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    rol = _crear(c, h, "Gerente", CONCEPTOS_VER)
    nuevos = {"preliquidacion": {"conceptos": "editar", "gerencial": "ver"}}
    r = c.put(f"/api/admin/roles/{rol['id']}", json={"nombre": "Gerencia", "permisos": nuevos}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json() == {"id": rol["id"], "nombre": "Gerencia", "permisos": nuevos, "personas": []}
    assert _permisos_en_la_base(db, rol["id"]) == nuevos


def test_el_put_reemplaza_todos_los_modulos_activos_aunque_no_vengan(db):
    # El editor manda sólo los módulos con alguna pantalla: un módulo activo que
    # no viene se queda sin permisos (plan, sección 9, paso 3.8).
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    rol = _crear(c, h, "Mixto", {**CONCEPTOS_VER, "terceros": {"inicio": "editar"}})
    r = c.put(f"/api/admin/roles/{rol['id']}", json={"nombre": "Mixto", "permisos": CONCEPTOS_VER}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["permisos"] == CONCEPTOS_VER
    assert _permisos_en_la_base(db, rol["id"]) == CONCEPTOS_VER


def test_el_put_conserva_los_permisos_de_un_modulo_fuera_del_catalogo(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    rol = _crear(c, h, "Contadora", CONCEPTOS_VER)
    # Un módulo que no está activo (no está en el catálogo): el editor no lo
    # muestra, así que no lo manda.
    db.add(RolPermiso(rol_id=rol["id"], modulo="facturacion", pantalla="emision", nivel="editar"))
    db.commit()

    r = c.put(f"/api/admin/roles/{rol['id']}",
              json={"nombre": "Contadora", "permisos": {"preliquidacion": {"conceptos": "editar"}}},
              headers=h)
    assert r.status_code == 200, r.text
    esperado = {"preliquidacion": {"conceptos": "editar"}, "facturacion": {"emision": "editar"}}
    assert r.json()["permisos"] == esperado
    assert _permisos_en_la_base(db, rol["id"]) == esperado


def test_borrar_rol_sin_personas(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    rol = _crear(c, h, "Gerente", CONCEPTOS_VER)
    r = c.delete(f"/api/admin/roles/{rol['id']}", headers=h)
    assert r.status_code == 204, r.text
    assert c.get("/api/admin/roles", headers=h).json() == []
    db.expire_all()
    assert db.query(Rol).count() == 0
    assert db.query(RolPermiso).count() == 0


def test_rol_inexistente_responde_404(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    r1 = c.put("/api/admin/roles/999", json={"nombre": "X", "permisos": CONCEPTOS_VER}, headers=h)
    r2 = c.delete("/api/admin/roles/999", headers=h)
    # El 404 es del endpoint (no de una ruta que no existe): dice qué falta.
    assert [(r1.status_code, r1.json()["detail"]), (r2.status_code, r2.json()["detail"])] == [
        (404, "El rol no existe"), (404, "El rol no existe")]


# ─── Conflictos (409) y validaciones (400) ────────────────────────────────────

def test_nombre_repetido_responde_409(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    _crear(c, h, "Gerente", CONCEPTOS_VER)
    otro = _crear(c, h, "Auditor", CONCEPTOS_VER)

    alta = c.post("/api/admin/roles", json={"nombre": "Gérente", "permisos": CONCEPTOS_VER}, headers=h)
    assert alta.status_code == 409
    assert alta.json()["detail"] == 'Ya hay un rol que se llama "Gerente".'

    cambio = c.put(f"/api/admin/roles/{otro['id']}", json={"nombre": "gerente", "permisos": CONCEPTOS_VER},
                   headers=h)
    assert cambio.status_code == 409
    assert cambio.json()["detail"] == 'Ya hay un rol que se llama "Gerente".'
    db.expire_all()
    assert sorted(r.nombre for r in db.query(Rol).all()) == ["Auditor", "Gerente"]


def test_nombre_que_choca_con_la_unique_responde_409_y_no_500(db, monkeypatch):
    # Doble clic en "Crear rol": los dos pedidos pasan la consulta previa y el
    # segundo choca con uq_rol_nombre en el commit. Se simula salteándola.
    c = TestClient(app, raise_server_exceptions=False)
    h = _token(c, "adm@t.com")
    _crear(c, h, "Gerente", CONCEPTOS_VER)
    otro = _crear(c, h, "Auditor", CONCEPTOS_VER)
    monkeypatch.setattr(roles_service, "rol_con_el_nombre", lambda *a, **k: None)

    alta = c.post("/api/admin/roles", json={"nombre": "Gerente", "permisos": CONCEPTOS_VER}, headers=h)
    cambio = c.put(f"/api/admin/roles/{otro['id']}", json={"nombre": "Gerente", "permisos": CONCEPTOS_VER},
                   headers=h)
    assert [alta.status_code, cambio.status_code] == [409, 409]
    assert alta.json()["detail"] == cambio.json()["detail"] == 'Ya hay un rol que se llama "Gerente".'
    db.expire_all()
    assert sorted(r.nombre for r in db.query(Rol).all()) == ["Auditor", "Gerente"]


def test_borrar_un_rol_en_uso_responde_409(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    rol = _crear(c, h, "Gerente", CONCEPTOS_VER)
    for email in ("ana@t.com", "beto@t.com"):
        c.put(f"/api/admin/usuarios/{_id(db, email)}/roles", json={"roles": [rol["id"]]}, headers=h)

    r = c.delete(f"/api/admin/roles/{rol['id']}", headers=h)
    assert r.status_code == 409
    assert r.json()["detail"] == (
        "Lo tienen 2 personas: Ana y Beto (inactiva). Sacáselo primero para poder borrarlo."
    )
    db.expire_all()
    assert db.query(Rol).count() == 1


@pytest.mark.parametrize("nombre, permisos, motivo", [
    ("   ", CONCEPTOS_VER, "El rol necesita un nombre."),
    ("X" * 61, CONCEPTOS_VER, "El nombre puede tener hasta 60 caracteres."),
    ("Vacío", {}, "El rol tiene que dar acceso al menos a una pantalla."),
    ("Vacío", {"preliquidacion": {"conceptos": None}}, "El rol tiene que dar acceso al menos a una pantalla."),
    ("Raro", {"facturacion": {"emision": "ver"}}, 'El módulo "facturacion" no existe o no está activo.'),
    ("Raro", {"preliquidacion": {"caja": "ver"}}, 'Preliquidación no tiene la pantalla "caja".'),
    ("Raro", {"preliquidacion": {"conceptos": "borrar"}}, 'Conceptos tiene un nivel desconocido: "borrar".'),
    ("Raro", {"preliquidacion": {"gerencial": "editar"}}, "Vista gerencial sólo admite Ver."),
    ("Raro", {"preliquidacion": {"revision": "editar"}}, "Revisión necesita al menos Ver en Inicio."),
])
def test_validaciones_responden_400(db, nombre, permisos, motivo):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    alta = c.post("/api/admin/roles", json={"nombre": nombre, "permisos": permisos}, headers=h)
    assert alta.status_code == 400
    assert alta.json()["detail"] == motivo

    rol = _crear(c, h, "Gerente", CONCEPTOS_VER)
    cambio = c.put(f"/api/admin/roles/{rol['id']}", json={"nombre": nombre, "permisos": permisos}, headers=h)
    assert cambio.status_code == 400
    assert cambio.json()["detail"] == motivo
    # El rechazo no cambió nada.
    db.expire_all()
    assert [r.nombre for r in db.query(Rol).all()] == ["Gerente"]
    assert _permisos_en_la_base(db, rol["id"]) == CONCEPTOS_VER


# ─── Roles de cada persona ────────────────────────────────────────────────────

def test_put_roles_de_una_persona(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    gerente = _crear(c, h, "Gerente", CONCEPTOS_VER)
    auditor = _crear(c, h, "Auditor", {"preliquidacion": {"verificacion": "ver"}})
    ana_id = _id(db, "ana@t.com")

    r = c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": [gerente["id"], auditor["id"]]}, headers=h)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    assert cuerpo["id"] == ana_id
    assert sorted(x["nombre"] for x in cuerpo["roles"]) == ["Auditor", "Gerente"]
    assert cuerpo["modulos"] == {"preliquidacion": "operador"}  # BK1 es aditivo
    db.expire_all()
    assert {fila.rol_id for fila in db.query(UsuarioRol).filter(UsuarioRol.usuario_id == ana_id)} == {
        gerente["id"], auditor["id"]}

    # Reemplaza la lista completa: sacarle uno es mandar la lista sin ese id.
    r = c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": [auditor["id"]]}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["roles"] == [{"id": auditor["id"], "nombre": "Auditor"}]
    r = c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": []}, headers=h)
    assert r.status_code == 200, r.text
    assert r.json()["roles"] == []


def test_put_roles_con_un_id_inexistente_responde_400_sin_cambiar_nada(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    gerente = _crear(c, h, "Gerente", CONCEPTOS_VER)
    ana_id = _id(db, "ana@t.com")
    c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": [gerente["id"]]}, headers=h)

    r = c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": [999]}, headers=h)
    assert r.status_code == 400
    assert r.json()["detail"] == "No existe el rol con id 999."
    db.expire_all()
    assert [fila.rol_id for fila in db.query(UsuarioRol).filter(UsuarioRol.usuario_id == ana_id)] == [
        gerente["id"]]


def test_put_roles_de_una_persona_inexistente_responde_404(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    r = c.put("/api/admin/usuarios/999/roles", json={"roles": []}, headers=h)
    assert r.status_code == 404
    assert r.json()["detail"] == "El usuario no existe"


def test_la_lista_de_usuarios_suma_los_roles_sin_sacar_los_modulos(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    gerente = _crear(c, h, "Gerente", CONCEPTOS_VER)
    c.put(f"/api/admin/usuarios/{_id(db, 'ana@t.com')}/roles", json={"roles": [gerente["id"]]}, headers=h)

    r = c.get("/api/admin/usuarios", headers=h)
    assert r.status_code == 200
    por_email = {u["email"]: u for u in r.json()}
    assert por_email["ana@t.com"]["roles"] == [{"id": gerente["id"], "nombre": "Gerente"}]
    assert por_email["ana@t.com"]["modulos"] == {"preliquidacion": "operador"}
    assert por_email["adm@t.com"]["roles"] == []


# ─── Vale enseguida ───────────────────────────────────────────────────────────

def test_el_cambio_de_rol_vale_enseguida(db):
    c = TestClient(app)
    h_adm = _token(c, "adm@t.com")
    rol = _crear(c, h_adm, "Gerente", CONCEPTOS_VER)
    c.put(f"/api/admin/usuarios/{_id(db, 'ana@t.com')}/roles", json={"roles": [rol["id"]]}, headers=h_adm)

    h_ana = _token(c, "ana@t.com")
    antes = c.get("/api/auth/me", headers=h_ana)
    assert antes.status_code == 200, antes.text
    assert antes.json()["permisos"] == CONCEPTOS_VER   # ya quedó en el cache de la persona

    nuevos = {"preliquidacion": {"conceptos": "editar", "gerencial": "ver"}}
    r = c.put(f"/api/admin/roles/{rol['id']}", json={"nombre": "Gerente", "permisos": nuevos}, headers=h_adm)
    assert r.status_code == 200, r.text

    despues = c.get("/api/auth/me", headers=h_ana)
    assert despues.status_code == 200, despues.text
    assert despues.json()["permisos"] == nuevos


def test_el_cambio_de_roles_de_una_persona_vale_enseguida(db):
    c = TestClient(app)
    h_adm = _token(c, "adm@t.com")
    rol = _crear(c, h_adm, "Gerente", CONCEPTOS_VER)
    ana_id = _id(db, "ana@t.com")

    h_ana = _token(c, "ana@t.com")
    assert c.get("/api/auth/me", headers=h_ana).json()["permisos"] == {}

    r = c.put(f"/api/admin/usuarios/{ana_id}/roles", json={"roles": [rol["id"]]}, headers=h_adm)
    assert r.status_code == 200, r.text
    assert c.get("/api/auth/me", headers=h_ana).json()["permisos"] == CONCEPTOS_VER
