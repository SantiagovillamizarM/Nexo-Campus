# ContextIA — Nexo Campus

Contexto técnico del proyecto. Léelo antes de escribir código, y pásaselo a tu asistente de IA (Claude, Copilot, ChatGPT, etc.) para que genere código coherente con el resto del equipo.

El enunciado completo del reto está en [Context.md](Context.md).

---

## 1. Qué es Nexo Campus

Es el **Sistema Central de Gestión Operativa de Campuslands**, un MVP que une en un solo flujo:

1. **Espacios:** reserva de aulas y cubículos sin solapamientos ni exceso de aforo.
2. **Recursos tecnológicos:** préstamo y devolución de equipos, con trazabilidad de estado.
3. **Incidencias:** reporte en lenguaje natural, con la IA a cargo de la clasificación, la priorización y el enrutamiento.

**Regla central:** los tres módulos están conectados. Un espacio o equipo inhabilitado, o con una incidencia grave abierta, **no puede** reservarse ni prestarse.

---

## 2. Lenguaje y stack

**Todo el proyecto está en Python 3.12.**

| Necesidad | Herramienta | Uso |
|---|---|---|
| Interfaz | **Streamlit** | Pantallas, formularios, tablas, mensajes de estado |
| Persistencia | **SQLite** + **SQLModel** | Base de datos en un archivo, sin servidor |
| Carga y limpieza de datos | **pandas** (+ openpyxl para Excel) | Leer los datos oficiales y detectar registros inconsistentes |
| Validación | **Pydantic** (incluido en SQLModel) | Validar entradas y respuestas de la IA |
| IA | **openai** (cliente compatible) | Sirve para Ollama local o cualquier API compatible con OpenAI |
| Configuración | **python-dotenv** | Leer el `.env` |
| Pruebas | **pytest** | Probar las reglas de negocio |

No agregues librerías nuevas sin avisar al equipo. Si alguna es necesaria, se agrega con versión fija en `requirements.txt`.

---

## 3. Arquitectura

```
┌──────────────────────────────┐
│  UI (Streamlit)  app.py, ui/ │  Solo muestra y captura datos
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐      ┌──────────────────────┐
│  Servicios  services/        │ ───▶ │  IA  ai/             │
│  Orquestan cada operación    │      │  Cliente, prompts,   │
│  y aplican las reglas        │      │  validación de JSON  │
└──────┬───────────────┬───────┘      └──────────────────────┘
       ▼               ▼
┌─────────────┐  ┌──────────────────────┐
│  rules/     │  │  repositories/       │
│  Reglas de  │  │  Lectura y escritura │
│  negocio    │  │  en SQLite           │
└─────────────┘  └──────────┬───────────┘
                            ▼
                 ┌──────────────────────┐
                 │  models/  + SQLite   │
                 └──────────────────────┘
```

### Responsabilidad de cada capa

| Carpeta | Hace | NO hace |
|---|---|---|
| `nexo_campus/ui/` y `app.py` | Formularios, tablas, `st.success`, `st.error`, `st.spinner` | Lógica de negocio ni consultas a la BD |
| `nexo_campus/services/` | Recibe la petición de la UI, llama a reglas, repositorios e IA, y devuelve el resultado | Código de Streamlit |
| `nexo_campus/rules/` | Funciones puras que validan una regla de negocio | Acceso a BD ni llamadas a la IA |
| `nexo_campus/repositories/` | Consultas e inserciones en SQLite | Decidir si una operación es válida |
| `nexo_campus/models/` | Definición de tablas y entidades (SQLModel) | Lógica |
| `nexo_campus/ai/` | Cliente de IA, prompts, validación de la respuesta | Decisiones finales sin validar |
| `nexo_campus/config.py` | Única fuente de configuración (lee el `.env`) | — |
| `nexo_campus/db.py` | Conexión a SQLite y sesiones (`obtener_sesion()`) | Consultas de negocio |
| `nexo_campus/carga/` | Lectura, limpieza y validación de los datos oficiales | Reglas de operación del día a día |
| `scripts/` | Script de carga de los datos oficiales a SQLite | — |
| `tests/` | Pruebas de reglas con casos válidos e inválidos | — |
| `data/raw/` | Datos oficiales entregados por Campuslands (sin modificar) | — |

**Regla de oro:** la UI llama a servicios, los servicios llaman a todo lo demás. Nunca al revés.

