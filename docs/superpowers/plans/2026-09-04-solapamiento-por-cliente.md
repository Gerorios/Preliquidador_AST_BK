# Solapamiento por cliente: compuerta con confirmación y listado vigente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que no se pueda crear (sin confirmarlo a conciencia) un Concepto por cliente que se sume a Conceptos específicos del mismo cliente, o viceversa, y que los solapamientos vigentes de una quincena queden siempre visibles en la página de Conceptos.

**Architecture:** El modelo de matching NO cambia (ADR-0011 reafirmado: los cuatro caminos suman, el tilde solo apaga comunes). Se agrega un servicio de detección `app/services/solapamiento_service.py` con dos entradas: `detectar_solapamiento_candidato(...)` (¿esta regla que quiero crear solapa con algo?) y `listar_solapamientos(db, quincena)` (¿qué solapamientos conviven hoy?). El `POST /api/precios/conceptos` usa la primera como **compuerta**: si hay solapamiento y el body no trae `confirmar_solapamiento: true`, responde **409** con el detalle (fincas, códigos coincidentes, líneas afectadas) y no crea nada. El front atrapa el 409, muestra un diálogo con ese detalle y botones cuyo default es el seguro ("Crear solo para la finca X" cuando se viene de una faltante). Un `GET /api/precios/conceptos/solapamientos` alimenta una franja ámbar arriba de la página, y `copiar_quincena` informa cuántos solapamientos heredó.

**Tech Stack:** Backend FastAPI + SQLAlchemy + pytest (sqlite en memoria en tests). Frontend React 18 + @tanstack/react-query v5 + axios + CSS Modules + react-hot-toast.

**Spec:** Sesión de grilling del 2026-09-04 (este documento la resume en "Decisiones de diseño"). Glosario: `CONTEXT.md` → término **Solapamiento por cliente**. ADRs relacionados: `docs/adr/0009-reemplaza-comun.md`, `docs/adr/0011-conceptos-por-cliente-y-supervisor.md`, `docs/adr/0008-precio-por-categoria-mantenimiento.md`.

## Decisiones de diseño (cerradas en grilling)

1. **El error fue del liquidador, no del modelo.** No se introduce jerarquía "el más específico gana". Se hace visible el solapamiento y se pide confirmación.
2. **Alerta con confirmación, no bloqueo duro.** Existe el caso legítimo (raro) de "precio por cliente base + plus por finca que suma".
3. **Qué es solapamiento:** misma quincena, misma tarea, mismo cliente, una regla **por cliente** (cliente sin finca, sin supervisor) contra una o más **específicas** (cliente + finca). En ambas direcciones. NO es solapamiento el cruce con el eje supervisor ni común vs no-común.
4. **El código de liquidación es agravante, no condición:** se alerta igual con códigos distintos; si coinciden, el mensaje lo dice en rojo ("cobrarían el código 461 DOS VECES").
5. **La categoría participa:** dos reglas con categoría explícita y distinta NO solapan. Si alguna es NULL o coinciden, sí. El conteo de líneas afectadas cuenta solo las que matchean ambas reglas de verdad (con filtro de categoría de cada una). Si el conteo da 0 la alerta aparece igual (el maestro se hereda).
6. **La compuerta vive en el POST** (409 + `confirmar_solapamiento`). Sin endpoint de preview separado. El PATCH no puede cambiar cliente/finca, así que no necesita compuerta.
7. **Listado vigente:** `GET /conceptos/solapamientos?quincena=` + franja ámbar arriba de Conceptos, visible en todas las solapas, solo cuando hay al menos uno. `copiar_quincena` devuelve la cantidad heredada y el toast lo dice.
8. **Botones del diálogo:** desde faltante creando por cliente → "Crear solo para {finca}" (default, foco, Enter), "Sumar igual a las N", "Cancelar". Desde "+ Nuevo" o GrupoCard, o en dirección inversa (específica sobre por cliente) → "Sumar igual" y "Cancelar". "Sumar igual" nunca es default. En el encadenado "¿Crear otra regla?" el diálogo sale en cada alta.
9. **Sin ADR nuevo.** Se agrega un párrafo a ADR-0011.

## Global Constraints

- Dos repos: backend `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion` (rama `feature/solapamiento-por-cliente`) y frontend `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion` (rama `feature/solapamiento-por-cliente`). NUNCA commitear en `main` de ninguno.
- **Sin migración**: no hay columnas nuevas. Solo un campo nuevo en el body del POST (`confirmar_solapamiento`) y un campo opcional nuevo en `MensajeResponse`.
- Backend: tests con pytest (`python -m pytest tests/<archivo> -q`), sqlite en memoria, patrón de fixtures idéntico a `tests/test_conceptos_cliente_supervisor.py`. Los endpoints se invocan como funciones (`crear_concepto(datos=..., db=db)`), sin TestClient.
- Frontend: no hay suite de tests; la verificación por task es `npm run build` sin errores. Smoke final contra backend local con la quincena actual: SOLO lecturas, y un alta de prueba que el usuario valide (la base es dato real).
- Textos de UI y comentarios en español con tildes correctas. Estilo del archivo (camelCase en JS, snake_case en Python).
- Normalización de nombres siempre `strip().upper()` (como `_lineas_por_match`).
- La base `db_propia` es producción. PROHIBIDO deployar al VPS sin OK explícito del usuario.
- Los números de línea citados son de `main` al 2026-09-04; verificarlos con grep antes de editar.
- Commits terminan con:
  `Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>`

---

## Parte A — Backend

### Task A0: Rama de trabajo backend

**Files:** ninguno (solo git).

**Interfaces:**
- Produces: rama `feature/solapamiento-por-cliente` activa en el repo backend.

- [ ] **Step 1: Crear la rama**

```bash
cd "C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion"
git checkout main && git pull && git checkout -b feature/solapamiento-por-cliente
git branch --show-current   # debe decir: feature/solapamiento-por-cliente
```

---

### Task A1: Servicio de detección — compatibilidad de categorías y candidato por cliente

**Files:**
- Create: `app/services/solapamiento_service.py`
- Test: `tests/test_solapamiento_por_cliente.py`

**Interfaces:**
- Consumes: `ConceptoLiquidacion`, `Preliquidacion`, `PreliquidacionLinea`, `CategoriaOperario` (modelos existentes); `PreliquidacionService._lineas_por_match(preliq_id, tarea, cliente, finca, supervisor)` y `PreliquidacionService._categoria_por_cuil(quincena)` (existentes en `app/services/preliquidacion_service.py:385` y `:700`).
- Produces:
  ```python
  def categorias_compatibles(a: Optional[int], b: Optional[int]) -> bool
  def detectar_solapamiento_candidato(
      db, quincena: date, tarea_nombre: str, cliente_nombre: Optional[str],
      finca_nombre: Optional[str], supervisor_nombre: Optional[str],
      codigo: Optional[int], categoria: Optional[int],
  ) -> Optional[dict]
  ```
  El dict devuelto (o `None` si no hay solapamiento) tiene SIEMPRE esta forma, que también usa el listado de la Task A2:
  ```python
  {
    "tarea_nombre": str, "cliente_nombre": str,
    "direccion": "por_cliente_sobre_especificos" | "especifico_sobre_por_cliente",
    "reglas_por_cliente": [ {"id": int, "codigo": int|None, "precio": str|None, "categoria": int|None} ],
    "especificos":        [ {"id": int, "finca_nombre": str, "codigo": int|None, "precio": str|None,
                              "categoria": int|None, "mismo_codigo": bool} ],
    "fincas": [str],                 # fincas con específica involucrada, ordenadas
    "codigos_coincidentes": [int],   # códigos presentes en ambos lados
    "lineas_afectadas": int,         # líneas de la quincena que matchean ambos lados
  }
  ```
  Para un candidato (regla que todavía no existe) el lado del candidato va vacío en la lista y el front completa con lo que envió.

- [ ] **Step 1: Escribir los tests que fallan (categorías + candidato por cliente)**

Crear `tests/test_solapamiento_por_cliente.py`:

