# Vista Gerencial: Indicadores de Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Agregar a la vista gerencial (control post-cierre) la descomposición de la variación (dotación / actividad / precio), los KPIs $/hora jornal y % adicionales, y los desvíos por cliente contra su media histórica.

**Architecture:** Se extiende `GerencialService` (backend FastAPI + SQLAlchemy, agregaciones sobre `preliquidacion_linea`) con un endpoint nuevo `/api/gerencial/indicadores` y otro `/api/gerencial/desvios-cliente`. El frontend (React + react-query) agrega dos tiles KPI, un panel "¿Por qué varió?" y una tabla de desvíos por cliente en `Gerencial.jsx`, reutilizando los componentes y estilos existentes (BarraDesvio, clases de Gerencial.module.css).

**Tech Stack:** FastAPI, SQLAlchemy, pytest (sqlite in-memory); React 18, @tanstack/react-query, CSS Modules, SVG inline.

**Spec:** Diseño aprobado en conversación (2026-08-17): (1) descomposición de variación total = efecto dotación + efecto actividad + efecto precio vs período anterior; (2) KPIs $/hora jornal y % adicionales (importe_total − importe_base); (3) desvíos por cliente con la misma ventana histórica que los desvíos por persona (6 quincenas, mínimo 3).

## Global Constraints

- Repos: backend `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion`, frontend `C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion` (repo git separado).
- Rama de trabajo en AMBOS repos: `feature/gerencial-control-analitico` (crearla desde `main` antes de editar; NUNCA commitear en main).
- PROHIBIDO deployar al VPS o tocar producción. La base `preliquidacion` es dato real: solo lecturas.
- Tests backend: `python -m pytest tests/ -q` desde la raíz del backend. Deben pasar TODOS (no solo los nuevos).
- Frontend: no hay suite de tests; la verificación es `npm run build` sin errores + smoke test real al final.
- Textos de UI en español con tildes correctas. Código y nombres siguen el estilo existente (español, snake_case backend, camelCase frontend).
- La vista gerencial es SOLO LECTURA y accesible a roles admin/jefe/gerente (el router ya lo impone; los endpoints nuevos van en el mismo router).
- Convención de quincenas: día 1 = primera quincena, día 16 = segunda.
- Commits terminan con:
  `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`

## Fórmulas (referencia normativa para las tareas)

Sean período actual (1) y anterior (0): `T` = suma de `importe_total`, `P` = personas (CUIT distintos), `H` = suma de `coalesce(hsjornal, 0)`, `B` = suma de `coalesce(importe_base, 0)`.

- `costo_hora = T / H` (None si `H == 0`)
- `adicionales = T − B`; `adicionales_pct = adicionales / T × 100` (None si `T == 0`)
- Descomposición (atribución secuencial dotación → actividad → precio; suma exacta = `T1 − T0`). Solo se calcula si `T0>0 and P0>0 and H0>0 and P1>0 and H1>0`; si no, es `None`:
  - `hpp0 = H0/P0` (horas por persona), `cph0 = T0/H0` ($ por hora)
  - `efecto_dotacion = (P1 − P0) × hpp0 × cph0`
  - `efecto_actividad = (H1 − P1 × hpp0) × cph0`
  - `efecto_precio = T1 − H1 × cph0`
  - `pct` de cada efecto = `monto / T0 × 100`

---

### Task 0: Ramas de trabajo

**Files:** ninguno (solo git).

**Interfaces:**
- Produces: rama `feature/gerencial-control-analitico` activa en ambos repos.

- [ ] **Step 1: Crear rama en backend**

```bash
cd "C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\backend_preliquidacion"
git checkout main && git pull && git checkout -b feature/gerencial-control-analitico
```

- [ ] **Step 2: Crear rama en frontend**

```bash
cd "C:\Users\Administrador\Desktop\LA Gero\Sistema_Preliquidacion\frontend_preliquidacion"
git checkout main && git pull && git checkout -b feature/gerencial-control-analitico
```

- [ ] **Step 3: Verificar**

Run: `git branch --show-current` en ambos repos.
Expected: `feature/gerencial-control-analitico` en los dos.

---

### Task 1: Backend — método `indicadores` con métricas y descomposición

**Files:**
- Modify: `app/services/gerencial_service.py` (agregar `_metricas` y `indicadores` después de `_totales`, ~línea 126)
- Test: `tests/test_gerencial_kpis.py` (extender `_linea` y agregar tests al final)

**Interfaces:**
- Consumes: `_resolver_periodo`, `_periodo_anterior`, `_lineas_periodo` (existentes en `GerencialService`).
- Produces: `GerencialService.indicadores(quincena: date | None, mes: str | None, empresa: str | None) -> dict` con la forma:

```python
{
    "quincenas": ["2026-05-16"],
    "actual":   {"total": float, "personas": int, "lineas": int,
                 "horas_jornal": float, "costo_hora": float | None,
                 "adicionales": float, "adicionales_pct": float | None},
    "anterior": {..., "quincenas": [...]} | None,   # misma forma que actual
    "variaciones": {"total_pct": float | None,
                    "costo_hora_pct": float | None,
                    "adicionales_pct_puntos": float | None} | None,
    "descomposicion": {"dotacion":  {"monto": float, "pct": float},
                       "actividad": {"monto": float, "pct": float},
                       "precio":    {"monto": float, "pct": float}} | None,
}
```

