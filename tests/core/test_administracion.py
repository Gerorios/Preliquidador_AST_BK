"""API de Administración: solo admin, alta desde el padrón, roles, reset y
protecciones (PR 5 etapa 0)."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import invalidar_cache_usuarios, pwd_context
from app.core.database import Base, get_db_propia, get_db_sueldos
from app.core.identidad import email_de_cuil
from app.core.models import Usuario, UsuarioModulo
from app.main import app

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
    op.modulos.append(UsuarioModulo(modulo="preliquidacion", rol="operador"))
    s.add_all([adm, op]); s.commit()

    app.dependency_overrides[get_db_propia] = lambda: s
    app.dependency_overrides[get_db_sueldos] = lambda: None
    yield s
    app.dependency_overrides.clear(); s.close()
    # Los ids de esta base en memoria arrancan de nuevo en 1 en cada test:
    # sin esto, el cache de proceso de get_usuario_actual (60s de TTL) puede
    # devolverle a otro archivo de test un Usuario de esta base ya cerrada.
    invalidar_cache_usuarios()


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
        c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "modulos": {}}, headers=h),
        c.patch(f"/api/admin/usuarios/{op_id}", json={"nombre": "X"}, headers=h),
        c.put(f"/api/admin/usuarios/{op_id}/modulos", json={"modulos": {}}, headers=h),
        c.post(f"/api/admin/usuarios/{op_id}/password", json={}, headers=h),
    ]
    assert [r.status_code for r in llamadas] == [403] * 6


def test_lista_usuarios_con_sus_modulos(db):
    c = TestClient(app)
    r = c.get("/api/admin/usuarios", headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    por_email = {u["email"]: u for u in r.json()}
    assert por_email["op@t.com"]["modulos"] == {"preliquidacion": "operador"}
    assert por_email["adm@t.com"]["rol"] == "admin"
    assert por_email["adm@t.com"]["cuil"] is None      # mail real


def test_padron_marca_a_quien_ya_tiene_usuario(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "modulos": {}}, headers=h)

    r = c.get("/api/admin/padron", params={"q": "gomez"}, headers=h)
    assert r.status_code == 200
    persona = r.json()["personas"][0]
    assert persona["cuil"] == CUIL_A
    assert persona["ya_tiene_usuario"] is True


def test_alta_en_lote_crea_los_dos_con_los_mismos_roles(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios",
               json={"cuils": [CUIL_A, CUIL_B], "rol_global": "usuario",
                     "modulos": {"fletes": "operador"}},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200, r.text
    assert len(r.json()["creados"]) == 2
    assert r.json()["omitidos"] == []
    for cuil in (CUIL_A, CUIL_B):
        u = db.query(Usuario).filter(Usuario.email == email_de_cuil(cuil)).one()
        assert {m.modulo: m.rol for m in u.modulos} == {"fletes": "operador"}


def test_alta_rechaza_modulo_o_rol_inexistente(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    r1 = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario",
                                             "modulos": {"inventado": "operador"}}, headers=h)
    r2 = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario",
                                             "modulos": {"fletes": "jefe"}}, headers=h)
    r3 = c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "rey",
                                             "modulos": {}}, headers=h)
    assert [r1.status_code, r2.status_code, r3.status_code] == [400, 400, 400]


def test_alta_omite_a_quien_no_esta_en_el_padron(db):
    c = TestClient(app)
    r = c.post("/api/admin/usuarios",
               json={"cuils": ["20999999997"], "rol_global": "usuario", "modulos": {}},
               headers=_token(c, "adm@t.com"))
    assert r.status_code == 200
    assert r.json()["creados"] == []
    assert r.json()["omitidos"] == [{"cuil": "20999999997", "motivo": "no está en el padrón"}]


def test_cambiar_roles_por_modulo(db):
    c = TestClient(app)
    op_id = db.query(Usuario).filter(Usuario.email == "op@t.com").one().id
    r = c.put(f"/api/admin/usuarios/{op_id}/modulos",
              json={"modulos": {"fletes": "gerente"}},
              headers=_token(c, "adm@t.com"))
    assert r.status_code == 200, r.text
    assert r.json()["modulos"] == {"fletes": "gerente"}


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
    c.post("/api/admin/usuarios", json={"cuils": [CUIL_A], "rol_global": "usuario", "modulos": {}}, headers=h)
    nuevo_id = db.query(Usuario).filter(Usuario.email == email_de_cuil(CUIL_A)).one().id

    r = c.post(f"/api/admin/usuarios/{nuevo_id}/password", json={}, headers=h)
    assert r.status_code == 200
    assert r.json()["password"] == CUIL_A
    assert c.post("/api/auth/login", data={"username": CUIL_A, "password": CUIL_A}).status_code == 200


def test_usuario_inexistente_da_404(db):
    c = TestClient(app)
    h = _token(c, "adm@t.com")
    assert c.patch("/api/admin/usuarios/9999", json={"nombre": "X"}, headers=h).status_code == 404