```python
"""Solapamiento por cliente (CONTEXT.md): una regla POR CLIENTE y una o más
ESPECÍFICAS del mismo cliente, misma tarea y quincena, matchean las mismas
líneas y SUMAN (ADR-0011). No es error del modelo: el sistema lo hace visible
y pide confirmación. La categoría participa (categorías explícitas distintas
no solapan); el código coincidente es agravante, no condición.
"""
from datetime import date
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    CategoriaOperario, UnidadBaseConcepto, TipoConcepto,
)
from app.services.solapamiento_service import (
    categorias_compatibles, detectar_solapamiento_candidato,
)

Q = date(2026, 8, 16)
TAREA = "ENANCHADOR BOLSONES HORAS - CARGA"
CLIENTE = "CITRUSVIL"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=Q):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea=TAREA, cliente=CLIENTE, finca="EL CEIBAL", cuil="20-1-1",
           supervisor=None, hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        nombre_supervisor=supervisor, cuit=cuil,
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"), hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, quincena=Q, tarea=TAREA, cliente=None, finca=None, supervisor=None,
              codigo=461, precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL,
              reemplaza_comun=True, categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente, finca_nombre=finca,
        supervisor_nombre=supervisor, codigo=codigo, unidad_base=unidad, precio=precio,
        tipo=TipoConcepto.OTRO, reemplaza_comun=reemplaza_comun, categoria=categoria,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _candidato_por_cliente(db, codigo=461, categoria=None, cliente=CLIENTE, tarea=TAREA):
    return detectar_solapamiento_candidato(
        db, quincena=Q, tarea_nombre=tarea, cliente_nombre=cliente,
        finca_nombre=None, supervisor_nombre=None, codigo=codigo, categoria=categoria,
    )


# ─── categorías ───────────────────────────────────────────────────────────────

def test_categorias_compatibles():
    assert categorias_compatibles(None, None)
    assert categorias_compatibles(None, 3)
    assert categorias_compatibles(3, None)
    assert categorias_compatibles(3, 3)
    assert not categorias_compatibles(3, 5)


# ─── candidato POR CLIENTE sobre específicas existentes (el caso real) ────────

def test_por_cliente_sobre_cinco_especificas_mismo_codigo(db):
    preliq = _preliq(db)
    fincas = ["EL CEIBAL", "LA RAMADA", "SAN JOSE", "LOS NOGALES", "EL TIMBO"]
    for f in fincas:
        _concepto(db, cliente=CLIENTE, finca=f, codigo=461)
    # 3 líneas en fincas con específica + 1 en la finca nueva (sin regla)
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-1")
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-2")
    _linea(db, preliq, finca="LA RAMADA", cuil="20-1-3")
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-4")

    s = _candidato_por_cliente(db, codigo=461)

    assert s is not None
    assert s["direccion"] == "por_cliente_sobre_especificos"
    assert s["tarea_nombre"] == TAREA and s["cliente_nombre"] == CLIENTE
    assert s["reglas_por_cliente"] == []            # el candidato no existe todavía
    assert sorted(s["fincas"]) == sorted(fincas)
    assert len(s["especificos"]) == 5
    assert all(e["mismo_codigo"] for e in s["especificos"])
    assert s["codigos_coincidentes"] == [461]
    assert s["lineas_afectadas"] == 3               # LA NUEVA no cuenta: no tiene específica


def test_por_cliente_con_codigo_distinto_alerta_sin_agravante(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    s = _candidato_por_cliente(db, codigo=520)

    assert s is not None
    assert s["codigos_coincidentes"] == []
    assert s["especificos"][0]["mismo_codigo"] is False


def test_por_cliente_sin_especificas_no_solapa(db):
    _preliq(db)
    _concepto(db, codigo=461)                                   # común
    _concepto(db, supervisor="PEREZ", codigo=461)               # por supervisor
    _concepto(db, cliente="OTRO CLIENTE", finca="X", codigo=461)  # otro cliente

    assert _candidato_por_cliente(db, codigo=461) is None


def test_por_cliente_normaliza_mayusculas_y_espacios(db):
    _preliq(db)
    _concepto(db, tarea=TAREA.lower(), cliente=" citrusvil ", finca="EL CEIBAL", codigo=461)

    s = _candidato_por_cliente(db, codigo=461, cliente="CITRUSVIL", tarea=TAREA)

    assert s is not None
    assert s["fincas"] == ["EL CEIBAL"]


def test_sin_preliquidacion_generada_alerta_igual_con_cero_lineas(db):
    # Sin Preliquidacion para la quincena: la alerta sale (el maestro se
    # hereda) pero lineas_afectadas es 0.
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    s = _candidato_por_cliente(db, codigo=461)

    assert s is not None
    assert s["lineas_afectadas"] == 0
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_solapamiento_por_cliente.py -q`
Expected: FAIL / ERROR con `ModuleNotFoundError: No module named 'app.services.solapamiento_service'`.

- [ ] **Step 3: Implementar el servicio (mínimo para estos tests)**

Crear `app/services/solapamiento_service.py`:

```python
"""Solapamiento por cliente (CONTEXT.md).

Para la misma quincena y tarea, una regla POR CLIENTE (cliente sin finca, sin
supervisor) y una o más ESPECÍFICAS (cliente + finca) de ESE MISMO cliente
matchean las mismas líneas y, por ADR-0011, SUMAN. No es un error del
modelo: es un riesgo de pago doble que el liquidador debe controlar. Este
módulo lo detecta (para la compuerta del POST y para el listado vigente);
NO cambia el matching.

Reglas:
- La categoría participa: dos categorías explícitas y distintas NO solapan
  (pagan a personas distintas). NULL en alguna, o iguales → solapan.
- El código coincidente es agravante (se informa), no condición.
- El cruce con el eje supervisor y el común vs no-común NO son solapamiento.
"""
from datetime import date
from typing import Optional

from sqlalchemy import func

from app.models.models import ConceptoLiquidacion, Preliquidacion
from app.services.preliquidacion_service import PreliquidacionService

DIRECCION_POR_CLIENTE = "por_cliente_sobre_especificos"
DIRECCION_ESPECIFICO = "especifico_sobre_por_cliente"


def _norm(s: Optional[str]) -> str:
    return (s or "").strip().upper()


def categorias_compatibles(a: Optional[int], b: Optional[int]) -> bool:
    """Dos reglas pueden matchear a la misma persona si alguna no tiene
    categoría o si tienen la misma."""
    return a is None or b is None or a == b


def _precio_str(p) -> Optional[str]:
    return None if p is None else str(p)


def _regla_por_cliente_dict(c: ConceptoLiquidacion) -> dict:
    return {"id": c.id, "codigo": c.codigo, "precio": _precio_str(c.precio),
            "categoria": c.categoria}


def _especifico_dict(c: ConceptoLiquidacion, codigos_otro_lado: set) -> dict:
    return {"id": c.id, "finca_nombre": c.finca_nombre, "codigo": c.codigo,
            "precio": _precio_str(c.precio), "categoria": c.categoria,
            "mismo_codigo": c.codigo is not None and c.codigo in codigos_otro_lado}


def _reglas_eje_cliente(db, quincena: date, tarea_nombre: str, cliente_nombre: str):
    """Todas las reglas de esa quincena/tarea/cliente (normalizado), sin
    supervisor. Devuelve (por_cliente, especificos)."""
    reglas = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena,
        func.upper(func.trim(ConceptoLiquidacion.tarea_nombre)) == _norm(tarea_nombre),
        func.upper(func.trim(ConceptoLiquidacion.cliente_nombre)) == _norm(cliente_nombre),
        ConceptoLiquidacion.supervisor_nombre.is_(None),
    ).all()
    por_cliente = [c for c in reglas if not (c.finca_nombre or "").strip()]
    especificos = [c for c in reglas if (c.finca_nombre or "").strip()]
    return por_cliente, especificos


def _contar_lineas_doble_match(db, quincena: date, tarea_nombre: str, cliente_nombre: str,
                               lado_pc: list, lado_esp: list) -> int:
    """Líneas de la quincena (tarea + cliente) para las que pasa al menos una
    regla por cliente Y al menos una específica de su finca, aplicando el
    filtro de categoría de cada regla a la persona de la línea (ADR-0008).

    lado_pc / lado_esp son listas de dicts {"finca_nombre"?, "categoria"}:
    sirven tanto para reglas existentes como para el candidato que todavía
    no está en la base.
    """
    preliq = db.query(Preliquidacion).filter(Preliquidacion.quincena == quincena).first()
    if not preliq or not lado_pc or not lado_esp:
        return 0
    svc = PreliquidacionService(db)
    cat_por_cuil = svc._categoria_por_cuil(quincena)
    lineas = svc._lineas_por_match(preliq.id, tarea_nombre, cliente_nombre)

    def pasa(regla: dict, cuil) -> bool:
        cat = regla.get("categoria")
        return cat is None or cat == cat_por_cuil.get(_norm(cuil))

    esp_por_finca: dict = {}
    for e in lado_esp:
        esp_por_finca.setdefault(_norm(e.get("finca_nombre")), []).append(e)

    total = 0
    for l in lineas:
        if not any(pasa(pc, l.cuit) for pc in lado_pc):
            continue
        candidatas = esp_por_finca.get(_norm(l.nombre_finca), [])
        if any(pasa(e, l.cuit) for e in candidatas):
            total += 1
    return total


def _armar(quincena, tarea_nombre, cliente_nombre, direccion, por_cliente: list,
           especificos: list, lado_pc_dicts: list, lado_esp_dicts: list, db) -> dict:
    codigos_pc = {d.get("codigo") for d in lado_pc_dicts if d.get("codigo") is not None}
    codigos_esp = {d.get("codigo") for d in lado_esp_dicts if d.get("codigo") is not None}
    return {
        "tarea_nombre": tarea_nombre,
        "cliente_nombre": cliente_nombre,
        "direccion": direccion,
        "reglas_por_cliente": [_regla_por_cliente_dict(c) for c in por_cliente],
        "especificos": [_especifico_dict(c, codigos_pc) for c in especificos],
        "fincas": sorted({_norm(d.get("finca_nombre")) for d in lado_esp_dicts}),
        "codigos_coincidentes": sorted(codigos_pc & codigos_esp),
        "lineas_afectadas": _contar_lineas_doble_match(
            db, quincena, tarea_nombre, cliente_nombre, lado_pc_dicts, lado_esp_dicts,
        ),
    }


def detectar_solapamiento_candidato(
    db, quincena: date, tarea_nombre: str, cliente_nombre: Optional[str],
    finca_nombre: Optional[str], supervisor_nombre: Optional[str],
    codigo: Optional[int], categoria: Optional[int],
) -> Optional[dict]:
    """¿La regla que se quiere crear solapa con reglas ya existentes del eje
    cliente? None si no (común, por supervisor, o sin contraparte)."""
    if not (cliente_nombre or "").strip() or (supervisor_nombre or "").strip():
        return None  # común o por supervisor: no participan
    tarea_n = _norm(tarea_nombre)
    cliente_n = _norm(cliente_nombre)
    por_cliente, especificos = _reglas_eje_cliente(db, quincena, tarea_n, cliente_n)

    candidato = {"codigo": codigo, "categoria": categoria,
                 "finca_nombre": _norm(finca_nombre) or None}

    if candidato["finca_nombre"] is None:
        # Candidato POR CLIENTE: contraparte = específicas compatibles.
        contra = [e for e in especificos if categorias_compatibles(e.categoria, categoria)]
        if not contra:
            return None
        esp_dicts = [{"finca_nombre": e.finca_nombre, "categoria": e.categoria, "codigo": e.codigo}
                     for e in contra]
        return _armar(quincena, tarea_n, cliente_n, DIRECCION_POR_CLIENTE,
                      por_cliente=[], especificos=contra,
                      lado_pc_dicts=[candidato], lado_esp_dicts=esp_dicts, db=db)

    # Candidato ESPECÍFICO: contraparte = reglas por cliente compatibles.
    contra = [pc for pc in por_cliente if categorias_compatibles(pc.categoria, categoria)]
    if not contra:
        return None
    pc_dicts = [{"categoria": pc.categoria, "codigo": pc.codigo} for pc in contra]
    return _armar(quincena, tarea_n, cliente_n, DIRECCION_ESPECIFICO,
                  por_cliente=contra, especificos=[],
                  lado_pc_dicts=pc_dicts, lado_esp_dicts=[candidato], db=db)
```

