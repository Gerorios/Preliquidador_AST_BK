# Reproduce el IntegrityError que revienta scripts/crear_usuario.py al
# reasignar `usuario.modulos = [...]` con el mismo módulo y otro rol
# (SQLAlchemy inserta las filas nuevas antes de borrar las huérfanas y choca
# contra la UNIQUE (usuario_id, modulo)). reemplazar_modulos() borra y hace
# flush antes de asignar, así que no debería fallar.

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.core.models import Usuario, UsuarioModulo
from scripts.crear_usuario import reemplazar_modulos


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def test_reemplazar_modulos_no_revienta_con_integrity_error(db):
    usuario = Usuario(
        nombre="Test", email="t@t.com", password="x", rol="usuario", activo=True,
    )
    usuario.modulos = [UsuarioModulo(modulo="preliquidacion", rol="operador")]
    db.add(usuario)
    db.commit()

    reemplazar_modulos(db, usuario, [("preliquidacion", "gerente")])
    db.commit()

    db.refresh(usuario)
    assert len(usuario.modulos) == 1
    assert usuario.modulos[0].modulo == "preliquidacion"
    assert usuario.modulos[0].rol == "gerente"