---

## 4. Estructura del proyecto

```
Nexo-Campus/
├── app.py                  # Punto de entrada: streamlit run app.py
├── nexo_campus/
│   ├── config.py           # Variables del .env
│   ├── errors.py           # Excepciones propias (ReglaNegocioError, IAError...)
│   ├── db.py               # Conexión a SQLite y sesiones
│   ├── carga/              # Carga de datos oficiales (esquema.py = columnas esperadas)
│   ├── models/             # Entidades SQLModel
│   ├── repositories/       # Acceso a datos
│   ├── rules/              # Reglas de negocio (una por función)
│   ├── services/           # Casos de uso
│   ├── ai/                 # Integración con IA
│   └── ui/                 # Pantallas de Streamlit
├── scripts/                # Carga de datos oficiales
├── tests/                  # Pruebas
├── data/raw/               # Datos oficiales
├── requirements.txt
├── .env.example            # Plantilla de configuración (sí se sube)
└── .env                    # Configuración real (NUNCA se sube)
```

---

## 5. Instalación y ejecución

### Qué está en el repo y qué instala cada uno

El repositorio solo guarda **código y recetas**. Lo pesado o personal lo instala cada integrante en su máquina:

| Va en el repo | Lo instala cada uno en local (NO se sube) |
|---|---|
| `requirements.txt` (lista de librerías con versión fija) | `.venv/` con las librerías ya instaladas |
| `.env.example` (plantilla sin secretos) | `.env` con los valores reales |
| `nexo_campus/ai/cliente.py` (cliente de IA) | Ollama y el modelo `llama3.2:3b` (~2 GB) |
| Script de carga en `scripts/` | El archivo `.db` (se regenera con el script) |

### Pasos (una sola vez por máquina)

Todos los comandos se ejecutan en la carpeta raíz del proyecto. Sigue solo el bloque de tu sistema operativo.

#### Windows (PowerShell)

```powershell
# 1. Python 3.12 (si no lo tienes)
winget install -e --id Python.Python.3.12

# 2. Ollama: el servidor de IA local (arranca solo al iniciar sesión)
winget install -e --id Ollama.Ollama

# 3. Descargar el modelo del proyecto (~2 GB). Abre una terminal nueva si no reconoce "ollama"
ollama pull llama3.2:3b

# 4. Crear y activar el entorno virtual con Python 3.12
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
#    Si PowerShell bloquea el script: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

# 5. Instalar dependencias
pip install -r requirements.txt

# 6. Crear el .env y completar AI_API_KEY=ollama y AI_MODEL=llama3.2:3b
copy .env.example .env
```

#### macOS (Terminal, requiere [Homebrew](https://brew.sh))

```bash
# 1. Python 3.12
brew install python@3.12

# 2. Ollama y arrancarlo como servicio (queda activo al reiniciar)
brew install ollama
brew services start ollama
#    Alternativa: descargar la app desde https://ollama.com/download y abrirla

# 3. Descargar el modelo del proyecto (~2 GB)
ollama pull llama3.2:3b

# 4. Crear y activar el entorno virtual con Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# 5. Instalar dependencias
pip install -r requirements.txt

# 6. Crear el .env y completar AI_API_KEY=ollama y AI_MODEL=llama3.2:3b
cp .env.example .env
```

#### Linux (Ubuntu / Debian)

```bash
# 1. Python 3.12 (Ubuntu 24.04 ya lo trae en sus repositorios)
sudo apt update
sudo apt install python3.12 python3.12-venv
#    Ubuntu 22.04 o anterior: primero agregar el repositorio deadsnakes
#    sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update
#    Fedora: sudo dnf install python3.12

# 2. Ollama (el instalador oficial lo deja como servicio que arranca solo; pide sudo)
curl -fsSL https://ollama.com/install.sh | sh

# 3. Descargar el modelo del proyecto (~2 GB)
ollama pull llama3.2:3b

# 4. Crear y activar el entorno virtual con Python 3.12
python3.12 -m venv .venv
source .venv/bin/activate

# 5. Instalar dependencias
pip install -r requirements.txt

# 6. Crear el .env y completar AI_API_KEY=ollama y AI_MODEL=llama3.2:3b
cp .env.example .env
```