Nota para el implementador: en `_armar`, cuando el candidato es específico, `_especifico_dict` no se llama (lista vacía) y el `mismo_codigo` de las `reglas_por_cliente` no se informa por regla; el agravante se lee de `codigos_coincidentes`. Eso es intencional y el front lo usa así.

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_solapamiento_por_cliente.py -q`
Expected: `6 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/services/solapamiento_service.py tests/test_solapamiento_por_cliente.py
git commit -m "feat(conceptos): servicio de detección de solapamiento por cliente (candidato por cliente)

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task A2: Servicio de detección — dirección inversa, categoría y listado vigente

**Files:**
- Modify: `app/services/solapamiento_service.py` (agregar `listar_solapamientos`)
- Test: `tests/test_solapamiento_por_cliente.py` (agregar tests)

**Interfaces:**
- Consumes: todo lo de Task A1.
- Produces:
  ```python
  def listar_solapamientos(db, quincena: date) -> list[dict]
  ```
  Un dict por par (tarea, cliente) que tenga al menos una regla por cliente y al menos una específica con categorías compatibles. Misma forma que Task A1, con `direccion = "por_cliente_sobre_especificos"`, `reglas_por_cliente` con TODAS las por cliente del par y `especificos` solo las que son compatibles con alguna por cliente. Ordenado por `tarea_nombre`, `cliente_nombre`.

- [ ] **Step 1: Agregar los tests que fallan**

Al final de `tests/test_solapamiento_por_cliente.py`:

```python
from app.services.solapamiento_service import listar_solapamientos


def _candidato_especifico(db, finca, codigo=461, categoria=None):
    return detectar_solapamiento_candidato(
        db, quincena=Q, tarea_nombre=TAREA, cliente_nombre=CLIENTE,
        finca_nombre=finca, supervisor_nombre=None, codigo=codigo, categoria=categoria,
    )


# ─── dirección inversa: candidato ESPECÍFICO sobre por cliente existente ─────

def test_especifico_sobre_por_cliente_existente(db):
    preliq = _preliq(db)
    pc = _concepto(db, cliente=CLIENTE, finca=None, codigo=461, precio=Decimal("900"))
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-1")
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-2")
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-3")   # otra finca: no cuenta

    s = _candidato_especifico(db, finca="LA NUEVA", codigo=461)

    assert s is not None
    assert s["direccion"] == "especifico_sobre_por_cliente"
    assert [r["id"] for r in s["reglas_por_cliente"]] == [pc.id]
    assert Decimal(s["reglas_por_cliente"][0]["precio"]) == Decimal("900")
    assert s["especificos"] == []
    assert s["fincas"] == ["LA NUEVA"]
    assert s["codigos_coincidentes"] == [461]
    assert s["lineas_afectadas"] == 2


def test_especifico_sin_por_cliente_no_solapa(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)   # otra específica
    _concepto(db, codigo=461)                                        # común

    assert _candidato_especifico(db, finca="LA NUEVA") is None


# ─── categoría ───────────────────────────────────────────────────────────────

def test_categorias_explicitas_distintas_no_solapan(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)

    assert _candidato_por_cliente(db, codigo=461, categoria=5) is None


def test_categoria_null_contra_explicita_solapa_y_cuenta_solo_esa_categoria(db):
    preliq = _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)
    db.add_all([
        CategoriaOperario(quincena=Q, cuil="20-1-1", categoria=3),
        CategoriaOperario(quincena=Q, cuil="20-1-2", categoria=5),
    ])
    db.commit()
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-1")   # cat 3: cobra doble
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-2")   # cat 5: la específica no le aplica
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-3")   # sin categoría: la específica no le aplica

    s = _candidato_por_cliente(db, codigo=461, categoria=None)

    assert s is not None
    assert s["lineas_afectadas"] == 1


# ─── listado vigente ─────────────────────────────────────────────────────────

def test_listar_solapamientos_vacio_cuando_no_hay(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    _concepto(db, cliente="OTRO", finca=None, codigo=461)   # por cliente de OTRO cliente

    assert listar_solapamientos(db, Q) == []


def test_listar_solapamientos_agrupa_por_tarea_y_cliente(db):
    preliq = _preliq(db)
    # Par 1: CITRUSVIL — 2 por cliente + 2 específicas, 1 específica incompatible por categoría
    pc1 = _concepto(db, cliente=CLIENTE, finca=None, codigo=461)
    pc2 = _concepto(db, cliente=CLIENTE, finca=None, codigo=520)
    e1 = _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    e2 = _concepto(db, cliente=CLIENTE, finca="LA RAMADA", codigo=700)
    _concepto(db, cliente=CLIENTE, finca="SAN JOSE", codigo=461, categoria=3)  # compatible: pc1 no tiene categoría
    # Par 2: otra tarea, mismo cliente, solo específicas → no aparece
    _concepto(db, tarea="OTRA TAREA", cliente=CLIENTE, finca="EL CEIBAL", codigo=1)
    _linea(db, preliq, finca="EL CEIBAL", cuil="20-1-1")
    _linea(db, preliq, finca="LA RAMADA", cuil="20-1-2")
    _linea(db, preliq, finca="LA NUEVA", cuil="20-1-3")

    lista = listar_solapamientos(db, Q)

    assert len(lista) == 1
    s = lista[0]
    assert (s["tarea_nombre"], s["cliente_nombre"]) == (TAREA, CLIENTE)
    assert s["direccion"] == "por_cliente_sobre_especificos"
    assert sorted(r["id"] for r in s["reglas_por_cliente"]) == sorted([pc1.id, pc2.id])
    assert sorted(s["fincas"]) == ["EL CEIBAL", "LA RAMADA", "SAN JOSE"]
    assert s["codigos_coincidentes"] == [461]
    assert [e["mismo_codigo"] for e in sorted(s["especificos"], key=lambda e: e["finca_nombre"])] == [True, False, True]
    assert s["lineas_afectadas"] == 2


def test_listar_solapamientos_excluye_especificas_incompatibles_por_categoria(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461, categoria=5)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)   # incompatible
    _concepto(db, cliente=CLIENTE, finca="LA RAMADA", codigo=461, categoria=5)   # compatible

    lista = listar_solapamientos(db, Q)

    assert len(lista) == 1
    assert lista[0]["fincas"] == ["LA RAMADA"]


def test_listar_solapamientos_ordena_por_tarea_y_cliente(db):
    _preliq(db)
    _concepto(db, tarea="ZETA", cliente="A", finca=None, codigo=1)
    _concepto(db, tarea="ZETA", cliente="A", finca="F", codigo=1)
    _concepto(db, tarea="ALFA", cliente="B", finca=None, codigo=1)
    _concepto(db, tarea="ALFA", cliente="B", finca="F", codigo=1)

    lista = listar_solapamientos(db, Q)

    assert [(s["tarea_nombre"], s["cliente_nombre"]) for s in lista] == [("ALFA", "B"), ("ZETA", "A")]
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_solapamiento_por_cliente.py -q`
Expected: los 4 tests de dirección inversa/categoría PASAN (ya cubiertos por A1); los de `listar_solapamientos` FALLAN con `ImportError: cannot import name 'listar_solapamientos'`. Si alguno de dirección inversa falla, arreglar `detectar_solapamiento_candidato` antes de seguir.

- [ ] **Step 3: Implementar `listar_solapamientos`**

Al final de `app/services/solapamiento_service.py`:

