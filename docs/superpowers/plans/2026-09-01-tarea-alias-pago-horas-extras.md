# Tarea Alias de Pago (Horas Extras de Taller) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** La tarea `MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)` paga exactamente con el maestro de conceptos de `MANTENIMIENTOS MECANICOS (TALLERES)` (mismas categorías, mismos precios, sin recargo), sin que el liquidador cargue ningún concepto nuevo — la línea conserva su nombre real para que la liquidación formal identifique las horas extras.

**Architecture:** Un diccionario hardcodeado `TAREAS_ALIAS_PAGO {alias → canónica}` (nombres normalizados) en `preliquidacion_service.py` + dos helpers puros (`tarea_canonica`, `tareas_que_pagan_como`). El alias se aplica en los DOS puntos donde se matchea el maestro (generación: `_buscar_conceptos_cache`; recálculo: bloque inline de `_aplicar_conceptos_a_lineas`), en sentido inverso en el impacto reactivo (`_lineas_por_match`) y en mantenimiento (`_tareas_con_categoria`). En el API de precios: 422 al crear conceptos para una tarea alias, faltantes mapea alias→canónica, y el catálogo de tareas del maestro oculta los alias. Solo backend; el frontend no se toca (el dropdown de tareas viene del backend).

**Tech Stack:** FastAPI, SQLAlchemy 2.0, pytest (SQLite in-memory).

**Spec:** `docs/adr/0012-tarea-alias-de-pago.md` + entrada "Tarea alias de pago" en `CONTEXT.md` (ambos ya escritos en esta rama, se committean en Task 0).

## Global Constraints

- Rama de trabajo: `feature/alias-horas-extras-taller` (ya creada desde main). NUNCA commitear en main.
- PROHIBIDO deployar al VPS o tocar producción. La base `preliquidacion` es dato real: solo lecturas.
- Tests: `python -m pytest tests/ -q` desde la raíz del backend. Deben pasar TODOS (hoy: 146).
- Sin migraciones de base: el mapeo vive en código.
- Los nombres del alias son EXACTOS del catálogo real (verificados 2026-09-01): alias `MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)`, canónica `MANTENIMIENTOS MECANICOS (TALLERES)`. Ojo: los tests viejos usan un nombre parecido pero distinto ("MANTENIMIENTO MECANICO (TALLERES)", singular) — es irrelevante, el matching de tests es agnóstico del nombre.
- Textos de error en español con tildes correctas. Código en español, snake_case.
- Commits terminan con:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

---

### Task 0: Commit de la documentación de diseño

**Files:**
- Ya modificados en el working tree: `CONTEXT.md` (entrada "Tarea alias de pago" + mención en "Matching"), `docs/adr/0012-tarea-alias-de-pago.md` (nuevo), `docs/superpowers/plans/2026-09-01-tarea-alias-pago-horas-extras.md` (este plan).

**Interfaces:**
- Produces: baseline documental committeada para que los diffs de código queden limpios.

- [ ] **Step 1: Verificar que la rama es la correcta y committear**

```bash
git branch --show-current   # debe decir: feature/alias-horas-extras-taller
git add CONTEXT.md docs/adr/0012-tarea-alias-de-pago.md docs/superpowers/plans/2026-09-01-tarea-alias-pago-horas-extras.md
git commit -m "docs: ADR-0012 tarea alias de pago (horas extras de taller) + glosario y plan

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 1: Constante + helpers + alias en los dos paths de matching

**Files:**
- Modify: `app/services/preliquidacion_service.py` (constante y helpers junto a `EMPLEADOS_MENSUALIZADOS` ~línea 23; `_buscar_conceptos_cache` ~línea 324; loop de `_aplicar_conceptos_a_lineas` ~línea 529)
- Test: `tests/test_tarea_alias_pago.py` (nuevo)

**Interfaces:**
- Consumes: nada nuevo.
- Produces (usado por Tasks 2, 3, 4):
  - `TAREAS_ALIAS_PAGO: dict[str, str]` — claves y valores NORMALIZADOS (upper/trim), módulo `app.services.preliquidacion_service`.
  - `tarea_canonica(nombre: str | None) -> str` — normaliza y traduce alias→canónica (identidad si no es alias).
  - `tareas_que_pagan_como(tareas_normalizadas) -> list[str]` — expande un iterable de tareas canónicas normalizadas con sus alias (sentido inverso), devuelve lista ordenada sin duplicados.

- [ ] **Step 1: Escribir los tests que fallan**

Crear `tests/test_tarea_alias_pago.py`:

```python
from datetime import date
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.database import Base
from app.models.models import (
    Preliquidacion, PreliquidacionLinea, ConceptoLiquidacion,
    UnidadBaseConcepto, TipoConcepto,
)
from app.services.preliquidacion_service import (
    PreliquidacionService, TAREAS_ALIAS_PAGO, tarea_canonica, tareas_que_pagan_como,
)