### Ejecutar

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
streamlit run app.py
```

```bash
# macOS / Linux
source .venv/bin/activate
streamlit run app.py
```

### Comprobar que Ollama está corriendo

Abre `http://localhost:11434` en el navegador: debe decir `Ollama is running`. Si no:

| Sistema | Cómo arrancarlo |
|---|---|
| Windows | Abrir la app Ollama desde el menú Inicio, o `ollama serve` |
| macOS | `brew services start ollama`, o abrir la app Ollama |
| Linux | `sudo systemctl start ollama`, o `ollama serve` |

> Las instrucciones de Windows están probadas. Las de macOS y Linux siguen la documentación oficial, pero no se han probado en este equipo: si algo falla, avísale al equipo para corregir esta sección.

> **Ojo con `httpx`:** `openai==1.51.2` falla con `httpx` 0.28 o superior (`unexpected keyword argument 'proxies'`). Por eso `requirements.txt` fija `httpx==0.27.2`. No lo quites.

---

## 6. Configuración (.env)

- Toda la configuración se lee **solo** desde `nexo_campus/config.py`:
  ```python
  from nexo_campus import config
  config.AI_MODEL
  config.DATABASE_URL
  ```
- No uses `os.getenv` en otros archivos.
- **Nunca** escribas una clave, contraseña o token en el código ni en un commit. Subir una credencial real cuesta **−10 puntos**, aunque se borre después.
- Si agregas una variable nueva, agrégala también a `.env.example` con un valor de ejemplo.

---

## 7. Reglas de negocio

Cada regla es una **función aislada en `rules/`**, con sus límites en **constantes en mayúsculas al inicio del archivo**. El jurado pedirá cambiar una regla en vivo en menos de 3 minutos, así que tiene que ser fácil de encontrar y modificar.

```python
# nexo_campus/rules/prestamos.py
from nexo_campus.errors import ReglaNegocioError

MAX_PRESTAMOS_ACTIVOS = 2


def validar_limite_prestamos(prestamos_activos: int) -> None:
    if prestamos_activos >= MAX_PRESTAMOS_ACTIVOS:
        raise ReglaNegocioError(
            f"La persona ya tiene {prestamos_activos} préstamos activos "
            f"(máximo permitido: {MAX_PRESTAMOS_ACTIVOS})."
        )
```

- Si una regla no se cumple, se lanza `ReglaNegocioError` (definida en `nexo_campus/errors.py`) con un mensaje **entendible por un usuario final**.
- `errors.py` también define `DatosInconsistentesError` (registros inválidos en los datos de origen) e `IAError` (fallos de la IA). Todas heredan de `NexoCampusError`, así la UI puede capturarlas juntas.
- El servicio la deja pasar y la UI la muestra con `st.error(...)`.
- Las reglas son de **dominio**: solapamientos, aforo, estados y límites. Revisar que un campo no esté vacío no cuenta como regla.

Reglas implementadas (archivo y constante para la modificación en vivo):

| # | Regla | Archivo | Constantes |
|---|---|---|---|
| 1 | Una reserva no se solapa con otra activa del mismo espacio | `rules/reservas.py` | — |
| 2 | Los asistentes no superan el aforo | `rules/reservas.py` | — |
| 3 | No se reservan espacios en mantenimiento o inhabilitados | `rules/reservas.py` | `ESTADOS_RESERVABLES` |
| — | Horario del campus, duración mínima y máxima, nada en el pasado | `rules/reservas.py` | `HORA_APERTURA`, `HORA_CIERRE`, `DURACION_MINIMA_MINUTOS`, `DURACION_MAXIMA_HORAS` |
| 4 | Solo se presta un equipo disponible. Los PC de torre no se prestan sueltos: reservar su sala presta todos sus PCs operativos (`services/reservas.py → pcs_de_la_sala`, `prestamos_de_salas`, `pcs_en_uso`; el PC se liga a la sala por `ubicacion`) | `rules/prestamos.py` | `ESTADOS_PRESTABLES`, `TIPOS_NO_PRESTABLES` |
| 5 | Límite de préstamos activos por persona y duración máxima | `rules/prestamos.py` | `MAX_PRESTAMOS_ACTIVOS`, `DIAS_MAXIMOS_PRESTAMO` |
| — | Códigos válidos y únicos; el aforo no baja de una reserva futura; "prestado" no se pone a mano | `rules/catalogo.py` | `PATRON_CODIGO`, `AFORO_MAXIMO` |
| 6 | **Regla central** (ver abajo) | `rules/central.py` + `services/regla_central.py` | `PRIORIDADES_QUE_BLOQUEAN` |