```python
def listar_solapamientos(db, quincena: date) -> list:
    """Solapamientos por cliente VIGENTES en la quincena: un ítem por par
    (tarea, cliente) con al menos una regla por cliente y al menos una
    específica compatible por categoría. Alimenta la franja de aviso de la
    página de Conceptos y el detalle de la copia entre quincenas."""
    reglas = db.query(ConceptoLiquidacion).filter(
        ConceptoLiquidacion.quincena == quincena,
        ConceptoLiquidacion.cliente_nombre.isnot(None),
        ConceptoLiquidacion.supervisor_nombre.is_(None),
    ).all()

    pares: dict = {}
    for c in reglas:
        if not _norm(c.cliente_nombre):
            continue
        clave = (_norm(c.tarea_nombre), _norm(c.cliente_nombre))
        pc, esp = pares.setdefault(clave, ([], []))
        (esp if (c.finca_nombre or "").strip() else pc).append(c)

    resultado = []
    for (tarea_n, cliente_n), (por_cliente, especificos) in sorted(pares.items()):
        if not por_cliente or not especificos:
            continue
        compatibles = [
            e for e in especificos
            if any(categorias_compatibles(e.categoria, pc.categoria) for pc in por_cliente)
        ]
        if not compatibles:
            continue
        pc_dicts = [{"categoria": pc.categoria, "codigo": pc.codigo} for pc in por_cliente]
        esp_dicts = [{"finca_nombre": e.finca_nombre, "categoria": e.categoria, "codigo": e.codigo}
                     for e in compatibles]
        resultado.append(_armar(
            quincena, tarea_n, cliente_n, DIRECCION_POR_CLIENTE,
            por_cliente=por_cliente, especificos=compatibles,
            lado_pc_dicts=pc_dicts, lado_esp_dicts=esp_dicts, db=db,
        ))
    return resultado
```

- [ ] **Step 4: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_solapamiento_por_cliente.py -q`
Expected: `14 passed`.

- [ ] **Step 5: Commit**

```bash
git add app/services/solapamiento_service.py tests/test_solapamiento_por_cliente.py
git commit -m "feat(conceptos): dirección inversa, categoría y listado vigente de solapamientos

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task A3: Compuerta 409 en `POST /api/precios/conceptos`

**Files:**
- Modify: `app/schemas/schemas.py:137-153` (`ConceptoUnifRequest`: campo `confirmar_solapamiento`)
- Modify: `app/api/precios.py:292-330` (`crear_concepto`)
- Test: `tests/test_solapamiento_por_cliente.py` (agregar tests)

**Interfaces:**
- Consumes: `detectar_solapamiento_candidato` (Task A1).
- Produces:
  - `ConceptoUnifRequest.confirmar_solapamiento: bool = False`.
  - El POST responde `HTTPException(409, detail={...})` con:
    ```python
    {"tipo": "solapamiento_por_cliente",
     "mensaje": "Esta regla se va a SUMAR a reglas ya existentes del mismo cliente.",
     "solapamiento": <dict de Task A1>}
    ```
    El front (Parte B) depende de `detail.tipo == "solapamiento_por_cliente"` y de `detail.solapamiento`.

- [ ] **Step 1: Agregar los tests que fallan**

Al final de `tests/test_solapamiento_por_cliente.py`:

```python
from app.schemas.schemas import ConceptoUnifRequest
from app.api.precios import crear_concepto


def _req(cliente=CLIENTE, finca=None, codigo=461, categoria=None, confirmar=None):
    kwargs = dict(
        quincena=Q, tarea_nombre=TAREA, cliente_nombre=cliente, finca_nombre=finca,
        codigo=codigo, unidad_base=UnidadBaseConcepto.HSJORNAL, precio=Decimal("100"),
        tipo=TipoConcepto.OTRO, categoria=categoria,
    )
    if confirmar is not None:
        kwargs["confirmar_solapamiento"] = confirmar
    return ConceptoUnifRequest(**kwargs)


# ─── compuerta en el POST ────────────────────────────────────────────────────

def test_post_por_cliente_sobre_especificas_responde_409_y_no_crea(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    antes = db.query(ConceptoLiquidacion).count()

    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=_req(finca=None, codigo=461), db=db)

    assert exc.value.status_code == 409
    d = exc.value.detail
    assert d["tipo"] == "solapamiento_por_cliente"
    assert d["solapamiento"]["fincas"] == ["EL CEIBAL"]
    assert d["solapamiento"]["codigos_coincidentes"] == [461]
    assert db.query(ConceptoLiquidacion).count() == antes


def test_post_con_confirmar_solapamiento_crea_igual(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    nuevo = crear_concepto(datos=_req(finca=None, codigo=461, confirmar=True), db=db)

    assert nuevo.id is not None
    assert nuevo.cliente_nombre == CLIENTE and nuevo.finca_nombre is None


def test_post_especifico_sobre_por_cliente_responde_409(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461)

    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos=_req(finca="LA NUEVA", codigo=461), db=db)

    assert exc.value.status_code == 409
    assert exc.value.detail["solapamiento"]["direccion"] == "especifico_sobre_por_cliente"


def test_post_sin_solapamiento_crea_sin_confirmar(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    # Específica para la finca nueva: el camino correcto, sin 409.
    nuevo = crear_concepto(datos=_req(finca="LA NUEVA", codigo=461), db=db)
    assert nuevo.finca_nombre == "LA NUEVA"

    # Común y por supervisor: nunca participan.
    comun = crear_concepto(datos=_req(cliente=None, finca=None, codigo=999), db=db)
    assert comun.cliente_nombre is None


def test_post_categorias_distintas_no_disparan_409(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461, categoria=3)

    nuevo = crear_concepto(datos=_req(finca=None, codigo=461, categoria=5), db=db)
    assert nuevo.id is not None


def test_confirmar_solapamiento_default_false():
    assert _req().confirmar_solapamiento is False
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python -m pytest tests/test_solapamiento_por_cliente.py -q -k "post or default_false"`
Expected: FAIL. `test_confirmar_solapamiento_default_false` con `AttributeError`; los de 409 con `DID NOT RAISE` (hoy el POST crea sin chistar).

- [ ] **Step 3: Agregar el campo al schema**

En `app/schemas/schemas.py`, dentro de `ConceptoUnifRequest`, después de `reemplaza_comun`:

```python
    # Solapamiento por cliente (CONTEXT.md): si la regla que se crea SUMA a
    # reglas del eje cliente ya existentes (por cliente vs específicas del
    # mismo cliente), el POST responde 409 con el detalle salvo que el
    # liquidador lo confirme explícitamente con True.
    confirmar_solapamiento: bool = False
```

- [ ] **Step 4: Agregar la compuerta al endpoint**

En `app/api/precios.py`, importar el servicio junto a los otros imports:

```python
from app.services.solapamiento_service import (
    detectar_solapamiento_candidato, listar_solapamientos,
)
```

(`listar_solapamientos` se usa en Task A4; importarlo ya evita tocar el import dos veces.)

En `crear_concepto`, inmediatamente después de `_validar_cliente_xor_supervisor(cliente_nombre, supervisor_nombre)` y ANTES de resolver `reemplaza_comun`:

```python
    # Compuerta de solapamiento por cliente. No bloquea: el liquidador puede
    # confirmar (caso raro "precio por cliente base + plus por finca"). El
    # detalle viaja en el 409 para que el front muestre fincas, códigos
    # coincidentes y líneas afectadas.
    if not datos.confirmar_solapamiento:
        solapamiento = detectar_solapamiento_candidato(
            db, quincena=datos.quincena, tarea_nombre=datos.tarea_nombre,
            cliente_nombre=cliente_nombre,
            finca_nombre=datos.finca_nombre, supervisor_nombre=supervisor_nombre,
            codigo=datos.codigo, categoria=datos.categoria,
        )
        if solapamiento:
            raise HTTPException(
                status_code=409,
                detail={
                    "tipo": "solapamiento_por_cliente",
                    "mensaje": "Esta regla se va a SUMAR a reglas ya existentes del mismo cliente.",
                    "solapamiento": solapamiento,
                },
            )
```

- [ ] **Step 5: Correr toda la suite**

Run: `python -m pytest tests -q`
Expected: todo en verde (los tests previos de `test_conceptos_cliente_supervisor.py`, `test_reemplaza_default.py`, etc. crean por cliente y específicos en combinaciones que podrían disparar el 409). Si alguno falla con 409, revisar si el test creaba un solapamiento real: en ese caso agregar `confirmar_solapamiento=True` al request de ese test con un comentario `# solapamiento intencional para probar que suman (ADR-0011)`. NO relajar la compuerta.

- [ ] **Step 6: Commit**

```bash
git add app/schemas/schemas.py app/api/precios.py tests/
git commit -m "feat(conceptos): POST responde 409 con detalle ante solapamiento por cliente salvo confirmación

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task A4: `GET /api/precios/conceptos/solapamientos` y conteo en la copia

**Files:**
- Modify: `app/api/precios.py` (endpoint nuevo antes de `@router.get("/conceptos/faltantes")` ~línea 455; `copiar_quincena` ~384-452)
- Modify: `app/schemas/schemas.py:90-92` (`MensajeResponse`)
- Test: `tests/test_solapamiento_por_cliente.py`

**Interfaces:**
- Consumes: `listar_solapamientos` (Task A2).
- Produces:
  - `GET /api/precios/conceptos/solapamientos?quincena=YYYY-MM-DD` → `list[dict]` (forma de Task A1). Accesible a todo rol con sesión (como los demás GET).
  - `MensajeResponse.solapamientos_heredados: Optional[int] = None`; `copiar_quincena` lo llena con `len(listar_solapamientos(db, quincena_destino))` y agrega ` · N solapamiento(s) por cliente` al `detalle` cuando N > 0.

- [ ] **Step 1: Agregar los tests que fallan**

Al final de `tests/test_solapamiento_por_cliente.py`:

```python
from app.api.precios import solapamientos_quincena, copiar_quincena