- [ ] **Step 1: Extender el helper `_linea` del test con hsjornal e importe_base**

En `tests/test_gerencial_kpis.py`, reemplazar la firma y el cuerpo de `_linea` para aceptar los campos nuevos (default None, no rompe ningún test existente):

```python
def _linea(db, preliq, importe, cuil="20-11111111-1", nombre="JUAN",
           empresa="LA ASTURIANA", cliente="CLIENTE A", tarea="COSECHA LIMON",
           hsjornal=None, importe_base=None):
    l = PreliquidacionLinea(
        preliquidacion_id=preliq.id,
        cuit=cuil, nombre_empleado=nombre, empresa_asignada=empresa,
        nombre_cliente=cliente, nombre_finca="FINCA 1", nombre_tarea=tarea,
        importe_total=Decimal(str(importe)),
        hsjornal=Decimal(str(hsjornal)) if hsjornal is not None else None,
        importe_base=Decimal(str(importe_base)) if importe_base is not None else None,
    )
    db.add(l)
    db.commit()
    return l
```

- [ ] **Step 2: Escribir los tests que fallan**

Agregar al final de `tests/test_gerencial_kpis.py`:

```python
# ─── Indicadores de control ──────────────────────────────────────────────────

def test_indicadores_metricas_del_periodo(db):
    p = _preliq(db, Q_MAY_1)
    # 2 líneas: 10 hs a $100/h con base 900 (adicional 100), y una sin horas
    _linea(db, p, 1000, hsjornal=10, importe_base=900)
    _linea(db, p, 200, cuil="20-2", hsjornal=None, importe_base=200)

    r = GerencialService(db).indicadores(Q_MAY_1, None, None)
    a = r["actual"]
    assert a["total"] == 1200.0
    assert a["horas_jornal"] == 10.0
    assert a["costo_hora"] == 120.0          # 1200 / 10
    assert a["adicionales"] == 100.0         # 1200 - 1100
    assert a["adicionales_pct"] == 8.3       # 100/1200
    assert r["anterior"] is None
    assert r["variaciones"] is None
    assert r["descomposicion"] is None


def test_indicadores_sin_horas_costo_hora_none(db):
    p = _preliq(db, Q_MAY_1)
    _linea(db, p, 500)  # sin hsjornal
    r = GerencialService(db).indicadores(Q_MAY_1, None, None)
    assert r["actual"]["horas_jornal"] == 0.0
    assert r["actual"]["costo_hora"] is None


def test_indicadores_descomposicion_suma_exacta(db):
    # Anterior: 2 personas × 10 hs × $100/h = 2000
    p0 = _preliq(db, Q_MAY_1)
    _linea(db, p0, 1000, cuil="20-1", hsjornal=10, importe_base=1000)
    _linea(db, p0, 1000, cuil="20-2", hsjornal=10, importe_base=1000)
    # Actual: 3 personas × 12 hs × $110/h = 3960
    p1 = _preliq(db, Q_MAY_2)
    for c in ("20-1", "20-2", "20-3"):
        _linea(db, p1, 1320, cuil=c, hsjornal=12, importe_base=1320)

    r = GerencialService(db).indicadores(Q_MAY_2, None, None)
    d = r["descomposicion"]
    assert d["dotacion"]["monto"] == 1000.0    # (3-2) × 10 × 100
    assert d["actividad"]["monto"] == 600.0    # (36 - 30) × 100
    assert d["precio"]["monto"] == 360.0       # 3960 - 3600
    # suma exacta de la variación
    assert d["dotacion"]["monto"] + d["actividad"]["monto"] + d["precio"]["monto"] == 1960.0
    assert d["dotacion"]["pct"] == 50.0
    assert d["actividad"]["pct"] == 30.0
    assert d["precio"]["pct"] == 18.0
    v = r["variaciones"]
    assert v["total_pct"] == 98.0
    assert v["costo_hora_pct"] == 10.0         # 110 vs 100
    assert v["adicionales_pct_puntos"] == 0.0


def test_indicadores_descomposicion_none_sin_horas_previas(db):
    p0 = _preliq(db, Q_MAY_1)
    _linea(db, p0, 1000)                        # sin horas en el período anterior
    p1 = _preliq(db, Q_MAY_2)
    _linea(db, p1, 1200, hsjornal=10, importe_base=1200)

    r = GerencialService(db).indicadores(Q_MAY_2, None, None)
    assert r["anterior"] is not None
    assert r["descomposicion"] is None          # H0 == 0 → no explicable
    assert r["variaciones"]["total_pct"] == 20.0
    assert r["variaciones"]["costo_hora_pct"] is None
```