### Regla central unificada

Una incidencia **alta o crítica** sobre un espacio o equipo lo **inhabilita** al registrarse, así que las reglas 3 y 4 impiden reservarlo o prestarlo. Al **cerrarse**, vuelve al estado que tenía antes (se lee del historial).

- Si quedan otras incidencias graves abiertas sobre lo mismo, sigue bloqueado hasta cerrar la última.
- Si el espacio ya estaba inhabilitado por otra razón (por ejemplo, desde Administrar), cerrar la incidencia no lo libera.
- Un equipo **prestado** no se le quita a quien lo tiene: se bloquea cuando se devuelve.
- Las reservas activas futuras de un espacio bloqueado se avisan en pantalla para reubicarlas; no se cancelan solas.
- Cada bloqueo y liberación queda en el historial (`HistorialEstadoEspacio` y `HistorialEstadoRecurso`, origen `incidencia`).
- Se activa desde `services/incidencias.py` (`registrar_incidencia` y `cerrar_incidencia`).

---

## 8. Uso de la IA

### Proveedor principal: Gemini

Desde el 16/10/2026 el equipo usa **Gemini 2.5 Flash** (Google AI Studio) por su endpoint compatible con OpenAI. No cambió nada del código: solo el `.env`.

```env
AI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
AI_API_KEY=<clave de Google AI Studio, solo en el .env>
AI_MODEL=gemini-2.5-flash
```

| Prueba (16/10/2026) | llama3.2:3b | Gemini 2.5 Flash |
|---|---|---|
| "Huele a gas en la cocina" | aseo / alta ❌ | seguridad / crítica ✅ |
| Robo, desmayo, aire acondicionado, falta de papel | — | 4/4 correctos |
| Tiempo por consulta | 7–8 s | ~2 s |

- **Cuota diaria (importante para la demo)**: el plan gratuito permite **solo 20 consultas por día por modelo** (`GenerateRequestsPerDayPerProjectPerModel-FreeTier`). El 16/10/2026 se agotó la de `gemini-2.5-flash` con las pruebas. Por eso:
  - El modelo principal es `gemini-2.5-flash-lite` (1–2 s por consulta, mismos resultados en las pruebas clave) y el respaldo es `gemini-2.5-flash` (`AI_MODELO_RESPALDO`). Si uno agota su cuota, `cliente.py` usa el otro sin esperar.
  - Si los dos se agotan, la app muestra "Se alcanzó el límite de consultas…" y se clasifica manualmente.
  - **No gasten consultas el día de la demo**: cada "Analizar con IA" y cada reserva rechazada con alternativas consume una. Para más margen, activar facturación en el proyecto de Google AI Studio (el nivel pagado tiene límites mucho más altos y cuesta fracciones de centavo por consulta).
- **Cambios del `.env` sin reiniciar**: `config.py` vuelve a leer la IA si el archivo cambió, así que cambiar la clave o el modelo se aplica en la siguiente consulta.
- **Necesita internet**. Sin conexión, se vuelve a Ollama cambiando las tres líneas del `.env` (están comentadas en `.env.example`).
- La clave es **real**: va solo en el `.env`. Revisar `git status` antes de cada commit.

### Respaldo local: Ollama

Ollama es un programa que corre el modelo **en tu propia máquina** y abre una API en `http://localhost:11434/v1`. Esa API imita la de OpenAI, por eso usamos la librería `openai` para hablar con ella. No hay que pagar ni crear cuenta, y no sale nada a internet.

```
nexo_campus/ai/cliente.py ──HTTP──▶ Ollama (localhost:11434) ──▶ modelo llama3.2:3b
```

- `AI_API_KEY=ollama` **no es una clave real**: Ollama no pide clave, pero la librería `openai` exige un valor no vacío.
- Si el jurado autoriza otra API compatible con OpenAI, solo se cambian `AI_BASE_URL`, `AI_API_KEY` y `AI_MODEL` en el `.env`. El código no cambia. Esa clave sí sería real y **nunca** se sube.

### Cliente disponible (`nexo_campus/ai/cliente.py`)