def test_endpoint_solapamientos_devuelve_lista(db):
    _preliq(db)
    _concepto(db, cliente=CLIENTE, finca=None, codigo=461)
    _concepto(db, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    lista = solapamientos_quincena(quincena=Q, db=db)

    assert len(lista) == 1
    assert lista[0]["cliente_nombre"] == CLIENTE


def test_copiar_informa_solapamientos_heredados(db):
    origen = date(2026, 8, 1)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca=None, codigo=461)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca="LA RAMADA", codigo=461)

    r = copiar_quincena(quincena_origen=origen, quincena_destino=Q, db=db)

    assert r.solapamientos_heredados == 1
    assert "1 solapamiento" in (r.detalle or "")


def test_copiar_sin_solapamientos_informa_cero(db):
    origen = date(2026, 8, 1)
    _concepto(db, quincena=origen, cliente=CLIENTE, finca="EL CEIBAL", codigo=461)

    r = copiar_quincena(quincena_origen=origen, quincena_destino=Q, db=db)

    assert r.solapamientos_heredados == 0
    assert "solapamiento" not in (r.detalle or "")
```

- [ ] **Step 2: Correr y verificar que fallan**

Run: `python -m pytest tests/test_solapamiento_por_cliente.py -q -k "endpoint or copiar"`
Expected: FAIL con `ImportError: cannot import name 'solapamientos_quincena'`.

- [ ] **Step 3: Schema**

En `app/schemas/schemas.py`, `MensajeResponse`:

```python
class MensajeResponse(BaseModel):
    mensaje: str
    detalle: Optional[str] = None
    # Solo lo llena copiar_quincena: cantidad de solapamientos por cliente
    # (CONTEXT.md) que quedaron vigentes en la quincena destino tras copiar.
    solapamientos_heredados: Optional[int] = None
```

- [ ] **Step 4: Endpoint de listado**

En `app/api/precios.py`, justo antes de `@router.get("/conceptos/faltantes")`:

```python
@router.get("/conceptos/solapamientos")
def solapamientos_quincena(
    quincena: date = Query(...),
    db: Session = Depends(get_db_propia),
):
    """
    Solapamientos por cliente vigentes en la quincena (CONTEXT.md): pares
    tarea+cliente donde conviven una regla por cliente y específicas del
    mismo cliente con categorías compatibles. Suman por ADR-0011; el
    liquidador debe controlarlos. Vacío = todo en orden.
    """
    return listar_solapamientos(db, quincena)
```

- [ ] **Step 5: Conteo en la copia**

En `copiar_quincena`, reemplazar el `return` final:

```python
    solapamientos = len(listar_solapamientos(db, quincena_destino))
    if solapamientos:
        plural = "s" if solapamientos != 1 else ""
        detalle += f" · {solapamientos} solapamiento{plural} por cliente"

    return MensajeResponse(
        mensaje="Conceptos copiados", detalle=detalle,
        solapamientos_heredados=solapamientos,
    )
```

- [ ] **Step 6: Correr toda la suite**

Run: `python -m pytest tests -q`
Expected: todo en verde. `test_copiar_heredado.py` compara `detalle` en algún test; si asegura igualdad exacta del string, ese test sigue pasando porque sin solapamientos no se agrega nada.

- [ ] **Step 7: Commit**

```bash
git add app/api/precios.py app/schemas/schemas.py tests/test_solapamiento_por_cliente.py
git commit -m "feat(conceptos): endpoint de solapamientos vigentes y conteo al copiar quincena

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task A5: Documentación — ADR-0011 y smoke backend

**Files:**
- Modify: `docs/adr/0011-conceptos-por-cliente-y-supervisor.md` (párrafo al final)
- Verificar: `CONTEXT.md` ya tiene el término **Solapamiento por cliente** (agregado el 2026-09-04 en el grilling; no tocar).

**Interfaces:** ninguna.

- [ ] **Step 1: Agregar el párrafo al ADR-0011**

Al final de `docs/adr/0011-conceptos-por-cliente-y-supervisor.md`:

```markdown

## Reafirmación (2026-09-04)

En la segunda quincena de agosto de 2026 un pago se duplicó por este diseño: una tarea tenía cinco conceptos específicos de un cliente (uno por finca), apareció una finca nueva sin regla, y el liquidador cargó reglas **por cliente** para cubrirla. Como los caminos suman y el tilde solo apaga comunes, las fincas que ya tenían específico cobraron doble. Se volvió a evaluar la jerarquía "el más específico gana" y se **rechazó de nuevo** por las mismas razones de arriba: el modelo no puede adivinar si una regla por cliente es un "default para el resto" o un plus que suma, y el caso legítimo de suma existe. La respuesta fue hacer el **Solapamiento por cliente** (ver `CONTEXT.md`) visible y explícito: el alta responde 409 con fincas, códigos coincidentes y líneas afectadas salvo confirmación expresa, hay un listado de solapamientos vigentes por quincena, y la copia entre quincenas informa cuántos hereda. El camino correcto para "una finca nueva" es crear la específica de esa finca, y la UI lo ofrece como acción por defecto.
```

- [ ] **Step 2: Smoke real de solo lectura contra la base**

Levantar el backend local (o usar el ya levantado) y consultar el endpoint nuevo con la quincena actual. Con un token de sesión válido (obtenerlo del login del front en DevTools → Application → localStorage, o pedírselo al usuario):

```bash
curl -s -H "Authorization: Bearer <TOKEN>" "http://localhost:8000/api/precios/conceptos/solapamientos?quincena=2026-08-16"
```

Expected: `[]` (el 2026-09-04 se verificó por SQL que la base no tiene solapamientos vigentes). Si devuelve elementos, reportarlos al usuario tal cual: son solapamientos reales que existen hoy.

- [ ] **Step 3: Commit y PR del backend**

```bash
git add docs/adr/0011-conceptos-por-cliente-y-supervisor.md CONTEXT.md
git commit -m "docs(adr): reafirmación de ADR-0011 tras el pago duplicado; término Solapamiento por cliente

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
git push -u origin feature/solapamiento-por-cliente
```

Crear el PR con `gh` (está fuera del PATH; ver memoria `gh-cli-no-instalado.md` para la ruta completa) usando `--body-file` con un cuerpo que resuma: compuerta 409, endpoint de listado, conteo al copiar, sin migración, 23 tests nuevos. NO mergear sin OK del usuario. NO deployar.

---

## Parte B — Frontend

### Task B0: Rama de trabajo frontend

**Files:** ninguno (solo git).

- [ ] **Step 1: Crear la rama**

```bash
cd "C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion"
git checkout main && git pull && git checkout -b feature/solapamiento-por-cliente
git branch --show-current   # debe decir: feature/solapamiento-por-cliente
```

---

### Task B1: El error de axios conserva status y detalle estructurado; servicio nuevo

**Files:**
- Modify: `src/services/api.js:20-30` (interceptor de respuesta)
- Modify: `src/services/preliquidacion.js:104-121` (agregar `listarSolapamientos`)

**Interfaces:**
- Produces:
  - Todo `Error` rechazado por `api` gana `error.status` (número o `undefined`) y `error.detail` (el `detail` crudo del backend: string u objeto). `error.message` sigue siendo un string legible: si `detail` es objeto usa `detail.mensaje`.
  - `listarSolapamientos(quincena) → Promise<Array<Solapamiento>>` donde `Solapamiento` es el dict de Task A1.

- [ ] **Step 1: Interceptor**

En `src/services/api.js`, reemplazar el interceptor de respuesta:

```js
// Si el servidor devuelve 401, cerrar sesión automáticamente.
// El Error que se propaga conserva `status` y `detail` (crudo) para que la UI
// pueda reaccionar a respuestas estructuradas — hoy el 409 de solapamiento
// por cliente, cuyo detail es un objeto {tipo, mensaje, solapamiento}.
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      useAuthStore.getState().logout()
      window.location.href = '/login'
    }
    const detail = err.response?.data?.detail
    const msg = (detail && typeof detail === 'object' ? detail.mensaje : detail)
      || err.message || 'Error desconocido'
    const error = new Error(msg)
    error.status = err.response?.status
    error.detail = detail
    return Promise.reject(error)
  }
)
```

- [ ] **Step 2: Servicio**

En `src/services/preliquidacion.js`, después de `listarConceptosFaltantes`:

```js
// Solapamientos por cliente vigentes en la quincena (una regla por cliente
// conviviendo con específicas del mismo cliente: suman, ADR-0011). Vacío =
// todo en orden.
export const listarSolapamientos = (quincena) =>
  api.get('/precios/conceptos/solapamientos', { params: { quincena } }).then(r => r.data)
```

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: sin errores.

- [ ] **Step 4: Commit**