- [ ] **Step 3: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_gerencial_kpis.py -q -k indicadores`
Expected: FAIL con `AttributeError: ... no attribute 'indicadores'`.

- [ ] **Step 4: Implementar `_metricas` e `indicadores`**

En `app/services/gerencial_service.py`, después de `_totales` (línea ~126):

```python
    def _metricas(self, quincenas: list[date], empresa: str | None) -> dict:
        """Métricas de control del período: totales + horas + adicionales."""
        fila = (
            self._lineas_periodo(quincenas, empresa)
            .with_entities(
                func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
                func.count(func.distinct(PreliquidacionLinea.cuit)),
                func.count(PreliquidacionLinea.id),
                func.coalesce(func.sum(func.coalesce(PreliquidacionLinea.hsjornal, 0)), 0),
                func.coalesce(func.sum(func.coalesce(PreliquidacionLinea.importe_base, 0)), 0),
            )
            .one()
        )
        total, personas, lineas, horas, base = (
            float(fila[0]), int(fila[1]), int(fila[2]), float(fila[3]), float(fila[4])
        )
        adicionales = round(total - base, 2)
        return {
            "total": total,
            "personas": personas,
            "lineas": lineas,
            "horas_jornal": horas,
            "costo_hora": round(total / horas, 2) if horas > 0 else None,
            "adicionales": adicionales,
            "adicionales_pct": round(adicionales / total * 100, 1) if total > 0 else None,
        }

    def indicadores(self, quincena: date | None, mes: str | None, empresa: str | None) -> dict:
        """KPIs de control con comparación y descomposición de la variación
        (dotación → actividad → precio, atribución secuencial que suma exacto)."""
        quincenas = self._resolver_periodo(quincena, mes)
        actual = self._metricas(quincenas, empresa)

        anteriores = self._periodo_anterior(quincena, mes)
        anterior = self._metricas(anteriores, empresa) if anteriores else None

        variaciones = None
        descomposicion = None
        if anterior:
            t0, t1 = anterior["total"], actual["total"]
            variaciones = {
                "total_pct": round((t1 / t0 - 1) * 100, 1) if t0 > 0 else None,
                "costo_hora_pct": (
                    round((actual["costo_hora"] / anterior["costo_hora"] - 1) * 100, 1)
                    if actual["costo_hora"] and anterior["costo_hora"] else None
                ),
                "adicionales_pct_puntos": (
                    round(actual["adicionales_pct"] - anterior["adicionales_pct"], 1)
                    if actual["adicionales_pct"] is not None
                    and anterior["adicionales_pct"] is not None else None
                ),
            }
            p0, p1 = anterior["personas"], actual["personas"]
            h0, h1 = anterior["horas_jornal"], actual["horas_jornal"]
            if t0 > 0 and p0 > 0 and h0 > 0 and p1 > 0 and h1 > 0:
                hpp0 = h0 / p0   # horas por persona del período base
                cph0 = t0 / h0   # $ por hora del período base
                dotacion = (p1 - p0) * hpp0 * cph0
                actividad = (h1 - p1 * hpp0) * cph0
                precio = t1 - h1 * cph0
                descomposicion = {
                    clave: {"monto": round(monto, 2), "pct": round(monto / t0 * 100, 1)}
                    for clave, monto in (
                        ("dotacion", dotacion), ("actividad", actividad), ("precio", precio)
                    )
                }
            anterior = {**anterior, "quincenas": [str(q) for q in anteriores]}

        return {
            "quincenas": [str(q) for q in quincenas],
            "actual": actual,
            "anterior": anterior,
            "variaciones": variaciones,
            "descomposicion": descomposicion,
        }
```

- [ ] **Step 5: Correr los tests y verificar que pasan**

Run: `python -m pytest tests/test_gerencial_kpis.py -q`
Expected: PASS todos (los nuevos y los preexistentes).

- [ ] **Step 6: Commit**

```bash
git add app/services/gerencial_service.py tests/test_gerencial_kpis.py
git commit -m "feat(gerencial): indicadores de control con descomposición de la variación"
```

---

### Task 2: Backend — desvíos por cliente (refactor DRY del cálculo de desvíos)

**Files:**
- Modify: `app/services/gerencial_service.py` (refactor de `desvios_por_persona` líneas 251-317 + método nuevo)
- Test: `tests/test_gerencial_kpis.py`

**Interfaces:**
- Consumes: `_resolver_periodo`, constantes `VENTANA_HISTORICA`, `MINIMO_QUINCENAS_HISTORIA`, `UMBRAL_DESVIO_DEFAULT`.
- Produces: `GerencialService.desvios_por_cliente(quincena, mes, empresa, umbral_pct=UMBRAL_DESVIO_DEFAULT) -> dict` con la forma:

```python
{
    "umbral_pct": 30.0, "ventana_quincenas": 6, "minimo_quincenas": 3,
    "clientes": [{"cliente": str, "promedio_quincenal": float,
                  "quincenas_historia": int, "media_historica": float,
                  "desvio_pct": float | None, "supera_umbral": bool}],
    "sin_historial": [{"cliente": str, "promedio_quincenal": float,
                       "quincenas_historia": int}],
}
```

También produce el helper interno `_calcular_desvios(filas, quincenas_periodo, umbral_pct)` donde `filas` es un iterable de tuplas `(quincena, clave, etiqueta, total)`; devuelve `(comparables, sin_historial)` con entradas `{"clave", "etiqueta", "promedio_quincenal", "quincenas_historia", ...}`. `desvios_por_persona` DEBE seguir devolviendo exactamente la misma forma que hoy (claves `cuil`/`nombre`) — los tests existentes lo garantizan.

- [ ] **Step 1: Escribir los tests que fallan**

Agregar al final de `tests/test_gerencial_kpis.py`:

```python
# ─── Desvíos por cliente ─────────────────────────────────────────────────────

