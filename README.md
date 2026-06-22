# Sistema de Preliquidación — La Asturiana SRL

## Requisitos
- Python 3.13 (o 3.11/3.12)
- MySQL local para la BD propia
- Acceso a la BD externa con credenciales

---

## Instalación

```bash
cd backend
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env         # completar con credenciales reales
```

---

## Verificar conexiones antes de arrancar

```bash
python verificar_conexion.py
```

Si la query principal falla, ajustar `QUERY_PRINCIPAL` en
`app/services/consulta_externa.py` con los nombres reales de tus tablas.

---

## Arrancar el servidor

```bash
uvicorn app.main:app --reload
```

- API: http://localhost:8000
- Documentación interactiva: http://localhost:8000/docs
- Health check: http://localhost:8000/health

---

## Notas importantes

### Tabla usuarios
El sistema usa la tabla `usuarios` que ya existe en tu BD propia.
No la crea ni la modifica. Solo la referencia para relaciones internas.

### Tablas que sí crea automáticamente (solo si no existen)
- empresa
- empleado / empleado_legajo / empleado_categoria
- precio_maestro / precio_comun
- preliquidacion / preliquidacion_linea
- concepto_adicional / ajuste_manual

### BD externa
Solo lectura. Nunca escribe en ella.

---

## Endpoints disponibles (http://localhost:8000/docs)

| Método | URL | Descripción |
|--------|-----|-------------|
| POST | /api/preliquidacion/generar | Genera preliquidación para una quincena |
| GET | /api/preliquidacion/ | Lista todas las preliquidaciones |
| GET | /api/preliquidacion/{id}/estadisticas | Estadísticas de una preliquidación |
| GET | /api/preliquidacion/{id}/lineas | Lista líneas con filtros |
| PATCH | /api/preliquidacion/linea/{id} | Edita una línea |
| POST | /api/preliquidacion/linea/{id}/concepto | Agrega bono/concepto |
| DELETE | /api/preliquidacion/linea/concepto/{id} | Elimina concepto |
| GET | /api/precios/maestro/clientes | Desplegable clientes (BD externa) |
| GET | /api/precios/maestro/fincas?cliente=X | Desplegable fincas (BD externa) |
| GET | /api/precios/maestro/tareas | Desplegable tareas (BD externa) |
| GET | /api/precios/maestro | Lista precios maestro |
| POST | /api/precios/maestro | Carga/actualiza precio maestro |
| GET | /api/precios/comunes | Lista precios comunes |
| POST | /api/precios/comunes | Carga/actualiza precio común |