```bash
git add src/services/api.js src/services/preliquidacion.js
git commit -m "feat(api): el Error conserva status y detail estructurado; servicio listarSolapamientos

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B2: Componente `DialogoSolapamiento` + CSS

**Files:**
- Modify: `src/pages/Conceptos.jsx` (nuevo componente antes de `PromptOtraRegla`, ~línea 338)
- Modify: `src/pages/Conceptos.module.css` (clases nuevas al final)

**Interfaces:**
- Produces:
  ```jsx
  <DialogoSolapamiento
    solapamiento={Solapamiento}      // detail.solapamiento del 409
    candidato={{ codigo, precio, categoria, finca_nombre }}  // lo que el liquidador intentó crear
    fincaNueva={string|null}          // solo desde una faltante creando por cliente
    onCrearSoloFinca={fn|null}        // null = no mostrar ese botón
    onSumarIgual={fn}
    onCancelar={fn}
  />
  ```
  Reglas: el botón por defecto (autoFocus + Enter) es "Crear solo para {fincaNueva}" si existe, si no "Cancelar". "Sumar igual" nunca tiene autoFocus. Escape = Cancelar.

- [ ] **Step 1: CSS**

Al final de `src/pages/Conceptos.module.css`:

```css
/* ─── Diálogo de solapamiento por cliente ─── */
.overlay {
  position: fixed; inset: 0; z-index: 50;
  background: rgba(0, 0, 0, 0.45);
  display: flex; align-items: center; justify-content: center;
  padding: 16px;
}
.dialogo {
  width: min(640px, 100%);
  max-height: 90vh; overflow: auto;
  background: var(--bg-elevated, #fff);
  border: 1px solid var(--warn);
  border-radius: var(--radius);
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.25);
  padding: 18px 20px;
  font-size: 0.88rem;
}
.dialogoTitulo {
  display: flex; align-items: center; gap: 8px;
  font-weight: 600; color: var(--warn); font-size: 1rem;
  margin-bottom: 12px;
}
.dialogoDatos { display: grid; grid-template-columns: 90px 1fr; gap: 4px 10px; margin-bottom: 12px; }
.dialogoLista { margin: 6px 0 12px 0; padding-left: 18px; }
.dialogoLista li { margin: 2px 0; }
.mismoCodigo { color: var(--danger); font-weight: 600; }
.dialogoImpacto {
  padding: 10px 12px; border-radius: var(--radius);
  background: var(--warn-dim); margin-bottom: 14px;
}
.dialogoImpactoGrave { background: var(--danger-dim); color: var(--danger); font-weight: 600; }
.dialogoBotones { display: flex; flex-wrap: wrap; gap: 8px; justify-content: flex-end; }

/* ─── Franja de solapamientos vigentes ─── */
.franjaSolap {
  border: 1px solid var(--warn);
  background: var(--warn-dim);
  border-radius: var(--radius);
  padding: 10px 14px;
  margin: 0 0 12px 0;
  font-size: 0.86rem;
}
.franjaSolapHead {
  display: flex; align-items: center; justify-content: space-between; gap: 10px;
  cursor: pointer; font-weight: 600; color: var(--warn);
}
.franjaSolapItem {
  display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 8px;
  padding: 8px 0; border-top: 1px solid rgba(150, 96, 15, 0.25);
}
.franjaSolapItem:first-of-type { margin-top: 8px; }
```

- [ ] **Step 2: Componente**

En `src/pages/Conceptos.jsx`, antes de `function PromptOtraRegla`:

```jsx
// ─── DialogoSolapamiento: confirmación ante un 409 de solapamiento por cliente
//
// El backend detectó que la regla que se quiere crear SUMA a reglas del eje
// cliente ya existentes (por cliente vs específicas del mismo cliente —
// ADR-0011 reafirmado). No bloquea: muestra fincas, códigos coincidentes y
// líneas afectadas y pide una decisión explícita. El botón peligroso
// ("Sumar igual") NUNCA es el default.
function DialogoSolapamiento({ solapamiento, candidato, fincaNueva, onCrearSoloFinca, onSumarIgual, onCancelar }) {
  const s = solapamiento
  const esPorClienteSobreEsp = s.direccion === 'por_cliente_sobre_especificos'
  const grave = s.codigos_coincidentes.length > 0
  const n = s.lineas_afectadas

  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') onCancelar() }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onCancelar])

  const fmtPrecio = (p) => p == null ? '—' : `$ ${Number(p).toLocaleString('es-AR', { maximumFractionDigits: 2 })}`

  return (
    <div className={styles.overlay} role="dialog" aria-modal="true" aria-labelledby="titulo-solap">
      <div className={styles.dialogo}>
        <div id="titulo-solap" className={styles.dialogoTitulo}>
          ⚠ Esta regla se va a SUMAR a reglas ya existentes
        </div>

        <div className={styles.dialogoDatos}>
          <span className={styles.textoMuted}>Tarea</span><b>{s.tarea_nombre}</b>
          <span className={styles.textoMuted}>Cliente</span>
          <b>{s.cliente_nombre}{esPorClienteSobreEsp ? ' (todas las fincas)' : ` / ${candidato.finca_nombre}`}</b>
          <span className={styles.textoMuted}>Nueva regla</span>
          <span>cód. <b className="mono">{candidato.codigo}</b> · {fmtPrecio(candidato.precio)}{candidato.categoria ? ` · cat. ${candidato.categoria}` : ''}</span>
        </div>

        {esPorClienteSobreEsp ? (
          <>
            <div>Ya existen <b>{s.especificos.length}</b> regla(s) específica(s) de {s.cliente_nombre} para esta tarea:</div>
            <ul className={styles.dialogoLista}>
              {s.especificos.map(e => (
                <li key={e.id}>
                  Finca <b>{e.finca_nombre}</b> · cód. <span className="mono">{e.codigo ?? '—'}</span>
                  {e.categoria ? ` · cat. ${e.categoria}` : ''} · {fmtPrecio(e.precio)}
                  {e.mismo_codigo && <span className={styles.mismoCodigo}> ← mismo código</span>}
                </li>
              ))}
            </ul>
          </>
        ) : (
          <>
            <div>Esta finca ya cobra por regla(s) <b>por cliente</b> de {s.cliente_nombre} (todas las fincas):</div>
            <ul className={styles.dialogoLista}>
              {s.reglas_por_cliente.map(r => (
                <li key={r.id}>
                  cód. <span className="mono">{r.codigo ?? '—'}</span>
                  {r.categoria ? ` · cat. ${r.categoria}` : ''} · {fmtPrecio(r.precio)}
                  {s.codigos_coincidentes.includes(r.codigo) && <span className={styles.mismoCodigo}> ← mismo código</span>}
                </li>
              ))}
            </ul>
          </>
        )}

        <div className={`${styles.dialogoImpacto} ${grave ? styles.dialogoImpactoGrave : ''}`}>
          {grave
            ? <>Las <b>{n}</b> línea(s) de esta quincena que matchean ambas reglas cobrarían el código <span className="mono">{s.codigos_coincidentes.join(', ')}</span> DOS VECES.</>
            : <><b>{n}</b> línea(s) de esta quincena matchean ambas reglas y cobrarían las dos (códigos distintos).</>}
          {n === 0 && <div className={styles.textoMuted}>Hoy no hay líneas afectadas, pero el maestro se hereda a la quincena siguiente.</div>}
          {fincaNueva && <div>Solo la finca <b>{fincaNueva}</b> no tiene regla.</div>}
        </div>

        <div className={styles.dialogoBotones}>
          {onCrearSoloFinca
            ? <button className="btn btn-primary" autoFocus onClick={onCrearSoloFinca}>Crear solo para {fincaNueva}</button>
            : <button className="btn" autoFocus onClick={onCancelar}>Cancelar</button>}
          <button className="btn btn-danger" onClick={onSumarIgual}>
            {esPorClienteSobreEsp ? `Sumar igual a las ${s.especificos.length}` : 'Sumar igual'}
          </button>
          {onCrearSoloFinca && <button className="btn" onClick={onCancelar}>Cancelar</button>}
        </div>
      </div>
    </div>
  )
}
```

Verificar que `useEffect` ya está importado desde `react` en la línea 1 del archivo (`import { useState, useMemo, useEffect, ... } from 'react'`); si no, agregarlo.

- [ ] **Step 3: Build**

Run: `npm run build`
Expected: sin errores (el componente todavía no se usa; puede haber warning de "defined but never used" solo si hay lint en el build; ignorar).

- [ ] **Step 4: Commit**

```bash
git add src/pages/Conceptos.jsx src/pages/Conceptos.module.css
git commit -m "feat(conceptos): componente DialogoSolapamiento y estilos de franja

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B3: Cablear el 409 en las tres superficies de alta

**Files:**
- Modify: `src/pages/Conceptos.jsx`: `Conceptos()` (estado + mutations ~758-780), `FilaFaltante` (~355-420), `GrupoCard` (~206-240), `handleCrearNuevo` (~930-955).

**Interfaces:**
- Consumes: `DialogoSolapamiento` (B2), `error.status` / `error.detail` (B1).
- Produces: en `Conceptos()` un estado `pendienteSolap` con forma
  ```js
  { solapamiento, datos /* body que se intentó */, fincaNueva /* string|null */, mutate /* mutCrear | mutCrearSinFaltantes */, onSuccess /* callback original */ }
  ```
  y un helper `manejarErrorCrear(err, ctx)` que las tres superficies usan en `onError`. Las superficies hijas reciben la prop nueva `onSolapamiento(ctx)`.

- [ ] **Step 1: Estado y helper en `Conceptos()`**

Junto a los demás `useState` de la página (cerca de `const [tab, setTab] = useState(1)`, ~línea 616):