| Función | Devuelve |
|---|---|
| `consultar_texto(mensaje, instrucciones="")` | Texto libre |
| `consultar_json(mensaje, instrucciones, ModeloPydantic)` | Una instancia del modelo Pydantic, ya validada |

```python
from pydantic import BaseModel
from nexo_campus.ai.cliente import consultar_json

class Triaje(BaseModel):
    categoria: str
    prioridad: str

triaje = consultar_json(texto_usuario, "Responde solo JSON con 'categoria' y 'prioridad'.", Triaje)
```

Cualquier fallo (Ollama apagado, tiempo de espera, error del servidor, JSON inválido) se convierte en `IAError` con un mensaje entendible. El servicio la deja pasar y la UI la muestra con `st.error(...)`.

### Para qué se usa
- **Triaje de incidencias:** a partir del texto libre, la IA devuelve categoría, prioridad, área responsable y justificación.
- **Recomendaciones:** cuando una reserva se rechaza o un espacio se inhabilita, la IA sugiere alternativas.

### Reglas obligatorias
1. **La IA responde en JSON** y la respuesta se valida con un modelo Pydantic. Si no es válida, se trata como error.
2. **Lo que diga la IA se valida contra la BD.** Si recomienda un espacio, ese espacio tiene que existir y estar disponible antes de mostrarse.
3. **Prohibido simular la IA.** Nada de respuestas fijas, `if` que devuelvan resultados inventados ni datos quemados para que la demo "funcione". Cuesta **−15 puntos**.
4. **Si la IA falla** (caída, tiempo de espera, JSON inválido), se muestra un error claro y el usuario puede clasificar a mano. Ese registro queda marcado como `origen = "manual"`, nunca como si lo hubiera hecho la IA.
5. Toda llamada a la IA va dentro de `st.spinner("Analizando con IA...")` en la UI.
6. El cliente de IA usa `config.AI_BASE_URL`, `config.AI_API_KEY`, `config.AI_MODEL` y `config.AI_TIMEOUT`.
7. Nadie crea otro cliente de `openai` por su cuenta: todas las llamadas pasan por `nexo_campus/ai/cliente.py`.

### Triaje de incidencias (`nexo_campus/ai/triaje.py`)

```python
from nexo_campus.ai.triaje import clasificar_incidencia

triaje = clasificar_incidencia("El proyector no enciende", espacio=aula, recurso=proyector, reserva_en_curso=clase)
triaje.categoria          # "tecnologia"
triaje.prioridad          # Prioridad.critica (Enum de models)
triaje.area_responsable   # "soporte_ti"
triaje.justificacion      # una o dos frases en español
```

- Constantes al inicio del archivo (el jurado puede pedir cambiarlas):
  - `CATEGORIAS = ["infraestructura", "tecnologia", "aseo", "seguridad", "bienestar", "otro"]`
  - `AREAS = ["mantenimiento", "soporte_ti", "servicios_generales", "seguridad", "bienestar"]`
  - `AREA_POR_CATEGORIA`: a qué área se enruta cada categoría. `otro` no está en el diccionario, así que puede ir a cualquier área.
- **Contexto:** `espacio`, `recurso` y `reserva_en_curso` son opcionales. Si hay una clase en curso en el espacio, la IA lo sabe y sube la prioridad: un proyector que no enciende es `alta` en un aula vacía y `critica` con clase en curso.
- La respuesta se rechaza (`IAError`) si la IA inventa una categoría, una prioridad o un área fuera de la lista, si deja vacía la justificación o si el área no corresponde a la categoría.
- Si el texto está vacío o supera `MAX_CARACTERES_INCIDENCIA` (1000), lanza `NexoCampusError` sin llamar a la IA.

### Servicio de incidencias (`nexo_campus/services/incidencias.py`)

Dos pasos, para que la persona confirme o corrija lo que propone la IA:

| Función | Qué hace |
|---|---|
| `analizar_incidencia(descripcion, espacio_id=None, recurso_id=None) -> Triaje` | Valida el texto y que el espacio o el equipo existan, busca si hay clase en curso y llama a la IA. **No guarda nada.** Si la IA falla, deja pasar el `IAError` |
| `origen_segun_propuesta(propuesta, categoria, prioridad, area) -> OrigenClasificacion` | Ayuda para la UI: `ia` si la persona aceptó la propuesta tal cual, `manual` si cambió algo o si no hubo propuesta (la IA falló) |
| `registrar_incidencia(descripcion, reportante, espacio_id, recurso_id, categoria, prioridad, area_responsable, justificacion, origen) -> Incidencia` | Valida que los valores estén en las listas y guarda la incidencia abierta. `origen` solo puede ser `ia` o `manual` |
| `cerrar_incidencia(incidencia_id) -> Incidencia` | Cierra la incidencia. Rechaza las que no existen o ya están cerradas |

