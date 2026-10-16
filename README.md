# Nexo Campus

Sistema Central de Gestión Operativa de Campuslands: espacios, recursos tecnológicos e incidencias en un único flujo asistido por IA.

> Documento en construcción durante la hackatón.

## Estado actual de la interfaz (P4)

Primera tarea completada: esqueleto de Streamlit con cuatro pestañas informativas:

- **Inicio:** futuro resumen de la operación del campus.
- **Espacios:** futura consulta de espacios y reservas.
- **Recursos:** futuros préstamos y devoluciones de equipos.
- **Incidencias:** futuras incidencias y solicitudes.

El punto de entrada es `app.py`. Utiliza componentes nativos de Streamlit y no
importa servicios, configuración de IA ni acceso a la base de datos. La conexión
con los servicios del equipo corresponde a las siguientes etapas.

## Problema

_Pendiente._

## Integrantes

- _Pendiente_

## Stack tecnológico

- Python 3.12
- Streamlit (interfaz)
- SQLite + SQLModel (persistencia)
- pandas (carga y limpieza de datos)
- Pydantic (validación)
- Cliente compatible con OpenAI para el modelo de IA autorizado

## Uso de la IA

_Pendiente._

## Reglas de negocio implementadas

_Pendiente._

## Instalación y ejecución

La interfaz está en su etapa inicial: cuatro pestañas informativas, sin operaciones
ni conexión con datos, servicios o IA. Este esqueleto no requiere un archivo `.env`
ni Ollama. Ejecuta los comandos desde la raíz del repositorio con **Python 3.12**,
la versión acordada por el equipo.

### Windows (PowerShell)

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### Linux / macOS

Si ya tienes Python 3.12 instalado:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

### Linux: si no existe el comando `python3.12`

Este fue el procedimiento utilizado en el equipo de P4, que inicialmente tenía
Python 3.14. No es necesario cambiar las versiones de `requirements.txt`.
Requiere conexión a internet y `curl` para instalar uv; si uv ya está instalado,
omite el primer comando.

Ejecuta cada comando por separado y continúa solo si termina correctamente:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
~/.local/bin/uv python install 3.12
~/.local/bin/uv venv --python 3.12 --seed .venv
source .venv/bin/activate
python --version
python -m pip install -r requirements.txt
python -m streamlit run app.py
```

Antes de instalar las dependencias, `python --version` debe mostrar Python 3.12.x.
La opción `--seed` incluye pip dentro del entorno virtual. Si `.venv` ya existe
y funciona con Python 3.12, solo necesitas activarlo; no vuelvas a crearlo.

### Abrir y comprobar la interfaz

Si Streamlit solicita un correo en `Email:`, puedes dejarlo vacío y pulsar Enter.
Abre la dirección local que indique Streamlit en la terminal (normalmente
`http://localhost:8501`). Debes ver las pestañas Inicio, Espacios, Recursos e
Incidencias; cada una muestra un título y un mensaje sobre su contenido futuro.

La primera tarea se comprueba seleccionando las cuatro pestañas y verificando
que cambia el contenido sin mostrar errores. El usuario confirmó esta navegación
y compartió capturas de Inicio y Espacios. La instalación de las dependencias se
completó con Python 3.12.15 en Linux. Los comandos de Windows y macOS se conservan
como guía del equipo; no se verificaron durante esta entrega.

Mantén la terminal abierta mientras utilizas la aplicación. Para detenerla,
pulsa `Ctrl+C`. Para volver a ejecutarla en Linux, desde la raíz del repositorio:

```bash
source .venv/bin/activate
python -m streamlit run app.py
```

El entorno `.venv`, las credenciales `.env` y las bases de datos locales están
excluidos mediante `.gitignore` y no deben incluirse en la entrega.