```jsx
  // Solapamiento por cliente pendiente de decisión: el POST respondió 409 y
  // guardamos lo necesario para reintentar (confirmando o como específica).
  const [pendienteSolap, setPendienteSolap] = useState(null)
```

Debajo de la definición de `invalidar` (~línea 757):

```jsx
  // onError compartido por las 3 superficies de alta. Un 409 de solapamiento
  // abre el diálogo; cualquier otro error va al toast como siempre.
  // ctx = { datos, fincaNueva, mutate, onSuccess }
  const manejarErrorCrear = (err, ctx) => {
    if (err.status === 409 && err.detail?.tipo === 'solapamiento_por_cliente') {
      setPendienteSolap({ solapamiento: err.detail.solapamiento, ...ctx })
      return
    }
    toast.error(err.message)
  }

  const cerrarSolap = () => setPendienteSolap(null)

  const sumarIgual = () => {
    const p = pendienteSolap
    setPendienteSolap(null)
    p.mutate({ ...p.datos, confirmar_solapamiento: true }, { onSuccess: p.onSuccess })
  }

  const crearSoloFinca = () => {
    const p = pendienteSolap
    setPendienteSolap(null)
    // Convierte la regla por cliente en específica para la finca que faltaba.
    // No puede volver a dar 409: una específica solo solapa con una por
    // cliente ya existente, y si existiera el backend no habría devuelto
    // "por_cliente_sobre_especificos".
    p.mutate({ ...p.datos, finca_nombre: p.fincaNueva }, { onSuccess: p.onSuccess })
  }
```

- [ ] **Step 2: Mutations sin `onError` global**

Las mutations `mutCrear` y `mutCrearSinFaltantes` (~758-780) hoy tienen `onError: err => toast.error(err.message)`. Quitar esa línea de AMBAS: el `onError` pasa a darse por llamada, en cada superficie, para que reciba el contexto. Quedan:

```jsx
  const { mutate: mutCrear } = useMutation({
    mutationFn: crearConcepto,
    onSuccess: () => { toast.success('Regla guardada'); invalidar() },
  })

  const { mutate: mutCrearSinFaltantes } = useMutation({
    mutationFn: crearConcepto,
    onSuccess: () => {
      toast.success('Regla guardada')
      qc.invalidateQueries({ queryKey: ['conceptos'] })
      qc.invalidateQueries({ queryKey: ['quincenas-conceptos'] })
      qc.invalidateQueries({ queryKey: ['panel-precios'] })
      qc.invalidateQueries({ queryKey: ['lineas'] })
      qc.invalidateQueries({ queryKey: ['stats'] })
    },
  })
```

- [ ] **Step 3: `FilaFaltante` — la superficie con "Crear solo para la finca"**

Agregar la prop `onSolapamiento` a la firma:

```jsx
function FilaFaltante({ f, idx, quincena, todasFaltantes, mutCrear, mutCrearSinFaltantes, onFinEncadenado, supervisores, onSolapamiento }) {
```

Reemplazar `handleGuardar` completo:

```jsx
  const handleGuardar = () => {
    if (!form.codigo) { toast.error('Ingresá un código'); return }
    if (alcance === 'supervisor' && !supervisorSel) { toast.error('Seleccioná un supervisor'); return }
    const codigo = parseInt(form.codigo)
    const datos = {
      quincena,
      tarea_nombre:   f.tarea_nombre,
      cliente_nombre: (alcance === 'cliente' || alcance === 'finca') ? f.cliente_nombre : null,
      finca_nombre:   alcance === 'finca' ? f.finca_nombre : null,
      supervisor_nombre: alcance === 'supervisor' ? supervisorSel : null,
      codigo,
      unidad_base: form.unidad_base,
      precio:      form.precio !== '' ? parseFloat(form.precio) : null,
      tipo:        form.tipo,
      categoria:   form.categoria !== '' ? parseInt(form.categoria) : null,
      reemplaza_comun: alcance === 'comun' ? false : form.reemplaza_comun,
    }
    const onSuccess = () => setReglaCreada(codigo)
    mutCrearSinFaltantes(datos, {
      onSuccess,
      // Desde una faltante sabemos qué finca no tiene regla: si eligió "por
      // cliente" y solapa, el diálogo ofrece crear la específica de esa finca.
      onError: err => onSolapamiento(err, {
        datos, onSuccess, mutate: mutCrearSinFaltantes,
        fincaNueva: alcance === 'cliente' ? f.finca_nombre : null,
      }),
    })
  }
```

En el render de la tabla de faltantes (~línea 1035), pasar la prop:

```jsx
                      onSolapamiento={manejarErrorCrear}
```

- [ ] **Step 4: `GrupoCard`**

Agregar la prop `onSolapamiento` a la firma:

```jsx
function GrupoCard({ reglas, quincena, esComun, mutCrear, mutActualizar, mutEliminar, onSolapamiento }) {
```

Reemplazar `handleAgregar`:

```jsx
  const handleAgregar = () => {
    if (!nuevaRegla.codigo) { toast.error('Ingresá un código'); return }
    const codigo = parseInt(nuevaRegla.codigo)
    const datos = {
      quincena,
      tarea_nombre:   primera.tarea_nombre,
      cliente_nombre: esComun ? null : (primera.cliente_nombre ?? null),
      finca_nombre:   esComun ? null : (primera.finca_nombre ?? null),
      supervisor_nombre: esComun ? null : (primera.supervisor_nombre ?? null),
      codigo,
      unidad_base: nuevaRegla.unidad_base,
      precio:      nuevaRegla.precio !== '' ? parseFloat(nuevaRegla.precio) : null,
      tipo:        nuevaRegla.tipo,
      categoria:   nuevaRegla.categoria !== '' ? parseInt(nuevaRegla.categoria) : null,
      reemplaza_comun: esComun ? false : nuevaRegla.reemplaza_comun,
    }
    const onSuccess = () => {
      setNuevaRegla({ ...EMPTY_REGLA, reemplaza_comun: !esComun })
      setReglaCreada(codigo)
    }
    mutCrear(datos, {
      onSuccess,
      // Desde un grupo no sabemos qué finca falta: el diálogo solo ofrece
      // "Sumar igual" o "Cancelar".
      onError: err => onSolapamiento(err, { datos, onSuccess, mutate: mutCrear, fincaNueva: null }),
    })
  }
```

En cada uso de `<GrupoCard ... />` (grep `mutCrear={mutCrear}` dentro del render de tabs 1-4, ~línea 1207), agregar:

```jsx
                onSolapamiento={manejarErrorCrear}
```

- [ ] **Step 5: `handleCrearNuevo`**

Reemplazar la llamada `mutCrear({...}, { onSuccess: ... })` por:

```jsx
    const datos = {
      quincena,
      tarea_nombre:   formNuevo.tarea_nombre,
      cliente_nombre: (alcanceNuevo === 'cliente' || alcanceNuevo === 'finca') ? formNuevo.cliente_nombre : null,
      finca_nombre:   alcanceNuevo === 'finca' ? (formNuevo.finca_nombre || null) : null,
      supervisor_nombre: alcanceNuevo === 'supervisor' ? formNuevo.supervisor_nombre : null,
      codigo,
      unidad_base: formNuevo.unidad_base,
      precio:      formNuevo.precio !== '' ? parseFloat(formNuevo.precio) : null,
      tipo:        formNuevo.tipo,
      categoria:   formNuevo.categoria !== '' ? parseInt(formNuevo.categoria) : null,
      reemplaza_comun: alcanceNuevo === 'comun' ? false : formNuevo.reemplaza_comun,
    }
    const onSuccess = () => {
      // Conserva tarea/cliente/finca/supervisor y el alcance; limpia lo demás.
      setFormNuevo(f => ({ ...f, codigo: '', precio: '', categoria: '' }))
      setReglaCreadaNuevo(codigo)
    }
    mutCrear(datos, {
      onSuccess,
      onError: err => manejarErrorCrear(err, { datos, onSuccess, mutate: mutCrear, fincaNueva: null }),
    })
```

- [ ] **Step 6: Renderizar el diálogo**

Al final del JSX de `Conceptos()`, justo antes del `</div>` de cierre de `styles.page`:

```jsx
      {pendienteSolap && (
        <DialogoSolapamiento
          solapamiento={pendienteSolap.solapamiento}
          candidato={{
            codigo: pendienteSolap.datos.codigo,
            precio: pendienteSolap.datos.precio,
            categoria: pendienteSolap.datos.categoria,
            finca_nombre: pendienteSolap.datos.finca_nombre,
          }}
          fincaNueva={pendienteSolap.fincaNueva}
          onCrearSoloFinca={pendienteSolap.fincaNueva ? crearSoloFinca : null}
          onSumarIgual={sumarIgual}
          onCancelar={cerrarSolap}
        />
      )}
```

- [ ] **Step 7: Build y verificación manual del encadenado**

Run: `npm run build`
Expected: sin errores.

Verificación de lógica (leer el código, no ejecutar): en `FilaFaltante`, tras "Sumar igual" o "Crear solo para la finca", `onSuccess` es el mismo `() => setReglaCreada(codigo)` original, así que el prompt "¿Crear otra regla?" aparece igual y la siguiente alta vuelve a pasar por `handleGuardar` → nuevo 409 si corresponde. Eso cumple la decisión 8 ("el diálogo sale en cada alta").

- [ ] **Step 8: Commit**