Flujo esperado en la UI (P4):

```python
try:
    with st.spinner("Analizando con IA..."):
        propuesta = analizar_incidencia(texto, espacio_id, recurso_id)
except IAError as exc:
    st.error(str(exc))            # y se muestran los selectores vacíos para clasificar a mano
    propuesta = None
# ... la persona acepta o corrige con selectores ...
origen = origen_segun_propuesta(propuesta, categoria, prioridad, area)
registrar_incidencia(texto, reportante, espacio_id, recurso_id, categoria, prioridad, area, justificacion, origen)
```

Depende de `repositories/incidencias.py` (`guardar_incidencia`, `obtener_incidencia`, `cerrar_incidencia`) y de `obtener_recurso` en `repositories/prestamos.py`, ambos de P1. Hasta que existan, el servicio no se puede importar en la app, pero sus pruebas (`tests/test_servicio_incidencias.py`) ya corren con repositorios en memoria. La regla central (inhabilitar y rehabilitar espacios o equipos) es de P2.

### Recomendaciones de espacios (`nexo_campus/ai/recomendaciones.py`)

```python
from nexo_campus.ai.recomendaciones import recomendar_espacios
from nexo_campus.repositories.reservas import espacios_disponibles

candidatos = espacios_disponibles(inicio, fin, asistentes)        # salen de la BD, nunca de la IA
recomendaciones = recomendar_espacios(motivo, asistentes, candidatos)
for r in recomendaciones:
    r.orden, r.espacio_id, r.razon                                 # 1 = la mejor opción
```

- La IA solo **ordena y explica**. Si devuelve un `espacio_id` que no está entre los candidatos, o uno repetido, se descarta y el orden se renumera.
- Devuelve como máximo `MAX_RECOMENDACIONES` (3). Al prompt se envían como máximo `MAX_CANDIDATOS_EN_PROMPT` (15) candidatos.
- Sin candidatos devuelve `[]` sin llamar a la IA.
- Si la IA falla, o si todas sus recomendaciones eran inventadas, lanza `IAError`. La UI muestra entonces los candidatos sin orden, con el aviso "sin recomendación de IA".

### Qué tan confiable resultó (llama3.2:3b en Ollama local, 16/10/2026)

**Triaje.** 15 incidencias realistas pasadas por `clasificar_incidencia` contra Ollama con el prompt final. La IA usa temperatura 0, así que la misma consulta da siempre la misma respuesta: dos corridas seguidas dieron la misma tabla.

| Tipo | Reporte | Contexto | Esperado | Respuesta de la IA | Tiempo | |
|---|---|---|---|---|---|---|
| fácil | El aire acondicionado del aula no enfría y hace mucho calor | aula | infraestructura / media | infraestructura / media / mantenimiento | 7.3 s | ✅ |
| fácil | No hay papel higiénico en el baño del segundo piso | — | aseo / baja | aseo / baja / servicios_generales | 6.7 s | ✅ |
| fácil | Se robaron un portátil del cubículo mientras estábamos en el descanso | cubículo | seguridad / alta | seguridad / alta / seguridad | 7.1 s | ✅ |
| urgente | Sale humo del tomacorriente y huele a quemado | aula | seguridad / critica | seguridad / critica / seguridad | 8.1 s | ✅ |
| urgente | Huele a gas en la cocina de la cafetería | — | seguridad / critica | seguridad / critica / seguridad | 7.5 s | ✅ |
| urgente | Un compañero se desmayó en el pasillo del tercer piso | — | bienestar / critica | bienestar / critica / bienestar | 7.2 s | ✅ |
| contexto | El proyector no enciende | equipo, aula, clase en curso | tecnologia / critica | tecnologia / critica / soporte_ti | 8.2 s | ✅ |
| contexto | El proyector no enciende | equipo, aula | tecnologia / alta o media | tecnologia / alta / soporte_ti | 6.7 s | ✅ |
| contexto | Se fue la luz | aula, clase en curso | infraestructura / critica | infraestructura / media / mantenimiento | 7.9 s | ❌ |
| ambigua | La sala no tiene marcadores para el tablero | aula | infraestructura / baja | otro / baja / servicios_generales | 7.7 s | ❌ |
| ambigua | El portátil está muy lento y se calienta mucho | equipo | tecnologia / media | tecnologia / media / soporte_ti | 7.1 s | ✅ |
| irrelevante | hola | — | otro / baja | otro / baja / servicios_generales | 6.2 s | ✅ |
| irrelevante | La comida de la cafetería está muy cara | — | otro / baja | otro / baja / servicios_generales | 6.6 s | ✅ |
| mal español | el wifi no sirbe en todo el piso 2 nadie se puede conetar | — | tecnologia / alta | tecnologia / alta / soporte_ti | 7.2 s | ✅ |
| mal español | ai un man raro tomandole fotos a las peladas en la entrada | — | seguridad / alta | seguridad / alta / seguridad | 7.0 s | ✅ |