def test_desvios_cliente_contra_su_media(db):
    # Historia del CLIENTE A: 3 quincenas a 1000
    for q in (date(2026, 4, 1), date(2026, 4, 16), Q_MAY_1):
        _linea(db, _preliq(db, q), 1000, cliente="CLIENTE A")
    # Período actual: CLIENTE A gasta 1500 (+50%), CLIENTE B aparece nuevo
    p = _preliq(db, Q_MAY_2)
    _linea(db, p, 1500, cliente="CLIENTE A")
    _linea(db, p, 800, cuil="20-2", cliente="CLIENTE B")

    r = GerencialService(db).desvios_por_cliente(Q_MAY_2, None, None, umbral_pct=30.0)
    a = next(c for c in r["clientes"] if c["cliente"] == "CLIENTE A")
    assert a["promedio_quincenal"] == 1500.0
    assert a["media_historica"] == 1000.0
    assert a["desvio_pct"] == 50.0
    assert a["supera_umbral"] is True
    nuevos = [c["cliente"] for c in r["sin_historial"]]
    assert "CLIENTE B" in nuevos


def test_desvios_cliente_sin_cliente_agrupa(db):
    for q in (date(2026, 4, 1), date(2026, 4, 16), Q_MAY_1):
        _linea(db, _preliq(db, q), 500, cliente=None)
    p = _preliq(db, Q_MAY_2)
    _linea(db, p, 500, cliente=None)

    r = GerencialService(db).desvios_por_cliente(Q_MAY_2, None, None)
    assert [c["cliente"] for c in r["clientes"]] == ["SIN CLIENTE"]
    assert r["clientes"][0]["desvio_pct"] == 0.0
```

- [ ] **Step 2: Correr los tests y verificar que fallan**

Run: `python -m pytest tests/test_gerencial_kpis.py -q -k desvios_cliente`
Expected: FAIL con `AttributeError: ... no attribute 'desvios_por_cliente'`.

- [ ] **Step 3: Refactorizar el cálculo común y agregar el método nuevo**

En `gerencial_service.py`, extraer de `desvios_por_persona` (líneas 274-310 actuales) el helper genérico, y reescribir ambos métodos públicos:

```python
    def _calcular_desvios(self, filas, quincenas_periodo: set, umbral_pct: float):
        """Núcleo común de los desvíos. `filas`: (quincena, clave, etiqueta, total).
        Compara el promedio POR QUINCENA del período contra la media de las
        últimas VENTANA_HISTORICA quincenas con actividad (mínimo MINIMO_...)."""
        inicio_periodo = min(quincenas_periodo)
        acumulado: dict[str, dict] = {}
        for qcna, clave, etiqueta, total in filas:
            datos = acumulado.setdefault(clave, {"etiqueta": etiqueta, "actual": [], "historia": {}})
            datos["etiqueta"] = etiqueta or datos["etiqueta"]
            if qcna in quincenas_periodo:
                datos["actual"].append(float(total))
            elif qcna < inicio_periodo:
                datos["historia"][qcna] = float(total)

        comparables, sin_historial = [], []
        for clave, datos in acumulado.items():
            if not datos["actual"]:
                continue  # sin actividad en el período
            promedio_actual = sum(datos["actual"]) / len(datos["actual"])
            historia = [
                total for _, total in sorted(datos["historia"].items(), reverse=True)
            ][:VENTANA_HISTORICA]
            entrada = {
                "clave": clave,
                "etiqueta": datos["etiqueta"],
                "promedio_quincenal": round(promedio_actual, 2),
                "quincenas_historia": len(historia),
            }
            if len(historia) < MINIMO_QUINCENAS_HISTORIA:
                sin_historial.append(entrada)
                continue
            media = sum(historia) / len(historia)
            desvio = round((promedio_actual / media - 1) * 100, 1) if media > 0 else None
            entrada.update({
                "media_historica": round(media, 2),
                "desvio_pct": desvio,
                "supera_umbral": desvio is not None and desvio >= umbral_pct,
            })
            comparables.append(entrada)

        comparables.sort(key=lambda p: (p["desvio_pct"] is None, -(p["desvio_pct"] or 0)))
        sin_historial.sort(key=lambda p: -p["promedio_quincenal"])
        return comparables, sin_historial