TAREA_ALIAS = "MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)"
TAREA_CANONICA = "MANTENIMIENTOS MECANICOS (TALLERES)"


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _preliq(db, quincena=date(2026, 5, 1)):
    p = Preliquidacion(quincena=quincena, creado_por=1)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _linea(db, preliq, tarea, cliente="CLIENTE A", finca="FINCA 1",
           cuil="20111111119", hsjornal=Decimal("8")):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        nombre_tarea=tarea, nombre_cliente=cliente, nombre_finca=finca,
        cuit=cuil,
        hsjornal=hsjornal, tancadas=Decimal("0"), unidades=Decimal("0"),
        hsmaquina=Decimal("0"),
        importe_total=Decimal("0"), linea_incompleta=True,
    )
    db.add(l)
    db.commit()
    db.refresh(l)
    return l


def _concepto(db, quincena, tarea, cliente=None, finca=None, codigo=1,
              precio=Decimal("100"), unidad=UnidadBaseConcepto.HSJORNAL,
              categoria=None):
    c = ConceptoLiquidacion(
        quincena=quincena, tarea_nombre=tarea, cliente_nombre=cliente,
        finca_nombre=finca, codigo=codigo, unidad_base=unidad, precio=precio,
        tipo=TipoConcepto.OTRO, categoria=categoria,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _match(c):
    return {
        "tarea_nombre": c.tarea_nombre, "cliente_nombre": c.cliente_nombre,
        "finca_nombre": c.finca_nombre, "supervisor_nombre": c.supervisor_nombre,
    }


# ─── Helpers puros ───────────────────────────────────────────────────────────

def test_tarea_canonica_traduce_el_alias():
    assert tarea_canonica(TAREA_ALIAS) == TAREA_CANONICA
    assert tarea_canonica("  " + TAREA_ALIAS.lower() + " ") == TAREA_CANONICA
    assert tarea_canonica("COSECHA LIMON") == "COSECHA LIMON"
    assert tarea_canonica(None) == ""


def test_tareas_que_pagan_como_expande_el_inverso():
    assert tareas_que_pagan_como([TAREA_CANONICA]) == sorted(
        {TAREA_CANONICA, TAREA_ALIAS}
    )
    assert tareas_que_pagan_como(["COSECHA LIMON"]) == ["COSECHA LIMON"]
    assert tareas_que_pagan_como([]) == []


def test_el_mapa_esta_normalizado():
    for alias, canonica in TAREAS_ALIAS_PAGO.items():
        assert alias == alias.strip().upper()
        assert canonica == canonica.strip().upper()
        assert canonica not in TAREAS_ALIAS_PAGO  # sin cadenas alias→alias


# ─── Path de recálculo (_aplicar_conceptos_a_lineas) ─────────────────────────

def test_linea_alias_paga_con_el_comun_de_la_canonica(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, TAREA_ALIAS)
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))

    PreliquidacionService(db).recalcular_por_concepto(
        preliq.quincena, actual=_match(c))

    db.refresh(linea)
    assert linea.linea_incompleta is False
    assert linea.importe_total == Decimal("800")  # 8 hs × $100
    assert linea.nombre_tarea == TAREA_ALIAS      # el nombre real NO se toca


