# Nexo Campus

**Sistema Central de Gestión Operativa de Campuslands.** Une en un solo flujo la reserva de espacios, el préstamo y control de equipos tecnológicos y la gestión de incidencias, con Inteligencia Artificial para clasificar incidencias y recomendar espacios.

> Proyecto desarrollado en la Hackatón Campuslands *"El campus bajo presión"*.

---

## Contenido

1. [El problema](#1-el-problema)
2. [La solución](#2-la-solución)
3. [Integrantes](#3-integrantes)
4. [Stack tecnológico](#4-stack-tecnológico)
5. [Arquitectura](#5-arquitectura)
6. [Uso de la Inteligencia Artificial](#6-uso-de-la-inteligencia-artificial)
7. [Reglas de negocio](#7-reglas-de-negocio)
8. [Datos](#8-datos)
9. [Instalación](#9-instalación)
10. [Ejecución](#10-ejecución)
11. [Guía de uso](#11-guía-de-uso)
12. [Pruebas](#12-pruebas)
13. [Estructura del proyecto](#13-estructura-del-proyecto)
14. [Seguridad](#14-seguridad)
15. [Solución de problemas](#15-solución-de-problemas)

---

## 1. El problema

Campuslands crece rápido y su operación diaria depende de registros dispersos y revisiones manuales:

- **Espacios:** dos grupos reservan la misma sala a la misma hora, o se reserva una sala pequeña para más personas de las que caben.
- **Equipos:** no hay certeza de qué equipo está prestado, a quién, o si está dañado.
- **Incidencias:** los reportes llegan desordenados; no está claro cuál es urgente ni qué área debe atenderlo.
- **Todo está desconectado:** un aula con una falla grave se sigue asignando porque nadie conecta el reporte con las reservas.

## 2. La solución

Nexo Campus es un MVP con tres módulos que operan como uno solo:

| Módulo | Qué hace |
|---|---|
| **Espacios** | Reserva de salas validando cruces de horario, aforo, estado del espacio y horario del campus. Si una reserva se rechaza, la IA recomienda alternativas reales y libres. |
| **Recursos** | Los **PC de torre se prestan junto con su sala** al reservarla; los equipos sueltos (portátiles, proyectores) se prestan y devuelven con límite por persona. Inventario e **historial de cada cambio de estado**. |
| **Incidencias** | Reporte en lenguaje natural. La IA propone **categoría, prioridad, área responsable y justificación**; una persona confirma o corrige antes de guardar. |
| **Regla central** | Una incidencia **alta o crítica** sobre un espacio o equipo lo **inhabilita** automáticamente (no se puede reservar ni prestar). Al cerrarse, vuelve al estado que tenía. |

Además:
- **Carga de datos oficiales** desde la página o por consola, con un **reporte de calidad** de cada registro rechazado o corregido.
- **Administración** para registrar y editar espacios y equipos.
- **Panel de inicio** con el estado de la operación en una sola pantalla.

## 3. Integrantes

| Integrante | Usuario de GitHub |
|---|---|
| Santiago Villamizar Mantilla | SantiagovillamizarM |
| Manuel Isaac Camaño Díaz | — |
| Juan | Juan2509 |
| Pau | pau091 |

## 4. Stack tecnológico

| Necesidad | Tecnología | Versión |
|---|---|---|
| Lenguaje | Python | 3.12 |
| Interfaz | Streamlit | 1.39.0 |
| Persistencia | SQLite + SQLModel (SQLAlchemy) | 0.0.22 |
| Validación | Pydantic | 2.9.2 |
| Carga y limpieza de datos | pandas + openpyxl | 2.2.3 / 3.1.5 |
| Cliente de IA | openai (API compatible) + httpx | 1.51.2 / 0.27.2 |
| Modelo de IA | Google Gemini 2.5 Flash-Lite (respaldo: Gemini 2.5 Flash). Alternativa sin internet: Ollama + llama3.2:3b | — |
| Configuración | python-dotenv | 1.0.1 |
| Pruebas | pytest | 8.3.3 |

## 5. Arquitectura

Arquitectura por capas. La interfaz nunca accede a la base de datos ni a la IA directamente: siempre pasa por los servicios.

```
┌────────────────────────────────────────────┐
│  Interfaz (Streamlit)    app.py · ui/      │  Muestra datos y captura acciones
└──────────────────────┬─────────────────────┘
                       ▼
┌────────────────────────────────────────────┐      ┌──────────────────────────┐
│  Servicios               services/         │ ───▶ │  IA          ai/         │
│  Casos de uso: reservar, prestar,          │      │  Cliente, triaje y       │
│  registrar incidencia, regla central       │      │  recomendaciones         │
└──────────┬─────────────────────┬───────────┘      └────────────┬─────────────┘
           ▼                     ▼                               ▼
┌────────────────────┐  ┌────────────────────────┐     Gemini (API compatible
│  Reglas   rules/   │  │  Repositorios          │     con OpenAI) u Ollama
│  Funciones puras   │  │  repositories/         │
│  con constantes    │  │  Consultas a SQLite    │
└────────────────────┘  └───────────┬────────────┘
                                    ▼
                        ┌────────────────────────┐
                        │  Modelos  models/      │
                        │  SQLite (data/*.db)    │
                        └────────────────────────┘
```

| Capa | Responsabilidad |
|---|---|
| `nexo_campus/ui/` y `app.py` | Pantallas, formularios, tablas y mensajes de carga, éxito y error |
| `nexo_campus/services/` | Orquesta cada operación: busca datos, aplica las reglas, llama a la IA y guarda |
| `nexo_campus/rules/` | Reglas de negocio como funciones puras; los límites están en constantes |
| `nexo_campus/repositories/` | Lectura y escritura en SQLite |
| `nexo_campus/models/` | Entidades y estados (`Enum`) |
| `nexo_campus/ai/` | Cliente de IA, triaje y recomendaciones, con validación de respuestas |
| `nexo_campus/carga/` | Lectura, normalización y validación de los datos oficiales |
| `nexo_campus/config.py` | Única fuente de configuración (lee el `.env`) |

## 6. Uso de la Inteligencia Artificial

La IA se usa en dos puntos del flujo, siempre con **control de sus respuestas** y **sin decidir sola**.

### 6.1 Triaje de incidencias (`ai/triaje.py`)

A partir del texto libre de un reporte, la IA devuelve en JSON:

| Campo | Valores permitidos |
|---|---|
| `categoria` | infraestructura, tecnologia, aseo, seguridad, bienestar, otro |
| `prioridad` | baja, media, alta, critica |
| `area_responsable` | mantenimiento, soporte_ti, servicios_generales, seguridad, bienestar |
| `justificacion` | Una o dos frases en español |

- Recibe **contexto**: el espacio y el equipo afectados, y si hay una **clase en curso** en ese momento. Así, un proyector que no enciende es `alta` en un aula vacía y `critica` con clase.
- **Flujo en dos pasos** (`services/incidencias.py`):
  1. La IA propone (no se guarda nada).
  2. La persona acepta o corrige con selectores y registra.
- Queda marcada como **"Clasificada por IA"** solo si se aceptó sin cambios; si se corrigió o la IA falló, queda como **"Clasificación manual"**.

### 6.2 Recomendación de espacios (`ai/recomendaciones.py`)

Cuando una reserva se rechaza, el sistema busca en la base de datos los espacios **realmente libres** y con aforo suficiente. La IA **solo ordena y explica** cuáles sirven mejor para el motivo de la reserva: por ejemplo, salas de cómputo para una clase de programación y cubículos para una reunión pequeña. Si la IA devuelve un espacio que no está entre los candidatos, se descarta.

### 6.3 Control de respuestas

- La IA responde en **JSON** y se valida con **Pydantic** contra listas fijas. Si inventa un valor, deja vacía la justificación o el área no corresponde a la categoría, se rechaza con un error controlado.
- Si la IA falla (sin conexión, clave inválida, tiempo agotado, límite de consultas), la app **muestra el error y permite continuar manualmente**. **Nunca se inventa una respuesta.**
- Toda llamada pasa por un único cliente (`ai/cliente.py`), con mensajes claros para cada tipo de error.
- Si el modelo principal agota su cuota, se usa automáticamente el **modelo de respaldo** (`AI_MODELO_RESPALDO`).

### 6.4 Resultados de las pruebas

| Caso | Resultado de la IA |
|---|---|
| "Huele a gas en la cocina" | seguridad / crítica ✅ |
| "Una compañera se desmayó en el pasillo" | bienestar / crítica ✅ |
| "Se robaron un portátil del cubículo" | seguridad / alta ✅ |
| "Falta papel higiénico en el baño" | aseo / baja ✅ |
| "El proyector no enciende y hay clase" | tecnología / crítica ✅ |
| Clase de programación para 30 personas que no cabe en Sala Azul | Recomendó Artemis, Apolo y Sputnik (salas de cómputo) ✅ |
| Reunión de 8 personas | Recomendó Sala Azul, Sala Blanca y Cosmos ✅ |

Tiempo por consulta: 1 a 3 segundos con Gemini. El detalle de las pruebas y la comparación con el modelo local está en [`ContextIA.md`](ContextIA.md).

## 7. Reglas de negocio

Cada regla es una función aislada en `nexo_campus/rules/`, con sus límites en **constantes al inicio del archivo**, para poder modificarlas en vivo. Si una regla no se cumple, se lanza `ReglaNegocioError` con un mensaje para el usuario y **no se guarda nada**.

| # | Regla | Archivo | Constante (valor actual) |
|---|---|---|---|
| 1 | Una reserva no se cruza con otra reserva activa del mismo espacio (08–10 y 10–12 no se cruzan) | `rules/reservas.py` | — |
| 2 | Los asistentes no superan el aforo del espacio | `rules/reservas.py` | — |
| 3 | No se reservan espacios en mantenimiento o inhabilitados | `rules/reservas.py` | `ESTADOS_RESERVABLES` |
| 3b | Horario del campus, duración mínima y máxima, sin reservas en el pasado | `rules/reservas.py` | `HORA_APERTURA` (06:00), `HORA_CIERRE` (22:00), `DURACION_MINIMA_MINUTOS` (30), `DURACION_MAXIMA_HORAS` (4) |
| 4 | Solo se presta un equipo disponible. Los PC de torre no se prestan sueltos: **se prestan todos junto con su sala al reservarla** | `rules/prestamos.py` | `ESTADOS_PRESTABLES`, `TIPOS_NO_PRESTABLES` (`pc_torre`) |
| 5 | Límite de préstamos activos por persona y duración máxima del préstamo | `rules/prestamos.py` | `MAX_PRESTAMOS_ACTIVOS` (2), `DIAS_MAXIMOS_PRESTAMO` (7) |
| 6 | Códigos válidos y únicos; el aforo no puede bajar de una reserva futura ya aceptada; "Prestado" no se asigna a mano | `rules/catalogo.py` | `PATRON_CODIGO`, `AFORO_MAXIMO` (500) |
| 7 | **Regla central:** una incidencia alta o crítica inhabilita el espacio o equipo hasta que se cierra | `rules/central.py` + `services/regla_central.py` | `PRIORIDADES_QUE_BLOQUEAN` (alta, crítica) |

### Detalle de la regla central

- Al **registrar** una incidencia grave, el espacio o equipo queda **inhabilitado**: las reglas 3 y 4 impiden reservarlo o prestarlo.
- Al **cerrarla**, vuelve al estado que tenía antes, leído del historial. Si estaba en mantenimiento, vuelve a mantenimiento.
- Si hay varias incidencias graves abiertas sobre lo mismo, sigue bloqueado hasta cerrar la última.
- No libera lo que estaba inhabilitado por otra razón, por ejemplo desde Administrar.
- A un equipo **prestado** no se le quita a quien lo tiene: se bloquea cuando se devuelve.
- Las **reservas futuras** de un espacio bloqueado se señalan en pantalla para reubicarlas.
- Cada bloqueo y liberación queda en el **historial** del espacio o del equipo.

### Ejemplo del flujo integrado

```
Reserva de Apolo para mañana ✅
→ Incidencia "sale humo de un tomacorriente en Apolo" (crítica)
→ ⛔ Apolo queda inhabilitado · aviso: "1 reserva activa debe reubicarse"
→ Intento de reservar Apolo ❌ "está inhabilitado" → la IA recomienda Artemis, Sputnik y el Auditorio
→ Se cierra la incidencia → ✅ "Apolo vuelve a estar disponible"
```

## 8. Datos

### Datos incluidos

`data/raw/` contiene el inventario de Campuslands:

| Archivo | Contenido |
|---|---|
| `espacios.csv` | 10 salas: Auditorio (100), Cosmos (25), Apolo (34), Skilab (20), Sputnik (38), Artemis (32), Sala Blanca (12), Sala Azul (10), Sala Amarilla (6) y Sala Verde (6). Entre paréntesis, el aforo |
| `recursos.csv` | 124 PC de torre ubicados en las salas de cómputo: Apolo (34), Skilab (20), Sputnik (38) y Artemis (32). Cada PC está ligado a su sala por la columna `ubicacion` |

### Cargar datos

Hay dos formas, y las dos aplican la misma validación:

1. **Desde la página:** *Inicio → Cargar datos*. Se suben archivos CSV, Excel o JSON, el sistema reconoce qué contiene cada uno por su nombre y muestra el resultado.
2. **Por consola:**
   ```bash
   python scripts/cargar_datos.py              # primera carga
   python scripts/cargar_datos.py --reiniciar  # borra la base y vuelve a cargar desde cero
   ```

Archivos aceptados en `data/raw/`: `espacios`, `recursos`, `reservas`, `prestamos` e `incidencias`, en `.csv` (coma o punto y coma), `.xlsx`, `.xls` o `.json`. Si las columnas tienen otros nombres, se agregan como alias en `nexo_campus/carga/esquema.py`, sin tocar el código de carga.

### Qué valida la carga

Ningún registro inválido se descarta en silencio: todos quedan en el **reporte de calidad** (*Inicio → Calidad de datos*), con archivo, fila, ID y motivo.

| Revisión | Resultado |
|---|---|
| Campo obligatorio vacío, número o fecha inválidos, estado desconocido | Rechazado |
| Fila repetida o ID duplicado | Rechazado (se conserva el primero) |
| ID huérfano (una reserva o préstamo que apunta a algo que no existe) | Rechazado |
| Reserva solapada, que supera el aforo o que termina antes de empezar | Rechazado |
| Segundo préstamo activo del mismo equipo, o fechas incoherentes | Rechazado |
| Estado vacío | Cargado con valor por defecto + advertencia |
| Equipo "disponible" con un préstamo activo (o al revés) | Estado corregido + advertencia + historial |

## 9. Instalación

**Requisitos:** Python **3.12**, Git y conexión a internet para Gemini.

### 9.1 Clonar el repositorio

```bash
git clone https://github.com/SantiagovillamizarM/Nexo-Campus.git
cd Nexo-Campus
```

### 9.2 Crear el entorno virtual e instalar dependencias

**Windows (PowerShell)**
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```
> Si PowerShell bloquea la activación: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` y vuelve a activar.

**macOS / Linux**
```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

**Linux sin `python3.12`** (por ejemplo, si el sistema trae otra versión), con [uv](https://docs.astral.sh/uv/):
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.12
~/.local/bin/uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### 9.3 Configurar el `.env`

Copia la plantilla:

```powershell
copy .env.example .env     # Windows
```
```bash
cp .env.example .env       # macOS / Linux
```

Abre `.env` y completa la clave de **Google AI Studio** (https://aistudio.google.com → *Get API key*):

```env
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_API_KEY=tu_clave_aqui
AI_MODEL=gemini-2.5-flash-lite
AI_MODELO_RESPALDO=gemini-2.5-flash
AI_TIMEOUT=30
```

| Variable | Descripción |
|---|---|
| `AI_BASE_URL` | Endpoint compatible con OpenAI (Gemini u Ollama) |
| `AI_API_KEY` | Clave de la API. **Solo va en el `.env`**, nunca en el repositorio |
| `AI_MODEL` | Modelo principal |
| `AI_MODELO_RESPALDO` | Modelo que se usa si el principal agota su cuota (opcional) |
| `AI_TIMEOUT` | Segundos máximos de espera por consulta |
| `DATA_DIR` / `DATABASE_PATH` | Carpeta de datos y archivo de la base (por defecto `data/raw` y `data/nexo_campus.db`) |

**Alternativa sin internet (Ollama):** instala [Ollama](https://ollama.com/download), ejecuta `ollama pull llama3.2:3b` y en el `.env` usa:
```env
AI_BASE_URL=http://localhost:11434/v1
AI_API_KEY=ollama
AI_MODEL=llama3.2:3b
```

Sin IA configurada la app funciona igual; las incidencias se clasifican manualmente.

### 9.4 Cargar los datos

```bash
python scripts/cargar_datos.py
```

Debe terminar con `Total: 134 registros cargados, 0 rechazados.`

## 10. Ejecución

Con el entorno virtual activado, desde la raíz del proyecto:

```bash
python -m streamlit run app.py
```

Abre **http://localhost:8501** en el navegador. Si Streamlit pide un `Email:`, déjalo vacío y presiona Enter. Para detener la app, pulsa `Ctrl+C` en la terminal.

**Resumen para volver a ejecutarla:**

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
python -m streamlit run app.py
```
```bash
# macOS / Linux
source .venv/bin/activate
python -m streamlit run app.py
```

## 11. Guía de uso

La navegación está en el **menú lateral**. Cada módulo tiene sus sub-pestañas:

| Módulo | Sub-pestañas | Qué se hace |
|---|---|---|
| **Inicio** | Resumen · Calidad de datos · Cargar datos | Métricas y estado de espacios, equipos e incidencias; reporte de registros rechazados; subida de archivos oficiales |
| **Espacios** | Reservar · Reservas · Catálogo · Administrar | Reservar (con el panel de reglas vigentes); cancelar reservas; buscar y filtrar espacios; registrar y editar espacios |
| **Recursos** | Inventario · Préstamos · Historial · Administrar | Inventario con filtros; prestar y devolver; historial de estados por equipo; registrar y editar equipos |
| **Incidencias** | Reportar incidencia · Tablero | Reportar, analizar con IA, revisar y registrar; tablero ordenado por prioridad; cerrar incidencias |

> **Préstamo de PCs:** al reservar una sala de cómputo se prestan todos sus PCs operativos durante la reserva. El mensaje de confirmación dice cuántos incluye y avisa si hay más asistentes que PCs operativos. *Recursos → Préstamos → Salas de cómputo* muestra las salas prestadas, y el inventario marca los PCs **en uso con su sala** en este momento. Para préstamos sueltos, registra portátiles o proyectores en *Recursos → Administrar*.

### Casos para la demostración

| Regla | Caso válido | Caso inválido |
|---|---|---|
| 1. Sin cruces | Apolo, mañana de 08:00 a 10:00 | Otra reserva de Apolo de 09:00 a 11:00 → "ya está reservado" |
| 2. Aforo | Sala Azul para 8 personas | Sala Azul para 20 → rechazada y la IA recomienda Cosmos u otra sala |
| 3. Estado | Reservar Cosmos disponible | Poner Cosmos en mantenimiento (Administrar) y reservarla → rechazada |
| 4. Préstamo | Reservar Apolo → incluye el préstamo de sus 34 PCs | Prestar un PC de torre suelto → "se presta junto con todos los PCs de la sala Apolo" |
| 5. Límite | Segundo préstamo de la misma persona | Tercer préstamo → "máximo permitido: 2" |
| 7. Central | Incidencia media en Apolo → sigue disponible | Incidencia crítica en Apolo → queda inhabilitada; al cerrarla se libera |

## 12. Pruebas

```bash
python -m pytest -q
```

174 pruebas cubren las reglas (casos válidos e inválidos), los servicios, los repositorios sobre SQLite temporal, la carga de datos con errores típicos, la regla central y el control de respuestas de la IA. **Las pruebas no llaman a la IA real ni necesitan internet**: la reemplazan para verificar la validación. En la aplicación, la IA nunca se simula.

## 13. Estructura del proyecto

```
Nexo-Campus/
├── app.py                      # Punto de entrada: python -m streamlit run app.py
├── nexo_campus/
│   ├── config.py               # Configuración desde el .env
│   ├── db.py                   # Conexión a SQLite y sesiones
│   ├── errors.py               # ReglaNegocioError, IAError, DatosInconsistentesError
│   ├── models/                 # Espacio, Recurso, Reserva, Prestamo, Incidencia, historiales
│   ├── rules/                  # reservas, prestamos, catalogo, central
│   ├── services/               # reservas, prestamos, incidencias, catalogo, regla_central
│   ├── repositories/           # reservas, prestamos, incidencias, catalogo
│   ├── ai/                     # cliente, triaje, recomendaciones
│   ├── carga/                  # esquema, lectura, normalización, cargador, importación
│   └── ui/                     # estilos, componentes y una pantalla por módulo
├── scripts/cargar_datos.py     # Carga por consola
├── tests/                      # Pruebas con pytest
├── data/raw/                   # Datos oficiales (espacios.csv, recursos.csv)
├── .streamlit/config.toml      # Tema de la interfaz
├── requirements.txt            # Dependencias con versión fija
├── .env.example                # Plantilla de configuración (sin claves)
└── ContextIA.md                # Contexto técnico detallado del proyecto
```

## 14. Seguridad

- **Sin credenciales en el repositorio:** la clave de la IA vive solo en el `.env`, excluido por `.gitignore`. El repositorio incluye `.env.example` sin valores reales.
- **Sin datos personales reales:** solo se usan los datos del reto.
- **La IA nunca se simula:** si falla, se muestra el error y se continúa manualmente.
- **Todo texto de los datos se escapa** antes de mostrarse en HTML.
- La app no tiene inicio de sesión: está pensada para ejecutarse localmente. Para que solo se pueda abrir desde el mismo computador, agrega a `.streamlit/config.toml`:
  ```toml
  [server]
  address = "localhost"
  ```

## 15. Solución de problemas

| Problema | Solución |
|---|---|
| `No module named streamlit` | El entorno virtual no está activado (ver [Ejecución](#10-ejecución)) |
| PowerShell no deja activar `.venv` | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| "La IA no está configurada" | Revisa `AI_BASE_URL`, `AI_API_KEY` y `AI_MODEL` en el `.env` |
| "La clave de la IA no es válida" | La clave del `.env` es incorrecta o fue revocada: genera otra en Google AI Studio |
| "Se alcanzó el límite de consultas a la IA" | El plan gratuito de Gemini limita las consultas por minuto y por día, por modelo. Espera un minuto, usa `AI_MODELO_RESPALDO` o clasifica manualmente |
| "La base de datos ya tiene información" al cargar | Ya estaba cargada. Para empezar de cero: `python scripts/cargar_datos.py --reiniciar` (borra lo registrado desde la app) |
| No aparecen espacios ni equipos | Ejecuta `python scripts/cargar_datos.py` o súbelos en *Inicio → Cargar datos* |
| Streamlit pide `Email:` | Déjalo vacío y presiona Enter |