```

`desvios_por_persona` queda como wrapper (misma respuesta pública que hoy):

```python
    def desvios_por_persona(
        self,
        quincena: date | None,
        mes: str | None,
        empresa: str | None,
        umbral_pct: float = UMBRAL_DESVIO_DEFAULT,
    ) -> dict:
        """Cada persona contra su propia media histórica (ver CONTEXT.md)."""
        quincenas_periodo = set(self._resolver_periodo(quincena, mes))
        q = self.db.query(
            Preliquidacion.quincena,
            PreliquidacionLinea.cuit,
            func.max(PreliquidacionLinea.nombre_empleado),
            func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
        ).join(PreliquidacionLinea)
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa)
        q = q.group_by(Preliquidacion.quincena, PreliquidacionLinea.cuit)

        comparables, sin_historial = self._calcular_desvios(q.all(), quincenas_periodo, umbral_pct)

        def _persona(e):
            e = {**e, "cuil": e.pop("clave"), "nombre": e.pop("etiqueta")}
            return e

        return {
            "umbral_pct": umbral_pct,
            "ventana_quincenas": VENTANA_HISTORICA,
            "minimo_quincenas": MINIMO_QUINCENAS_HISTORIA,
            "personas": [_persona(e) for e in comparables],
            "sin_historial": [_persona(e) for e in sin_historial],
        }
```

Y el método nuevo:

```python
    def desvios_por_cliente(
        self,
        quincena: date | None,
        mes: str | None,
        empresa: str | None,
        umbral_pct: float = UMBRAL_DESVIO_DEFAULT,
    ) -> dict:
        """Cada cliente contra su propia media histórica (misma ventana que
        los desvíos por persona). Líneas sin cliente caen en "SIN CLIENTE"."""
        quincenas_periodo = set(self._resolver_periodo(quincena, mes))
        q = self.db.query(
            Preliquidacion.quincena,
            func.coalesce(PreliquidacionLinea.nombre_cliente, "SIN CLIENTE"),
            func.coalesce(PreliquidacionLinea.nombre_cliente, "SIN CLIENTE"),
            func.coalesce(func.sum(PreliquidacionLinea.importe_total), 0),
        ).join(PreliquidacionLinea)
        if empresa:
            q = q.filter(PreliquidacionLinea.empresa_asignada == empresa)
        q = q.group_by(Preliquidacion.quincena, PreliquidacionLinea.nombre_cliente)

        comparables, sin_historial = self._calcular_desvios(q.all(), quincenas_periodo, umbral_pct)

        def _cliente(e):
            e = {**e, "cliente": e.pop("clave")}
            e.pop("etiqueta")
            return e

        return {
            "umbral_pct": umbral_pct,
            "ventana_quincenas": VENTANA_HISTORICA,
            "minimo_quincenas": MINIMO_QUINCENAS_HISTORIA,
            "clientes": [_cliente(e) for e in comparables],
            "sin_historial": [_cliente(e) for e in sin_historial],
        }
```

Eliminar del cuerpo viejo de `desvios_por_persona` el código que quedó duplicado (el bucle `por_persona` y el armado de `comparables`/`sin_historial` originales, líneas 274-310).

- [ ] **Step 4: Correr TODOS los tests**

Run: `python -m pytest tests/ -q`
Expected: PASS completo. Los tests preexistentes de desvíos por persona validan que el refactor no cambió la respuesta.

- [ ] **Step 5: Commit**

```bash
git add app/services/gerencial_service.py tests/test_gerencial_kpis.py
git commit -m "feat(gerencial): desvíos por cliente con ventana histórica compartida"
```

---

### Task 3: Backend — endpoints `/indicadores` y `/desvios-cliente`

**Files:**
- Modify: `app/api/gerencial.py` (agregar al final, después de `desvios_persona` línea 104)
- Test: `tests/test_autorizacion_roles.py` (solo si ese archivo enumera endpoints uno a uno; si la protección es por router, no hace falta tocarlo — verificarlo leyéndolo)

**Interfaces:**
- Consumes: `GerencialService.indicadores` (Task 1), `GerencialService.desvios_por_cliente` (Task 2), helpers `get_service` y `_atrapar_periodo` existentes.
- Produces: `GET /api/gerencial/indicadores?quincena|mes&empresa` y `GET /api/gerencial/desvios-cliente?quincena|mes&empresa&umbral`, protegidos por el router (roles admin/jefe/gerente).

- [ ] **Step 1: Agregar los endpoints**

Al final de `app/api/gerencial.py`:

```python
@router.get("/indicadores")
def indicadores(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    service: GerencialService = Depends(get_service),
):
    """KPIs de control: $/hora jornal, % adicionales y descomposición de la
    variación (dotación / actividad / precio) contra el período anterior."""
    return _atrapar_periodo(service.indicadores, quincena, mes, empresa)


@router.get("/desvios-cliente")
def desvios_cliente(
    quincena: Optional[date] = Query(None),
    mes: Optional[str] = Query(None),
    empresa: Optional[str] = Query(None),
    umbral: float = Query(UMBRAL_DESVIO_DEFAULT, ge=0, le=500),
    service: GerencialService = Depends(get_service),
):
    """Clientes vs. su propia media histórica (6 quincenas, mínimo 3)."""
    return _atrapar_periodo(service.desvios_por_cliente, quincena, mes, empresa, umbral)