def test_linea_de_otra_tarea_no_se_contamina(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, "COSECHA LIMON")
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))

    PreliquidacionService(db).recalcular_por_concepto(
        preliq.quincena, actual=_match(c))

    db.refresh(linea)
    assert linea.linea_incompleta is True
    assert linea.importe_total == Decimal("0")


# ─── Path de generación (_buscar_conceptos_cache) ────────────────────────────

def test_buscar_conceptos_cache_resuelve_el_alias(db):
    preliq = _preliq(db)
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))
    svc = PreliquidacionService(db)
    comunes, por_cliente, especificos, por_supervisor = \
        svc._cache_conceptos_quincena(preliq.quincena)
    cache = {
        "comunes": comunes, "por_cliente": por_cliente,
        "especificos": especificos, "por_supervisor": por_supervisor,
        "categoria_por_cuil": {},
    }

    reglas = svc._buscar_conceptos_cache(TAREA_ALIAS, "CLIENTE A", "FINCA 1",
                                         cache, cuil="20111111119")
    assert [r.id for r in reglas] == [c.id]
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_tarea_alias_pago.py -q`
Expected: FAIL con `ImportError: cannot import name 'TAREAS_ALIAS_PAGO'`.

- [ ] **Step 3: Implementar constante, helpers y los dos puntos de matching**

En `app/services/preliquidacion_service.py`, inmediatamente después de la lista `EMPLEADOS_MENSUALIZADOS` (~línea 23-30):

```python
# ADR-0012: tareas alias de pago. La clave (alias) existe solo para IDENTIFICAR
# un subconjunto de horas de su canónica (el valor); paga exactamente con el
# maestro de la canónica. Ambos lados NORMALIZADOS (upper/trim). Nombres
# exactos del catálogo de campo.
TAREAS_ALIAS_PAGO = {
    "MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)":
        "MANTENIMIENTOS MECANICOS (TALLERES)",
}


def tarea_canonica(nombre) -> str:
    """Nombre normalizado de la tarea con la que PAGA una línea (ADR-0012):
    la propia, salvo que sea un alias de pago."""
    t = (nombre or "").strip().upper()
    return TAREAS_ALIAS_PAGO.get(t, t)


def tareas_que_pagan_como(tareas_normalizadas) -> list:
    """Sentido inverso del alias: dado un conjunto de tareas canónicas
    (normalizadas), agrega los alias que pagan con ellas. Para expandir
    búsquedas de líneas afectadas por reglas del maestro."""
    base = set(tareas_normalizadas)
    return sorted(base | {a for a, c in TAREAS_ALIAS_PAGO.items() if c in base})
```

En `_buscar_conceptos_cache` (~línea 324), reemplazar:

```python
        t   = tarea.strip().upper()
```

por:

```python
        t   = tarea_canonica(tarea)  # ADR-0012: un alias paga con su canónica
```

En el loop de `_aplicar_conceptos_a_lineas` (~línea 529), reemplazar:

```python
            t   = (linea.nombre_tarea       or "").strip().upper()
```

por:

```python
            t   = tarea_canonica(linea.nombre_tarea)  # ADR-0012
```

(`tarea_canonica` es función de módulo — no necesita import dentro del service.)

- [ ] **Step 4: Correr los tests del archivo nuevo**

Run: `python -m pytest tests/test_tarea_alias_pago.py -q`
Expected: PASS todos. (El caso de precio por categoría se testea en Task 3: depende del fix de `_tareas_con_categoria`.)

- [ ] **Step 5: Correr TODA la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS completo (146 preexistentes + los nuevos).

- [ ] **Step 6: Commit**

```bash
git add app/services/preliquidacion_service.py tests/test_tarea_alias_pago.py
git commit -m "feat(alias): tarea alias de pago en los dos paths de matching (ADR-0012)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: Impacto reactivo inverso (editar la canónica recalcula las líneas alias)

