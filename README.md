# Control de Caja CHAMPIONSBET

Aplicación web responsiva para control, monitoreo en tiempo real y arqueo diario de caja de un punto de recargas y servicios.

- **Backend:** FastAPI + SQLAlchemy (SQLite) + WebSockets.
- **Frontend:** HTML5 + JavaScript moderno + Bootstrap 5 (una sola pantalla, sin recargas: todo llega por WebSocket).

## Inicio rápido

```bash
pip install -r requirements.txt
python main.py                 # o: uvicorn app.main:app --reload
```

Abrir http://localhost:8000. La base `caja.db` se crea y se siembra automáticamente al arrancar.

## Pruebas

```bash
pytest -q
```

## Datos precargados

- **Colaboradores:** Carlos, Refa (se pueden agregar más o alternar el turno activo).
- **Plataformas:** Ecuabet, DoradoBet, Mas 1X2, Astrobet, Sportbet, Mi Negocio Efectivo, Bemovil.
- **Cuentas:** Efectivo, Banco Pichincha, Banco Guayaquil, Banco Rumiñahui (BGR), Banco del Pacífico, Cooperativa 29 de Octubre, COOPMEGO, Cooperativa JEP.

## Reglas de negocio

| Operación | Efecto en plataforma | Efecto en cuenta / efectivo |
|---|---|---|
| Venta / recarga pagada | −monto (consumo de cupo) | +monto en la cuenta de ingreso |
| Venta a crédito | −monto | sin efecto hasta el abono (cuenta por cobrar) |
| Compra de cupo de contado | +monto | −monto de la cuenta indicada |
| Compra de cupo a crédito | +monto | sin efecto hasta liquidar (deuda a distribuidor) |
| Egreso / gasto | — | −monto |

Los abonos (`POST /api/payments`) admiten pagos parciales: suman al efectivo/banco en créditos de clientes, restan al liquidar deudas con distribuidores, y cierran la transacción cuando el saldo pendiente llega a cero.

## Alertas de abastecimiento

Cada plataforma tiene `saldo mínimo` (rojo) y `umbral de advertencia` (amarillo), editables desde la UI:

- Verde: saldo por encima del umbral de advertencia.
- Amarillo: saldo ≤ umbral de advertencia.
- Rojo parpadeante + badge y alerta sonora: saldo ≤ saldo mínimo.

## API

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/state` | Estado completo (plataformas, cuentas, colaboradores, créditos, deudas, totales) |
| POST | `/api/transactions` | Registrar venta, compra de cupo o egreso |
| POST | `/api/payments` | Abonar o liquidar un crédito / deuda |
| POST | `/api/collaborators` | Crear colaborador |
| PATCH | `/api/collaborators/{id}` | Activar/desactivar turno |
| PATCH | `/api/platforms/{id}/thresholds` | Actualizar umbrales de alerta |
| PATCH | `/api/accounts/{id}/balance` | Ajustar saldo de apertura de una cuenta |
| GET | `/api/report/csv?day=YYYY-MM-DD` | Exportar arqueo del día en CSV |
| WS | `/ws` | Estado inicial + difusión de cada cambio a todos los dispositivos |