```

- [ ] **Step 2: Revisar `tests/test_autorizacion_roles.py`**

Leerlo. Si tiene una lista de rutas gerenciales para probar autorización, agregar `/api/gerencial/indicadores` y `/api/gerencial/desvios-cliente` a esa lista siguiendo el patrón del archivo. Si la cobertura es genérica por router, no tocar nada.

- [ ] **Step 3: Correr TODOS los tests**

Run: `python -m pytest tests/ -q`
Expected: PASS completo.

- [ ] **Step 4: Commit**

```bash
git add app/api/gerencial.py tests/test_autorizacion_roles.py
git commit -m "feat(gerencial): endpoints de indicadores de control y desvíos por cliente"
```

---

### Task 4: Frontend — servicio + KPIs nuevos ($/hora jornal y % adicionales)

**Files:**
- Modify: `src/services/gerencial.js`
- Modify: `src/pages/Gerencial.jsx` (queries ~línea 91, fila KPI líneas 150-170)

**Interfaces:**
- Consumes: endpoints de Task 3.
- Produces: `obtenerIndicadores(periodo)` y `obtenerDesviosClientes(periodo, umbral)` en `src/services/gerencial.js`; variable `indicadores` (resultado de useQuery) disponible en el cuerpo de `Gerencial()` para las Tasks 5. La query de desvíos-clientes se agrega en Task 6.

- [ ] **Step 1: Agregar las funciones de servicio**

Al final de `src/services/gerencial.js`:

```js
export const obtenerIndicadores = (periodo) =>
  api.get('/gerencial/indicadores', { params: params(periodo) }).then(r => r.data)

export const obtenerDesviosClientes = (periodo, umbral) =>
  api.get('/gerencial/desvios-cliente', { params: params({ ...periodo, umbral }) }).then(r => r.data)
```

- [ ] **Step 2: Agregar la query y los tiles**

En `Gerencial.jsx`: importar `obtenerIndicadores` en el import de servicios, y junto a las otras queries (después de la de `desvios`, línea ~95):

```jsx
  const { data: indicadores } = useQuery({
    queryKey: ['gerencial-indicadores', keyPeriodo],
    queryFn: () => obtenerIndicadores(periodo),
    enabled: habilitado,
  })
```

En la fila KPI (después del tile PERSONAS, línea ~169), agregar dos tiles:

```jsx
        <div className={styles.kpiTile}>
          <div className={styles.kpiLabel}>$ / HORA JORNAL</div>
          <div className={styles.kpiValor}>
            {indicadores?.actual?.costo_hora != null ? moneda.format(indicadores.actual.costo_hora) : '—'}
          </div>
          {indicadores?.variaciones?.costo_hora_pct != null && (
            <div className={styles.kpiDelta}>
              <span className={indicadores.variaciones.costo_hora_pct >= 0 ? styles.deltaUp : styles.deltaDown}>
                {indicadores.variaciones.costo_hora_pct >= 0 ? '▲' : '▼'} {Math.abs(indicadores.variaciones.costo_hora_pct).toLocaleString('es-AR')} %
              </span>
              <span className={styles.deltaRef}> vs período anterior</span>
            </div>
          )}
        </div>
        <div className={styles.kpiTile}>
          <div className={styles.kpiLabel}>ADICIONALES SOBRE EL TOTAL</div>
          <div className={styles.kpiValor}>
            {indicadores?.actual?.adicionales_pct != null ? `${indicadores.actual.adicionales_pct.toLocaleString('es-AR')} %` : '—'}
          </div>
          {indicadores?.variaciones?.adicionales_pct_puntos != null && (
            <div className={styles.kpiDelta}>
              <span className={indicadores.variaciones.adicionales_pct_puntos >= 0 ? styles.deltaUp : styles.deltaDown}>
                {indicadores.variaciones.adicionales_pct_puntos >= 0 ? '▲' : '▼'} {Math.abs(indicadores.variaciones.adicionales_pct_puntos).toLocaleString('es-AR')} pts
              </span>
              <span className={styles.deltaRef}> vs período anterior</span>
            </div>
          )}
        </div>
```

Nota: los deltas usan ▲ rojo / ▼ verde igual que el tile existente (en costos, subir es malo — las clases `deltaUp`/`deltaDown` ya lo resuelven así).

- [ ] **Step 3: Verificar que compila**

Run: `npm run build` en el repo frontend.
Expected: build sin errores.

- [ ] **Step 4: Commit**

```bash
git add src/services/gerencial.js src/pages/Gerencial.jsx
git commit -m "feat(gerencial): KPIs de \$/hora jornal y % de adicionales"
```

---

### Task 5: Frontend — panel "¿Por qué varió?"

**Files:**
- Modify: `src/pages/Gerencial.jsx` (nuevo panel después de la fila KPI, línea ~171; componente nuevo al final del archivo)
- Modify: `src/pages/Gerencial.module.css` (clases nuevas al final)

**Interfaces:**
- Consumes: variable `indicadores` de Task 4; componentes/estilos existentes (`styles.panel`, `styles.desvioTrack`, `styles.desvioEjeCentral`, `styles.desvioFill*`, helper `compacto`).
- Produces: componente `PanelVariacion({ indicadores })` renderizado entre la fila KPI y EVOLUCIÓN POR QUINCENA.

- [ ] **Step 1: Insertar el panel en el layout**

Entre la fila KPI y la sección EVOLUCIÓN (línea ~172):

```jsx
      {/* ¿Por qué varió? */}
      <section className={styles.panel}>
        <div className={styles.panelTitulo}>¿POR QUÉ VARIÓ?</div>
        <div className={styles.panelSub}>
          Descomposición de la variación contra el período anterior. Los tres efectos suman la variación total.
        </div>
        <PanelVariacion indicadores={indicadores} />
      </section>