**Files:**
- Modify: `app/services/preliquidacion_service.py` (`_lineas_por_match`, ~línea 589-599)
- Test: `tests/test_tarea_alias_pago.py`

**Interfaces:**
- Consumes: `tareas_que_pagan_como` (Task 1).
- Produces: `_lineas_por_match` devuelve también las líneas cuya tarea es alias de la tarea de la regla. Firma intacta.

- [ ] **Step 1: Escribir el test que falla**

Agregar al final de `tests/test_tarea_alias_pago.py`:

```python
# ─── Impacto reactivo inverso ────────────────────────────────────────────────

def test_editar_concepto_de_la_canonica_recalcula_la_linea_alias(db):
    preliq = _preliq(db)
    linea_alias = _linea(db, preliq, TAREA_ALIAS)
    linea_canon = _linea(db, preliq, TAREA_CANONICA, cuil="20222222227")
    c = _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
                  precio=Decimal("100"))

    svc = PreliquidacionService(db)
    r = svc.recalcular_por_concepto(preliq.quincena, actual=_match(c))
    assert r["lineas_afectadas"] == 2  # la canónica Y la alias

    c.precio = Decimal("200")
    db.commit()
    svc.recalcular_por_concepto(preliq.quincena, actual=_match(c))

    db.refresh(linea_alias)
    db.refresh(linea_canon)
    assert linea_alias.importe_total == Decimal("1600")  # 8 × 200
    assert linea_canon.importe_total == Decimal("1600")
```

- [ ] **Step 2: Correr el test y verificar que falla**

Run: `python -m pytest tests/test_tarea_alias_pago.py::test_editar_concepto_de_la_canonica_recalcula_la_linea_alias -q`
Expected: FAIL en `assert r["lineas_afectadas"] == 2` (da 1: la línea alias no se encuentra).

- [ ] **Step 3: Implementar**

En `_lineas_por_match` (~línea 595-599), reemplazar:

```python
        t = (tarea_nombre or "").strip().upper()
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            func.upper(func.trim(PreliquidacionLinea.nombre_tarea)) == t,
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()
```

por:

```python
        # ADR-0012: una regla de la canónica también afecta a sus tareas alias.
        tareas = tareas_que_pagan_como([(tarea_nombre or "").strip().upper()])
        lineas = self.db.query(PreliquidacionLinea).filter(
            PreliquidacionLinea.preliquidacion_id == preliq_id,
            func.upper(func.trim(PreliquidacionLinea.nombre_tarea)).in_(tareas),
        ).options(joinedload(PreliquidacionLinea.conceptos)).all()
```

- [ ] **Step 4: Correr TODA la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS completo.

- [ ] **Step 5: Commit**

```bash
git add app/services/preliquidacion_service.py tests/test_tarea_alias_pago.py
git commit -m "feat(alias): el impacto reactivo de la canónica alcanza a las líneas alias

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Mantenimiento — las líneas alias son líneas de taller

**Files:**
- Modify: `app/services/preliquidacion_service.py` (`_tareas_con_categoria`, ~línea 643-651)
- Test: `tests/test_tarea_alias_pago.py`

**Interfaces:**
- Consumes: `tareas_que_pagan_como` (Task 1).
- Produces: `_tareas_con_categoria` incluye los alias de las tareas con categoría. Beneficia sin más cambios a `operarios_mantenimiento` (~línea 691), `recalcular_por_categoria` (~línea 666) y el tercer uso (~línea 803).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_tarea_alias_pago.py`:

