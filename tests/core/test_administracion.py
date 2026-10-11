"""API de Administración: solo admin, alta desde el padrón, roles, reset y
protecciones (PR 5 etapa 0). El alta asigna roles armables (ADR-0020); el
esquema anterior por módulo ya no está en la API."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import invalidar_cache_usuarios, pwd_context
from app.core.database import Base, get_db_propia, get_db_sueldos
from app.core.identidad import email_de_cuil
from app.core.models import Rol, RolPermiso, Usuario, UsuarioRol
from app.main import app
from tests.roles_de_prueba import SEMILLA

CUIL_A = "20111111119"
CUIL_B = "27222222224"

PADRON = {
    "personas": [
        {"cuil": CUIL_A, "apellido_nombre": "GOMEZ, JUAN",
         "empleos": [{"empresa": "LA ASTURIANA", "legajo": "4314"}]},
        {"cuil": CUIL_B, "apellido_nombre": "PEREZ, ANA",
         "empleos": [{"empresa": "LA ASTURIANA", "legajo": "5000"}]},
    ],
    "total": 2,
}


def _rol_de_semilla(nombre):
    """Rol real con los permisos que le da la migración core/002."""
    return Rol(nombre=nombre, permisos=[
        RolPermiso(modulo=m, pantalla=p, nivel=n) for r, m, p, n in SEMILLA if r == nombre
    ])


class PadronFalso:
    """Reemplaza a SueldosService en los tests: no toca la base de sueldos."""
    def __init__(self, db_sueldos=None):
        pass

    def buscar_personas(self, texto, limite=50):
        t = (texto or "").lower()
        personas = [p for p in PADRON["personas"]
                    if t in p["apellido_nombre"].lower() or p["cuil"].startswith(t)]
        return {"personas": personas[:limite], "total": len(personas)}


@pytest.fixture()
def db(monkeypatch):
    import app.core.administracion as admin_mod
    monkeypatch.setattr(admin_mod, "SueldosService", PadronFalso)

    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    s = sessionmaker(bind=engine)()
    adm = Usuario(nombre="Adm", email="adm@t.com", password=pwd_context.hash("x"), rol="admin", activo=True)
    op = Usuario(nombre="Op", email="op@t.com", password=pwd_context.hash("x"), rol="usuario", activo=True)
    op.roles.append(_rol_de_semilla("Preliquidador"))
    s.add_all([adm, op, _rol_de_semilla("Liquidador de terceros")]); s.commit()

    app.dependency_overrides[get_db_propia] = lambda: s
    app.dependency_overrides[get_db_sueldos] = lambda: None
    yield s
    app.dependency_overrides.clear(); s.close()
    # Los ids de esta base en memoria arrancan de nuevo en 1 en cada test:
    # sin esto, el cache de proceso de get_usuario_actual (60s de TTL) puede
    # devolverle a otro archivo de test un Usuario de esta base ya cerrada.
    invalidar_cache_usuarios()


def _rol_id(db, nombre):
    return db.query(Rol).filter(Rol.nombre == nombre).one().id


def _roles_en_la_base(db, email):
    db.expire_all()
    u = db.query(Usuario).filter(Usuario.email == email).one()
    return sorted(r.nombre for r in db.query(Rol).join(UsuarioRol, UsuarioRol.rol_id == Rol.id)
                  .filter(UsuarioRol.usuario_id == u.id))


def _token(c, email):
    r = c.post("/api/auth/login", data={"username": email, "password": "x"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_un_no_admin_recibe_403_en_todos_los_endpoints(db):
    c = TestClient(app)
    h = _token(c, "op@t.com")
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    llamadas = [
        c.get("/api/admin/usuarios", headers=h),
        c.get("/api/admin/padron", params={"q": "gomez"}, headers=h),
        c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "roles": []}, headers=h),
        c.patch(f"/api/admin/usuarios/{op_id}", json={"nombre": "X"}, headers=h),
        c.put(f"/api/admin/usuarios/{op_id}/roles", json={"roles": []}, headers=h),
        c.post(f"/api/admin/usuarios/{op_id}/password", json={}, headers=h),
    ]
    assert [r.status_code for r in llamadas] == [403] * 6


def test_la_ruta_de_modulos_ya_no_existe(db):
    """El esquema por módulo salió de la API (ADR-0020): los roles de una
    persona se cambian con PUT /usuarios/{id}/roles."""
    c = TestClient(app)
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    r = c.put(f"/api/admin/usuarios/{op_id}/modulos",
              json={"modulos": {"terceros": "operador"}},
              headers=_token(c, "adm@t.com"))
    assert r.status_code == 404


def test_lista_usuarios_con_sus_roles(db):
    c = TestClient(app)
    r = c.get("/api/admin/usuarios", headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    por_email = {u["email"]: u for u in r.json()}
    assert por_email["op@t.com"]["roles"] == [
        {"id": _rol_id(db, "Preliquidador"), "nombre": "Preliquidador"}]
    assert por_email["adm@t.com"]["roles"] == []
    assert all("modulos" not in u for u in r.json())
    assert por_email["adm@t.com"]["rol"] == "admin"
    assert por_email["adm@t.com"]["cuil"] is None      # mail real


def test_padron_marca_a_quien_ya_tiene_usuario(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "roles": []}, headers=h)

    r = c.get("/api/admin/padron", params={"q": "gomez"}, headers=h)
    assert r.status_code == 200
    persona = r.json()["personas"][0]
    assert persona["cuil"] == CUIL_A
    assert persona["ya_tiene_usuario"] is True


def test_alta_en_lote_crea_los_dos_con_los_mismos_roles(db):
    c = TestClient(app)
    roles = [_rol_id(db, "Liquidador de terceros"), _rol_id(db, "Preliquidador")]
    r = c.post("/api/admin/usuarios",
               json={"cuils": [CUIL_A, CUIL_B], "rol_global": "usuario", "roles": roles},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200, r.text
    assert len(r.json()["creados"]) == 2
    assert r.json()["omitidos"] == []
    for cuil in (CUIL_A, CUIL_B):
        assert _roles_en_la_base(db, email_de_cuil(cuil)) == ["Liquidador de terceros", "Preliquidador"]


def test_alta_sin_roles_crea_a_la_persona_sin_roles(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario"},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200, r.text
    assert len(r.json()["creados"]) == 1
    assert _roles_en_la_base(db, email_de_cuil(CUIL_A)) == []


def test_alta_con_un_rol_inexistente_responde_400_sin_crear_a_nadie(db):
    """Mismo criterio y texto que PUT /usuarios/{id}/roles."""
    c = TestClient(app)
    r = c.post("/api/admin/usuarios",
               json={"cuils": [CUIL_A, CUIL_B], "rol_global": "usuario",
                     "roles": [_rol_id(db, "Preliquidador"), 999]},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 400
    assert r.json()["detail"] == "No existe el rol con id 999."
    db.expire_all()
    emails = [email_de_cuil(CUIL_A), email_de_cuil(CUIL_B)]
    assert db.query(Usuario).filter(Usuario.email.in_(emails)).count() == 0


def test_alta_rechaza_rol_global_inexistente(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "rey", "roles": []},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 400


def test_alta_omite_a_quien_no_esta_en_el_padron(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios",
               json={"cuils": ["20999999997"], "rol_global": "usuario", "roles": []},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    assert r.json()["creados"] == []
    assert r.json()["omitidos"] == [{"cuil": "20999999997", "motivo": "no está en el padrón"}]


def test_desactivar_a_otro_y_que_no_pueda_loguearse(db):
    c = TestClient(app)
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    r = c.patch(f"/api/admin/usuarios/{op_id}", json={"activo": False},
                headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    assert r.json()["activo"] is False
    assert c.post("/api/auth/login", data={"username": "op@t.com", "password": "x"}).status_code == 401


def test_las_protecciones_de_admin_devuelven_400(db):
    """Las dos que puede disparar el propio admin desde la pantalla. La tercera
    (nunca cero admins activos) se prueba en test_usuarios_service.py, donde se
    puede armar el caso de dos admins."""
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    adm_id = db.query(Usuario).filter(Usuario.email == "adm@t.com").one().id
    assert c.patch(f"/api/admin/usuarios/{adm_id}", json={"activo": False}, headers=h).status_code == 400
    assert c.patch(f"/api/admin/usuarios/{adm_id}", json={"rol": "usuario"}, headers=h).status_code == 400


def test_reset_de_password_devuelve_el_cuil(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "roles": []}, headers=h)
    nuevo_id = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one().id

    r = c.post(f"/api/admin/usuarios/{nuevo_id}/password", json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["password"] == CUIL_A
    assert c.post("/api/auth/login", data={"username": email_de_cuil(CUIL_A), "password": CUIL_A}).status_code == 200


def test_usuario_inexistente_da_404(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    assert c.patch("/api/admin/usuarios/9999", json={"nombre": "X"}, headers=h).status_code == 404