```

- [ ] **Step 2: Agregar el componente al final de `Gerencial.jsx`**

```jsx
// ─── ¿Por qué varió?: descomposición dotación / actividad / precio ──────────
// Barras divergentes centradas en 0 (mismo lenguaje visual que BarraDesvio).

function PanelVariacion({ indicadores }) {
  const d = indicadores?.descomposicion
  if (!indicadores?.anterior) {
    return <div className={styles.empty}>Sin período anterior para comparar.</div>
  }
  if (!d) {
    return (
      <div className={styles.empty}>
        No se puede descomponer: falta información de horas o personas en alguno de los dos períodos.
      </div>
    )
  }
  const filas = [
    { id: 'dotacion', etiqueta: 'Dotación', detalle: `${indicadores.anterior.personas} → ${indicadores.actual.personas} personas`, ...d.dotacion },
    { id: 'actividad', etiqueta: 'Actividad', detalle: 'horas de jornal por persona', ...d.actividad },
    { id: 'precio', etiqueta: 'Precio', detalle: '$ pagado por hora de jornal', ...d.precio },
  ]
  const maxAbs = Math.max(...filas.map(f => Math.abs(f.monto)), 1)
  return (
    <div className={styles.variacionLista}>
      {filas.map(f => (
        <div key={f.id} className={styles.variacionFila}>
          <div className={styles.variacionEtiqueta}>
            {f.etiqueta}
            <span className={styles.barraExtra}> · {f.detalle}</span>
          </div>
          <div className={styles.desvioTrack}>
            <div className={styles.desvioEjeCentral} />
            <div
              className={`${styles.desvioFill} ${f.monto >= 0 ? styles.desvioFillPos : styles.desvioFillNeg}`}
              style={f.monto >= 0
                ? { left: '50%', width: `${(Math.abs(f.monto) / maxAbs) * 50}%` }
                : { left: `${50 - (Math.abs(f.monto) / maxAbs) * 50}%`, width: `${(Math.abs(f.monto) / maxAbs) * 50}%` }}
            />
          </div>
          <div className={styles.variacionValor}>
            <span className="mono">{f.monto >= 0 ? '+' : '−'}{compacto(Math.abs(f.monto))}</span>
            <span className={styles.barraPct}> {f.pct >= 0 ? '+' : ''}{f.pct.toLocaleString('es-AR')} %</span>
          </div>
        </div>
      ))}
    </div>
  )
}
```

- [ ] **Step 3: Agregar los estilos**

Al final de `src/pages/Gerencial.module.css` (copiar la grilla de `filaBarra` existente como referencia de proporciones):

```css
/* ─── Panel ¿Por qué varió? ─── */
.variacionLista {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}
.variacionFila {
  display: grid;
  grid-template-columns: 240px 1fr 170px;
  align-items: center;
  gap: 12px;
}
.variacionEtiqueta {
  font-weight: 600;
  font-size: 0.9rem;
}
.variacionValor {
  text-align: right;
  font-size: 0.9rem;
  white-space: nowrap;
}
@media (max-width: 720px) {
  .variacionFila { grid-template-columns: 130px 1fr 120px; }
}
```

Si `panelSub` hoy solo existe dentro de `panelTituloRow`, verificar que renderice bien suelto (es un `div` con clase propia, debería).

- [ ] **Step 4: Verificar que compila**

Run: `npm run build`
Expected: build sin errores.

- [ ] **Step 5: Commit**

```bash
git add src/pages/Gerencial.jsx src/pages/Gerencial.module.css
git commit -m "feat(gerencial): panel de descomposición de la variación (¿por qué varió?)"
```

---

### Task 6: Frontend — panel de desvíos por cliente

**Files:**
- Modify: `src/pages/Gerencial.jsx` (query nueva, panel después de DESVÍOS POR PERSONA línea ~228, componente al final)

**Interfaces:**
- Consumes: `obtenerDesviosClientes` (Task 4), estado `umbral` existente, componente `BarraDesvio` existente, estilos `thNum/tdNum/filaAlerta/...` existentes.
- Produces: componente `TablaDesviosClientes({ datos })` y su panel.

- [ ] **Step 1: Query nueva**

Importar `obtenerDesviosClientes` y agregar junto a las otras queries:

```jsx
  const { data: desviosClientes } = useQuery({
    queryKey: ['gerencial-desvios-clientes', keyPeriodo, umbral],
    queryFn: () => obtenerDesviosClientes(periodo, umbral),
    enabled: habilitado,
  })
```

- [ ] **Step 2: Panel en el layout**

Después de la sección DESVÍOS POR PERSONA (línea ~228), antes de la nota final:

```jsx
      {/* Desvíos por cliente */}
      <section className={styles.panel}>
        <div className={styles.panelTitulo}>DESVÍOS POR CLIENTE</div>
        <div className={styles.panelSub}>
          Cada cliente contra su propia media de las últimas {desviosClientes?.ventana_quincenas ?? 6} quincenas
          (mínimo {desviosClientes?.minimo_quincenas ?? 3} con actividad). Usa el mismo umbral de alerta.
        </div>
        <TablaDesviosClientes datos={desviosClientes} />
      </section>