Resumen: **13/15 correctos** (14/15 en categoría y 14/15 en prioridad). Todos los casos de riesgo para personas salieron `critica`, ninguna respuesta tuvo un JSON inválido y la consulta tarda de 6 a 8 s.

**Recomendaciones.** Con 6 espacios de prueba, la IA devolvió 3 opciones coherentes en cada caso: el laboratorio para una clase con computadores, cubículos para asesorías y reuniones pequeñas, y el auditorio para una charla de 90 personas, que era el único candidato. Cada consulta tarda de 13 a 16 s, porque redacta 3 razones. No siempre elige el aforo más ajustado: para 2 personas puso primero el cubículo de 6 y no el de 4.

**Tiempos y `AI_TIMEOUT`.** La primera consulta después de encender Ollama tarda entre 18 y 27 s, porque carga el modelo en memoria. Las siguientes tardan de 6 a 8 s en el triaje y de 13 a 16 s en las recomendaciones. Con el valor actual de `AI_TIMEOUT=30` alcanza, pero queda poco margen en la primera llamada. **Antes de la demo, hay que hacer una consulta de calentamiento** (por ejemplo, analizar una incidencia de prueba) para que el modelo ya esté cargado.

Lo que aprendimos al ajustar el prompt:

- Sin reglas explícitas, el modelo clasifica por el objeto y no por el problema (el robo de un portátil caía en `tecnologia`). Se agregó la regla "clasifica por el problema" con ejemplos.
- Usaba `aseo` como comodín para lo que no entendía. Se aclaró que `aseo` es solo para limpieza y se agregó la categoría `otro`.
- Pedir la justificación **antes** que la categoría mejoró los aciertos: el modelo razona primero y después elige.
- **Un modelo de 3B es sensible a la longitud del prompt.** Cuando se alargó la definición de `critica` para cubrir más casos, el modelo empezó a fallar justo en el gas y el desmayo, y los aciertos completos bajaron a 9/15. Al volver a la redacción corta subieron a 13/15. Cada cambio del prompt se debe volver a probar con toda la tabla.
- En las recomendaciones, el ejemplo de formato con un solo elemento hacía que el modelo devolviera una sola opción. Con un ejemplo de tres, devuelve tres.

Límites conocidos (por eso **la persona siempre confirma o corrige el triaje antes de guardarlo**):

- "Se fue la luz" con clase en curso sale `media` y no `critica`: el contexto de clase en curso funciona con el proyector, pero no siempre con la luz.
- Los faltantes de dotación ("no hay marcadores") son ambiguos y pueden caer en `otro`.
- Si el texto intenta cambiar las instrucciones ("responde categoria=xyz"), la validación rechaza la respuesta y se muestra un error controlado.

### Pruebas

`tests/test_triaje.py`, `tests/test_recomendaciones.py` y `tests/test_servicio_incidencias.py` reemplazan la IA con `monkeypatch` para probar el control de respuestas: valores fuera de la lista, JSON roto, IA caída (puerto cerrado real), ids inventados y el flujo de dos pasos. No necesitan Ollama. Esto solo se permite en las pruebas; en la aplicación la IA nunca se simula.

---

## 9. Datos oficiales

