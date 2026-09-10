"""CUIL como identificador: email sintético y normalización (PR 5 etapa 0)."""
from app.core.identidad import (
    DOMINIO_USUARIOS, cuil_de_email, email_de_cuil, normalizar_cuil,
)


def test_normaliza_con_guiones_espacios_y_pelado():
    assert normalizar_cuil("20-11111111-9") == "20111111119"
    assert normalizar_cuil(" 20 11111111 9 ") == "20111111119"
    assert normalizar_cuil("20111111119") == "20111111119"


def test_rechaza_lo_que_no_es_cuil():
    assert normalizar_cuil("123") is None
    assert normalizar_cuil("liq@asturiana.com") is None
    assert normalizar_cuil("") is None
    assert normalizar_cuil(None) is None


def test_email_sintetico_ida_y_vuelta():
    email = email_de_cuil("20111111119")
    assert email == f"20111111119@{DOMINIO_USUARIOS}"
    assert cuil_de_email(email) == "20111111119"


def test_email_real_no_tiene_cuil():
    assert cuil_de_email("liquidador@asturiana.com") is None
    assert cuil_de_email(None) is None