```

- [ ] **Step 3: Componente al final de `Gerencial.jsx`**

```jsx
// ─── Tabla de desvíos por cliente ────────────────────────────────────────────

function TablaDesviosClientes({ datos }) {
  const [verSinHistorial, setVerSinHistorial] = useState(false)
  if (!datos) return <div className={styles.empty}>Sin datos.</div>
  const { clientes, sin_historial: sinHistorial } = datos
  const maxAbs = Math.max(...clientes.map(c => Math.abs(c.desvio_pct ?? 0)), 1)

  return (
    <>
      {!clientes.length ? (
        <div className={styles.empty}>Ningún cliente con historial comparable en este período.</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>CLIENTE</th>
                <th className={styles.thNum}>PROMEDIO QUINCENAL</th>
                <th className={styles.thNum}>SU MEDIA HISTÓRICA</th>
                <th className={styles.thNum}>DESVÍO</th>
                <th className={styles.thBarra}></th>
              </tr>
            </thead>
            <tbody>
              {clientes.map(c => (
                <tr key={c.cliente} className={c.supera_umbral ? styles.filaAlerta : undefined}>
                  <td>
                    <div>{c.cliente}</div>
                    <div className={styles.cuil}>{c.quincenas_historia} quinc. de historia</div>
                  </td>
                  <td className={`mono ${styles.tdNum}`}>{moneda.format(c.promedio_quincenal)}</td>
                  <td className={`mono ${styles.tdNum}`}>{moneda.format(c.media_historica)}</td>
                  <td className={`mono ${styles.tdNum}`}>
                    <span className={c.supera_umbral ? styles.desvioAlerta : styles.desvioNormal}>
                      {c.desvio_pct > 0 ? '+' : ''}{c.desvio_pct?.toLocaleString('es-AR')} %
                    </span>
                    {c.supera_umbral && <span className={styles.badgeAlerta}>⚠ sobre umbral</span>}
                  </td>
                  <td className={styles.tdBarra}>
                    <BarraDesvio pct={c.desvio_pct} maxAbs={maxAbs} alerta={c.supera_umbral} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {sinHistorial.length > 0 && (
        <div className={styles.sinHistorial}>
          <button className="btn btn-sm" onClick={() => setVerSinHistorial(v => !v)}>
            {verSinHistorial ? '▾' : '▸'} {sinHistorial.length} clientes sin historial comparable
          </button>
          {verSinHistorial && (
            <div className={styles.sinHistorialLista}>
              {sinHistorial.map(c => (
                <div key={c.cliente} className={styles.sinHistorialItem}>
                  <span>{c.cliente}</span>
                  <span className={styles.cuil}>{c.quincenas_historia} quinc. de historia</span>
                  <span className="mono">{moneda.format(c.promedio_quincenal)}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </>
  )
}
```

- [ ] **Step 4: Verificar que compila**

Run: `npm run build`
Expected: build sin errores.

- [ ] **Step 5: Commit**

```bash
git add src/pages/Gerencial.jsx
git commit -m "feat(gerencial): tabla de desvíos por cliente"
```

---

### Task 7: Smoke test real (backend local + frontend dev contra datos reales)

**Files:** ninguno (verificación).

**Interfaces:**
- Consumes: todo lo anterior. Solo LECTURAS contra la base real.

- [ ] **Step 1: Correr toda la suite backend una última vez**

Run: `python -m pytest tests/ -q`
Expected: PASS completo.

- [ ] **Step 2: Probar los endpoints nuevos con datos reales**

Levantar el backend local (`uvicorn app.main:app --port 8000` o el comando que documente el README del backend) y, con una quincena real existente (obtenerla de `GET /api/gerencial/quincenas`), pedir:
- `GET /api/gerencial/indicadores?quincena=<q>` → verificar que `actual.total` coincide con `GET /api/gerencial/resumen?quincena=<q>` (`total`), que `costo_hora ≈ total / horas_jornal`, y que si hay `descomposicion` sus tres montos suman `actual.total − anterior.total` (tolerancia de centavos por redondeo).
- `GET /api/gerencial/desvios-cliente?quincena=<q>` → verificar que devuelve clientes conocidos y que la suma de conteos es plausible.

Nota: los endpoints exigen autenticación por rol; usar el mismo mecanismo que usan los tests o un token válido de la app local. Si levantar el backend requiere credenciales que no están disponibles, reportarlo como pendiente en lugar de saltearlo en silencio.

- [ ] **Step 3: Smoke visual del frontend**

Con el backend local corriendo, `npm run dev` y abrir la vista Gerencial: verificar los 4 tiles KPI, el panel ¿POR QUÉ VARIÓ? con las 3 barras, y la tabla DESVÍOS POR CLIENTE. Cambiar quincena/mes/empresa y confirmar que todo se actualiza sin errores de consola.

- [ ] **Step 4: Push de ambas ramas (sin PR todavía)**

```bash
git push -u origin feature/gerencial-control-analitico   # en cada repo
```

Los PRs se abren después de la revisión final de código (el usuario decide el merge y el deploy).
