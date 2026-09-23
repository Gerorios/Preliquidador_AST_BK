# Sistema de gestión La Asturiana — Backend

API REST de uso interno del Sistema de gestión La Asturiana SRL. Es un monolito modular
(ADR-0013): un núcleo compartido y módulos autocontenidos. El primer módulo,
**Preliquidación**, arma la preliquidación de sueldos por quincena a partir de las tareas
de campo y produce el Excel que alimenta la liquidación formal.

Repositorio hermano (frontend React + Vite): `Gerorios/Preliquidador_AST_FT`.

---

## Stack

| Componente | Tecnología |
|---|---|
| Lenguaje | Python 3.13 (soporta 3.11/3.12) |
| Framework web | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.0 |
| Base de datos | MySQL (PyMySQL) |
| Validación / config | Pydantic v2 + pydantic-settings (`.env`) |
| Autenticación | JWT + bcrypt |
| Exportación | openpyxl |
| Tests | pytest (SQLite en memoria) |

Las migraciones son SQL manual versionado en `migrations/<core|modulo>/` (Alembic figura en
`requirements.txt` pero no se usa).

---

## Estructura

```
app/
├── main.py            # arranque, middlewares, registro de routers
├── core/              # núcleo compartido: config, conexiones, auth, permisos, usuarios
└── modulos/
    ├── preliquidacion/   # módulo Preliquidación (activo): api/, services/, models.py, schemas.py
    └── terceros/         # módulo Liquidación Terceros (en construcción, inactivo)
migrations/            # SQL por núcleo y por módulo
tests/                 # core/, preliquidacion/, terceros/
scripts/               # utilidades de administración y desarrollo
docs/                  # documentación funcional, ADRs y guías
```

Reglas de arquitectura: un módulo nunca importa a otro, y el núcleo no importa módulos
(hay un test que lo verifica). Lo compartido sube al núcleo.

---

## Puesta en marcha

```bash
python -m venv venv
venv\Scripts\activate        # Windows  (Linux/Mac: source venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env       # completar; pedir las credenciales al responsable del sistema
python verificar_conexion.py # chequea las conexiones (en Windows, con PYTHONUTF8=1)
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentación interactiva de los endpoints: http://localhost:8000/docs
- Health check: http://localhost:8000/health

En desarrollo se trabaja contra la base de prueba, nunca contra la de producción. El detalle
está en `docs/modulos/PUESTA-A-PUNTO.md`.

### Tests

```bash
pytest
```

---

## Documentación

| Archivo | Contenido |
|---|---|
| `CONTEXT.md` | Glosario del dominio |
| `docs/DOCUMENTACION.md` | Documentación funcional |
| `docs/AYUDA.md` | Ayuda de uso |
| `docs/adr/` | Decisiones de arquitectura |
| `docs/BITACORA.md` | Qué se mergeó y por qué |
| `docs/modulos/GUIA-MODULOS.md` | Cómo construir un módulo |
| `docs/modulos/PUESTA-A-PUNTO.md` | Dejar una máquina nueva con los dos proyectos corriendo |
