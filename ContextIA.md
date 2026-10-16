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

Reglas previstas:

1. Una reserva no puede solaparse con otra en el mismo espacio.
2. El número de asistentes no puede superar el aforo del espacio.
3. No se reservan espacios inhabilitados o en mantenimiento.
4. No se presta un equipo ya prestado, en mantenimiento o dañado.
5. Límite de préstamos activos por persona.
6. **Regla central:** una incidencia de prioridad alta sobre un espacio o equipo lo inhabilita hasta que se cierre.

---

## 8. Uso de la IA

### Cómo funciona la conexión

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