```python
# ─── Mantenimiento: líneas alias = líneas de taller ─────────────────────────

def test_persona_con_solo_horas_extras_aparece_en_operarios(db):
    preliq = _preliq(db)
    _linea(db, preliq, TAREA_ALIAS, cuil="20111111119")
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("100"), categoria=3)

    ops = PreliquidacionService(db).operarios_mantenimiento(preliq.id)
    assert [o["cuil"] for o in ops] == ["20111111119"]


def test_cambiar_categoria_recalcula_la_linea_alias(db):
    preliq = _preliq(db)
    linea = _linea(db, preliq, TAREA_ALIAS, cuil="20111111119")
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("100"), categoria=3)
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("250"), categoria=4)

    svc = PreliquidacionService(db)
    svc.set_categoria_operario(preliq.id, "20111111119", 3)
    db.refresh(linea)
    assert linea.importe_total == Decimal("800")   # 8 × 100

    svc.set_categoria_operario(preliq.id, "20111111119", 4)
    db.refresh(linea)
    assert linea.importe_total == Decimal("2000")  # 8 × 250
```

Nota: si el asserts de `ops` falla por la forma del dict (clave `cuil` vs otra), leer `operarios_mantenimiento` (~línea 700-720) y ajustar la clave del test al campo real — el test debe verificar que la persona APARECE, no la forma exacta.

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_tarea_alias_pago.py -q -k "operarios or cambiar_categoria"`
Expected: FAIL — la persona no aparece / el importe no cambia (la tarea alias no está en `_tareas_con_categoria`).

- [ ] **Step 3: Implementar**

En `_tareas_con_categoria` (~línea 651), reemplazar:

```python
        return [r[0].strip().upper() for r in rows if r[0]]
```

por:

```python
        # ADR-0012: las tareas alias de una tarea de taller también son taller.
        return tareas_que_pagan_como([r[0].strip().upper() for r in rows if r[0]])
```

- [ ] **Step 4: Correr TODA la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS completo.

- [ ] **Step 5: Commit**

```bash
git add app/services/preliquidacion_service.py tests/test_tarea_alias_pago.py
git commit -m "feat(alias): las líneas de horas extras cuentan como taller en Mantenimiento

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: API de precios — bloqueo 422, faltantes mapeados y catálogo sin alias

**Files:**
- Modify: `app/api/precios.py` (`crear_concepto` ~línea 274; `conceptos_faltantes` ~línea 434; `listar_tareas` ~línea 61)
- Test: `tests/test_tarea_alias_pago.py`

**Interfaces:**
- Consumes: `TAREAS_ALIAS_PAGO`, `tarea_canonica` (Task 1) — importar desde `app.services.preliquidacion_service`.
- Produces:
  - `crear_concepto` levanta `HTTPException(422)` si `tarea_canonica(datos.tarea_nombre) != datos.tarea_nombre.strip().upper()` (es decir, la tarea es un alias). `actualizar_concepto` NO se toca: `ConceptoUnifUpdateRequest` no permite cambiar `tarea_nombre`, y ningún concepto existente puede tener una tarea alias (la creación está bloqueada).
  - `conceptos_faltantes` trata las líneas alias como líneas de la canónica: matchean contra los conceptos de la canónica y, si falta, el combo se lista con el NOMBRE DE LA CANÓNICA (así el atajo "crear regla desde faltante" del frontend crea la regla correcta).
  - `listar_tareas` filtra del catálogo las tareas alias (el liquidador no puede elegirlas en el maestro).

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_tarea_alias_pago.py`:

```python
# ─── API de precios ──────────────────────────────────────────────────────────

from fastapi import HTTPException
from app.api.precios import crear_concepto, conceptos_faltantes
from app.schemas.schemas import ConceptoUnifRequest


def test_crear_concepto_para_tarea_alias_da_422(db):
    datos = ConceptoUnifRequest(
        quincena=date(2026, 5, 1), tarea_nombre=TAREA_ALIAS,
        codigo=50, precio=Decimal("100"),
        unidad_base=UnidadBaseConcepto.HSJORNAL,
    )
    with pytest.raises(HTTPException) as exc:
        crear_concepto(datos, db)
    assert exc.value.status_code == 422
    assert TAREA_CANONICA in exc.value.detail


def test_faltantes_muestra_el_combo_alias_como_canonica(db):
    preliq = _preliq(db)
    _linea(db, preliq, TAREA_ALIAS, cliente="CLIENTE A", finca="FINCA 1")

    faltantes = conceptos_faltantes(preliq.quincena, db)
    assert {(f["tarea_nombre"], f["cliente_nombre"]) for f in faltantes} == {
        (TAREA_CANONICA, "CLIENTE A")
    }


