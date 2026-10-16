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

```powershell
# 1. Crear y activar el entorno virtual
python -m venv .venv
.\.venv\Scripts\Activate.ps1        # Windows (PowerShell)
# source .venv/bin/activate         # Linux / macOS

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Crear el .env a partir de la plantilla y completarlo
copy .env.example .env              # Windows
# cp .env.example .env              # Linux / macOS

# 4. Ejecutar la aplicación
streamlit run app.py
```

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

---

## 9. Datos oficiales

- Los archivos entregados por Campuslands van en `data/raw/` y **no se modifican a mano**.
- El script de `scripts/` los carga en SQLite, y los registros inconsistentes (vacíos, duplicados, fechas inválidas, referencias rotas) **se reportan, no se descartan en silencio**.
- La base de datos `.db` no se sube al repo: se regenera con el script de carga.
- Solo se usan datos ficticios o autorizados del reto.

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