```bash
git add src/pages/Conceptos.jsx
git commit -m "feat(conceptos): diálogo de solapamiento en faltantes, grupos y + Nuevo; crear solo para la finca por defecto

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B4: Franja de solapamientos vigentes + toast de copia

**Files:**
- Modify: `src/pages/Conceptos.jsx`: imports (línea ~6), queries (~712), `invalidar` (~748), mutation `copiar` (~809), JSX debajo de la topbar (~985), nuevo componente `FranjaSolapamientos`.

**Interfaces:**
- Consumes: `listarSolapamientos` (B1), query key nueva `['solapamientos', quincena]`.
- Produces: componente `FranjaSolapamientos({ items, onVerReglas })`; `onVerReglas(item)` recibe un Solapamiento y navega a la solapa "Por cliente" con la búsqueda cargada con la tarea.

- [ ] **Step 1: Import y query**

Agregar `listarSolapamientos` al import de `../services/preliquidacion` (línea ~6).

Junto a la query de faltantes (~línea 712):

```jsx
  const { data: solapamientos = [] } = useQuery({
    queryKey: ['solapamientos', quincena],
    queryFn: () => listarSolapamientos(quincena),
    enabled: !!quincena,
  })
```

- [ ] **Step 2: Invalidación**

En `invalidar()`, agregar:

```jsx
    qc.invalidateQueries({ queryKey: ['solapamientos'] })
```

Y en el `onSuccess` de `mutCrearSinFaltantes` (que no llama a `invalidar`), agregar la misma línea.

- [ ] **Step 3: Toast de la copia**

Reemplazar el `onSuccess` de la mutation `copiar`:

```jsx
    onSuccess: data => {
      toast.success(data.detalle || 'Copiado')
      if (data.solapamientos_heredados > 0) {
        const n = data.solapamientos_heredados
        toast(`Atención: ${n} solapamiento${n === 1 ? '' : 's'} por cliente heredado${n === 1 ? '' : 's'}. Revisá la franja de aviso.`,
          { icon: '⚠', duration: 8000 })
      }
      setMostrarCopiar(false); setQuincenaOrigen(''); invalidar()
    },
```

- [ ] **Step 4: Componente `FranjaSolapamientos`**

Antes de `function DialogoSolapamiento`:

```jsx
// ─── FranjaSolapamientos: aviso persistente de solapamientos por cliente ─────
//
// Solo se renderiza cuando hay al menos uno. Un solapamiento es una
// anomalía, no trabajo cotidiano: no merece solapa propia.
function FranjaSolapamientos({ items, onVerReglas }) {
  const [abierta, setAbierta] = useState(true)
  if (!items.length) return null
  const n = items.length
  return (
    <div className={styles.franjaSolap} role="alert">
      <div className={styles.franjaSolapHead} onClick={() => setAbierta(o => !o)}>
        <span>⚠ Esta quincena tiene {n} solapamiento{n === 1 ? '' : 's'} por cliente que suma{n === 1 ? '' : 'n'}</span>
        <span>{abierta ? '▲' : '▼'}</span>
      </div>
      {abierta && items.map(s => (
        <div key={`${s.tarea_nombre}|${s.cliente_nombre}`} className={styles.franjaSolapItem}>
          <span>
            <b>{s.tarea_nombre}</b> · {s.cliente_nombre}: {s.reglas_por_cliente.length} regla(s) por cliente
            {' '}+ {s.especificos.length} específica(s) en {s.fincas.join(', ')} · <b>{s.lineas_afectadas}</b> línea(s)
            {s.codigos_coincidentes.length > 0 && (
              <span className={styles.mismoCodigo}> · mismo código {s.codigos_coincidentes.join(', ')}: cobran DOS VECES</span>
            )}
          </span>
          <button className="btn btn-sm" onClick={() => onVerReglas(s)}>Ver reglas</button>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 5: Renderizar la franja y el "Ver reglas"**

En `Conceptos()`, debajo de `const cerrarSolap = ...`:

```jsx
  // "Ver reglas": va a la solapa Por cliente con la tarea en el buscador; las
  // específicas se ven cambiando a Por finca con la misma búsqueda.
  const verReglasSolap = (s) => {
    setTab(2)
    setBusqueda(s.tarea_nombre)
    setFiltrosEspecificos({})
    setMostrarNuevo(false)
    setReglaCreadaNuevo(null)
  }
```

En el JSX, inmediatamente después del bloque `{/* Panel copiar */} {mostrarCopiar && (...)}` y antes de `{/* Tabs */}`:

```jsx
      <FranjaSolapamientos items={solapamientos} onVerReglas={verReglasSolap} />
```

Nota: el cambio de solapa por los chips resetea `busqueda` a `''` (línea ~1011), pero `verReglasSolap` no pasa por ahí, así que la búsqueda queda cargada. Confirmar leyendo el código.

- [ ] **Step 6: Build**

Run: `npm run build`
Expected: sin errores.

- [ ] **Step 7: Commit**

```bash
git add src/pages/Conceptos.jsx
git commit -m "feat(conceptos): franja de solapamientos vigentes y aviso al copiar quincena

Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
```

---

### Task B5: Smoke real end-to-end y PR del frontend

**Files:** ninguno.

Precondición: backend de la rama `feature/solapamiento-por-cliente` corriendo local (`uvicorn app.main:app --reload` desde el repo backend) y front en `npm run dev`.

- [ ] **Step 1: Solo lectura**

1. Abrir Conceptos con la quincena actual. Expected: sin franja (la base no tiene solapamientos al 2026-09-04). Si aparece, anotar el contenido y reportarlo al usuario: es real.
2. DevTools → Network: confirmar la llamada `GET /api/precios/conceptos/solapamientos?quincena=...` → `200 []`.

- [ ] **Step 2: Alta de prueba que el usuario valide (crea datos reales; pedir OK antes)**

Elegir con el usuario una tarea+cliente que HOY tenga específicas (ideal: la misma del incidente, `ENANCHADOR BOLSONES HORAS - CARGA` / `CITRUSVIL`) y un código de prueba que el usuario indique.

1. Solapa "Por cliente" → "+ Nuevo" → alcance Por cliente → esa tarea y cliente → código y precio de prueba → Guardar.
   Expected: NO se crea; aparece el diálogo con las fincas específicas listadas, líneas afectadas > 0 si el código coincide con las específicas o "códigos distintos" si no. Botones: "Sumar igual a las N" (no enfocado) y "Cancelar" (enfocado). Apretar Escape → se cierra sin crear. Verificar en la solapa que no hay regla nueva.
2. Solapa "Sin concepto" (si hay alguna faltante de un cliente con específicas; si no, saltar): radio "Por cliente" → Guardar → diálogo con "Crear solo para {finca}" enfocado → Enter → se crea la ESPECÍFICA para esa finca (verificar en "Por finca"), aparece "¿Crear otra regla?". Si el usuario no quiere conservarla, borrarla desde "Por finca".
3. Con el OK explícito del usuario: repetir el paso 1 y apretar "Sumar igual". Expected: se crea la por cliente, `toast` "Regla guardada", y la franja ámbar aparece arriba con 1 ítem y "Ver reglas" lleva a Por cliente con la tarea en el buscador. Después **borrar esa regla** desde la solapa Por cliente y confirmar que la franja desaparece.

- [ ] **Step 3: Push y PR**

```bash
git push -u origin feature/solapamiento-por-cliente
```

Crear el PR con `gh` (ruta completa, `--body-file`) describiendo: interceptor con `status`/`detail`, diálogo de solapamiento en las 3 superficies con default seguro, franja vigente, toast de copia; depende del PR del backend. NO mergear ni deployar sin OK del usuario.

---

## Orden de ejecución y dependencias

- A0 → A1 → A2 → A3 → A4 → A5 (secuencial; cada task depende de la anterior).
- B0 → B1 → B2 → B3 → B4 → B5. B3 en adelante necesita el backend de A3/A4 corriendo para el smoke; el build no.
- A y B se pueden desarrollar en paralelo hasta B5. Para el deploy van **juntos**, con OK del usuario: el front nuevo sin backend nuevo degrada a lo de hoy (nunca ve un 409 ni la franja, y el GET de solapamientos da 404 silencioso en la query), pero el backend nuevo con el front viejo mostraría el 409 como un toast ilegible (el interceptor viejo convierte el `detail` objeto en texto). Si hay que elegir, primero el front y después el backend.

## Self-review (hecho al escribir)

- **Cobertura de decisiones:** 1-2 (sin cambio de matching, 409 confirmable) → A3. 3-5 (definición, código agravante, categoría) → A1/A2 con tests explícitos por cada regla. 6 (compuerta en POST, PATCH sin tocar) → A3. 7 (listado + franja + copia) → A4/B4. 8 (botones y default, encadenado) → B2/B3 Step 7. 9 (nota ADR) → A5.
- **Nombres consistentes:** `detectar_solapamiento_candidato`, `listar_solapamientos`, `categorias_compatibles`, `solapamientos_quincena`, `confirmar_solapamiento`, `solapamientos_heredados`, `DialogoSolapamiento`, `FranjaSolapamientos`, `manejarErrorCrear`, `pendienteSolap`, `listarSolapamientos`, query key `['solapamientos', quincena]`, `detail.tipo === 'solapamiento_por_cliente'` — mismos nombres en todas las tasks.
- **Riesgo conocido:** A3 Step 5 puede romper tests viejos que creaban solapamientos sin saberlo; la instrucción es confirmar en el test, no relajar la compuerta.