def test_faltantes_no_lista_el_alias_si_la_canonica_tiene_concepto(db):
    preliq = _preliq(db)
    _linea(db, preliq, TAREA_ALIAS, cliente="CLIENTE A", finca="FINCA 1")
    _concepto(db, preliq.quincena, TAREA_CANONICA, codigo=50,
              precio=Decimal("100"))

    faltantes = conceptos_faltantes(preliq.quincena, db)
    assert faltantes == []
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_tarea_alias_pago.py -q -k "crear_concepto or faltantes"`
Expected: FAIL — no hay 422, y faltantes lista el combo con el nombre del alias.

- [ ] **Step 3: Implementar el bloqueo 422**

En `app/api/precios.py`, agregar al import de servicios (~línea 11):

```python
from app.services.preliquidacion_service import (
    PreliquidacionService, TAREAS_ALIAS_PAGO, tarea_canonica,
)
```

Debajo de `_validar_cliente_xor_supervisor` (~línea 36), agregar:

```python
def _validar_tarea_no_alias(tarea_nombre: str):
    """ADR-0012: una tarea alias de pago no existe para el maestro."""
    t = (tarea_nombre or "").strip().upper()
    canonica = tarea_canonica(t)
    if canonica != t:
        raise HTTPException(
            status_code=422,
            detail=f"La tarea '{t}' es solo para identificar horas: paga "
                   f"automáticamente con los conceptos de '{canonica}'. "
                   f"Cargá el concepto en esa tarea.",
        )
```

En `crear_concepto` (~línea 274), como primera línea del cuerpo:

```python
    _validar_tarea_no_alias(datos.tarea_nombre)
```

- [ ] **Step 4: Implementar el mapeo en faltantes**

En `conceptos_faltantes` (~línea 434): el SQL compara `cl.tarea_nombre = pl.nombre_tarea` y devuelve `pl.nombre_tarea`. Construir un CASE dinámico desde la constante (hoy 1 par, pero sin hardcodear el par en el SQL):

```python
    # ADR-0012: las líneas de una tarea alias faltan/matchean como su canónica.
    casos = " ".join(
        f"WHEN UPPER(TRIM(pl.nombre_tarea)) = :alias_{i} THEN :canon_{i}"
        for i in range(len(TAREAS_ALIAS_PAGO))
    )
    tarea_pago = f"CASE {casos} ELSE pl.nombre_tarea END" if casos else "pl.nombre_tarea"
    params = {"quincena": quincena}
    for i, (alias, canon) in enumerate(sorted(TAREAS_ALIAS_PAGO.items())):
        params[f"alias_{i}"] = alias
        params[f"canon_{i}"] = canon

    rows = db.execute(text(f"""
        SELECT DISTINCT
            {tarea_pago} AS nombre_tarea,
            pl.nombre_cliente,
            pl.nombre_finca
        FROM preliquidacion_linea pl
        INNER JOIN preliquidacion p ON p.id = pl.preliquidacion_id
        WHERE p.quincena = :quincena
          AND NOT EXISTS (
              SELECT 1 FROM concepto_liquidacion cl
              WHERE cl.quincena = :quincena
                AND UPPER(TRIM(cl.tarea_nombre)) = UPPER(TRIM({tarea_pago}))
                AND cl.codigo IS NOT NULL
                AND cl.precio IS NOT NULL
                AND (
                    (cl.cliente_nombre IS NULL AND cl.supervisor_nombre IS NULL)
                    OR (cl.cliente_nombre = pl.nombre_cliente
                        AND (cl.finca_nombre IS NULL
                             OR cl.finca_nombre = pl.nombre_finca))
                    OR (cl.supervisor_nombre IS NOT NULL
                        AND UPPER(TRIM(cl.supervisor_nombre)) =
                            UPPER(TRIM(COALESCE(pl.nombre_supervisor, ''))))
                )
          )
        ORDER BY nombre_tarea, pl.nombre_cliente, pl.nombre_finca
    """), params).fetchall()