- Los archivos entregados por Campuslands van en `data/raw/` y **no se modifican a mano**.
- El script de `scripts/` los carga en SQLite, y los registros inconsistentes (vacíos, duplicados, fechas inválidas, referencias rotas) **se reportan, no se descartan en silencio**.
- La base de datos `.db` no se sube al repo: se regenera con el script de carga.
- Solo se usan datos ficticios o autorizados del reto.

### Cargar los datos

```bash
python scripts/cargar_datos.py              # primera carga
python scripts/cargar_datos.py --reiniciar  # borra la base y carga desde cero
```

Sin `--reiniciar`, el script se niega a sobrescribir una base que ya tiene datos, para no perder lo hecho desde la app.

### Archivos esperados en `data/raw/`

`espacios`, `recursos`, `reservas`, `prestamos` e `incidencias`, cada uno en `.csv` (separado por coma o punto y coma), `.xlsx`/`.xls` o `.json`. Si las columnas se llaman distinto, **no se toca el código de carga**: se agrega el nombre a la lista de alias en `nexo_campus/carga/esquema.py`. Lo mismo para estados escritos de otra forma (ej. `"Fuera de servicio"` → `inhabilitado`).

### Qué revisa la carga

| Revisión | Resultado |
|---|---|
| Campo obligatorio vacío, número o fecha inválidos, estado desconocido | Rechazado |
| Fila idéntica repetida o ID duplicado | Rechazado (se queda el primero) |
| ID huérfano (reserva, préstamo o incidencia que apunta a algo que no existe) | Rechazado |
| Reserva con fin antes del inicio, más asistentes que aforo o solapada con otra activa | Rechazado |
| Préstamo con fechas incoherentes o segundo préstamo activo del mismo equipo | Rechazado |
| Estado vacío | Cargado con valor por defecto + advertencia |
| Equipo `disponible` con préstamo activo, o `prestado` sin préstamo | Estado corregido + advertencia |

Todo queda en la tabla `RegistroInconsistente` (archivo, fila, ID, motivo, tipo). La UI lo consulta con `nexo_campus/repositories/catalogo.py` → `listar_inconsistencias()`, junto con `listar_espacios()`, `listar_recursos()` y `listar_incidencias()`.

### Usar la base desde el código

```python
from sqlmodel import select
from nexo_campus.db import obtener_sesion
from nexo_campus.models import Espacio, EstadoEspacio

with obtener_sesion() as sesion:
    disponibles = sesion.exec(select(Espacio).where(Espacio.estado == EstadoEspacio.disponible)).all()
```

Esto va en `repositories/`, nunca en la UI.

---

## 10. Manejo de errores e interfaz

- La aplicación **nunca** debe mostrar un traceback de Python al usuario.
- Cada acción muestra su estado:
  - Cargando: `st.spinner(...)`
  - Éxito: `st.success(...)`
  - Error de regla o validación: `st.error(...)` con el motivo
  - Advertencia (por ejemplo, datos inconsistentes): `st.warning(...)`
- Los errores inesperados se capturan en la capa de servicios o de UI y se convierten en un mensaje entendible.

---

## 11. Convenciones de código

- **Idioma:** nombres del dominio en español (`reserva`, `espacio`, `prestamo`, `incidencia`), en `snake_case`. Las clases en `PascalCase` (`Reserva`, `ServicioPrestamos`).
- Sin tildes ni `ñ` en nombres de variables, funciones o archivos (`prestamo`, no `préstamo`). En los mensajes al usuario sí se usan.
- Estados como constantes o `Enum`, nunca como texto suelto repetido:
  - Espacios y recursos: `disponible`, `prestado`, `mantenimiento`, `inhabilitado`, `danado`
  - Incidencias: `abierta`, `en_proceso`, `cerrada`
  - Prioridad: `baja`, `media`, `alta`, `critica`
- Funciones cortas, con *type hints*, y una sola responsabilidad.
- Comentarios solo donde el *porqué* no sea obvio.

---

## 12. Git

- Commits pequeños y frecuentes, con mensajes claros en español:
  - `feat: validar solapamiento de reservas`
  - `fix: manejar fechas inválidas en carga de datos`
  - `docs: instrucciones de instalación en README`
- `git pull` antes de empezar a trabajar y antes de cada `push`.
- Antes de cada commit, revisa con `git status` que no vaya un `.env`, un `.db` ni una carpeta `.venv`.