```

Nota: el único cambio semántico respecto del SQL actual es `{tarea_pago}` en el SELECT y en el JOIN del NOT EXISTS (con la comparación de tarea normalizada con UPPER/TRIM en ambos lados, que además corrige un case-mismatch latente). El resto del WHERE queda idéntico. El `f-string` es seguro: `{tarea_pago}` se construye solo desde la constante propia, los valores van como parámetros bind.

- [ ] **Step 5: Implementar el filtro del catálogo de tareas**

En `listar_tareas` (~línea 61), filtrar los alias del resultado:

```python
@router.get("/maestro/tareas")
def listar_tareas(db_externa: Session = Depends(get_db_externa)):
    tareas = ConsultaExternaService(db_externa).obtener_tareas()
    # ADR-0012: las tareas alias de pago no existen para el maestro.
    return [
        t for t in tareas
        if str(t.get("nombre", "")).strip().upper() not in TAREAS_ALIAS_PAGO
    ]
```

(Ajustar el nombre del campo si el decorator/cuerpo actual difiere — conservar el path y el response actual, solo agregar el filtro.)

- [ ] **Step 6: Correr TODA la suite**

Run: `python -m pytest tests/ -q`
Expected: PASS completo.

- [ ] **Step 7: Commit**

```bash
git add app/api/precios.py tests/test_tarea_alias_pago.py
git commit -m "feat(alias): la tarea alias no existe para el maestro (422, faltantes, catálogo)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: README, verificación final y PR

**Files:**
- Modify: `README.md` (sección "Reglas de negocio clave")

**Interfaces:**
- Consumes: todo lo anterior.

- [ ] **Step 1: Documentar la regla en el README**

En `README.md`, en la lista de "Reglas de negocio clave", agregar después del bullet de "Mantenimiento mecánico":

```markdown
- **Tarea alias de pago** (ADR-0012): `MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)` existe solo para identificar horas extras de taller; paga automáticamente con el maestro de `MANTENIMIENTOS MECANICOS (TALLERES)` (mismas categorías y precios, sin recargo). No aparece en faltantes ni admite conceptos propios; la línea conserva su nombre real en Revisión y en el Excel.
```

- [ ] **Step 2: Correr TODA la suite una última vez**

Run: `python -m pytest tests/ -q`
Expected: PASS completo.

- [ ] **Step 3: Smoke con datos reales (SOLO LECTURA)**

Con la base real (sin escribir nada):

```bash
python -c "
from app.core.database import SessionPropia
from sqlalchemy import text
s = SessionPropia()
r = s.execute(text(\"SELECT COUNT(*) FROM preliquidacion_linea WHERE UPPER(TRIM(nombre_tarea)) = 'MANTENIMIENTOS MECANICOS HORAS GUARDIA (TALLERES)'\")).scalar()
print('lineas alias en base:', r)
s.close()"
```

Expected: `lineas alias en base: 0` (al 2026-09-01 no había ninguna — si aparece alguna quincena nueva con líneas, anotarlo en el PR: al regenerar esa quincena van a pagar con el alias). Registrar el resultado en la descripción del PR.

- [ ] **Step 4: Push y PR (SIN mergear — el usuario decide merge y deploy)**

```bash
git add README.md
git commit -m "docs(readme): regla de tarea alias de pago (ADR-0012)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
git push -u origin feature/alias-horas-extras-taller
```

Crear el PR con `& "$env:ProgramFiles\GitHub CLI\gh.exe" pr create --title "feat: tarea alias de pago — horas extras de taller (ADR-0012)" --body-file <archivo temporal>` (PowerShell; el body inline puede ser bloqueado). El body resume: qué es el alias, las 4 zonas tocadas (matching ×2, reactivo inverso, mantenimiento, API precios), sin migraciones, resultado del smoke, y que NO se deploya sin OK explícito.
