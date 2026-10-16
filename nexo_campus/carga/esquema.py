"""Qué archivos y columnas espera la carga de datos.

ESTE ES EL ARCHIVO QUE SE AJUSTA cuando lleguen los datos oficiales: si una columna se llama
distinto, se agrega su nombre a la lista de alias del campo. Los nombres se comparan sin tildes,
en minúsculas y con "_" en lugar de espacios ("Capacidad Máxima" == "capacidad_maxima").
"""

# Nombre base de cada archivo en data/raw/ (sin extensión: .csv, .xlsx, .xls o .json)
ARCHIVOS = {
    "espacios": "espacios",
    "recursos": "recursos",
    "reservas": "reservas",
    "prestamos": "prestamos",
    "incidencias": "incidencias",
}

# campo del modelo -> nombres de columna aceptados en el archivo
COLUMNAS = {
    "espacios": {
        "id": ["id", "codigo", "id_espacio", "codigo_espacio"],
        "nombre": ["nombre", "nombre_espacio"],
        "tipo": ["tipo", "tipo_espacio"],
        "aforo": ["aforo", "capacidad", "capacidad_maxima"],
        "ubicacion": ["ubicacion", "sede", "bloque"],
        "estado": ["estado", "estado_espacio"],
    },
    "recursos": {
        "id": ["id", "codigo", "id_recurso", "codigo_recurso", "id_equipo", "serial"],
        "nombre": ["nombre", "nombre_recurso", "equipo"],
        "tipo": ["tipo", "tipo_recurso", "categoria"],
        "estado": ["estado", "estado_recurso"],
        "ubicacion": ["ubicacion", "sede"],
    },
    "reservas": {
        "id": ["id", "codigo", "id_reserva"],
        "espacio_id": ["espacio_id", "id_espacio", "codigo_espacio", "espacio"],
        "solicitante": ["solicitante", "responsable", "usuario", "reservado_por"],
        "fecha": ["fecha", "fecha_reserva", "dia"],  # opcional: cuando inicio y fin solo traen la hora
        "inicio": ["inicio", "fecha_inicio", "hora_inicio", "desde"],
        "fin": ["fin", "fecha_fin", "hora_fin", "hasta"],
        "asistentes": ["asistentes", "num_asistentes", "cantidad_personas", "personas"],
        "motivo": ["motivo", "proposito", "descripcion"],
        "estado": ["estado", "estado_reserva"],
    },
    "prestamos": {
        "id": ["id", "codigo", "id_prestamo"],
        "recurso_id": ["recurso_id", "id_recurso", "codigo_recurso", "id_equipo", "recurso", "equipo"],
        "solicitante": ["solicitante", "responsable", "usuario", "prestado_a"],
        "fecha_prestamo": ["fecha_prestamo", "fecha_inicio", "fecha_entrega", "fecha"],
        "fecha_devolucion_prevista": ["fecha_devolucion_prevista", "fecha_limite", "devolucion_prevista"],
        "fecha_devolucion": ["fecha_devolucion", "fecha_devolucion_real", "devuelto_en"],
        "estado": ["estado", "estado_prestamo"],
    },
    "incidencias": {
        "id": ["id", "codigo", "id_incidencia", "ticket"],
        "descripcion": ["descripcion", "detalle", "mensaje", "reporte"],
        "reportante": ["reportante", "reportado_por", "usuario", "solicitante"],
        "espacio_id": ["espacio_id", "id_espacio", "codigo_espacio", "espacio"],
        "recurso_id": ["recurso_id", "id_recurso", "codigo_recurso", "id_equipo", "recurso", "equipo"],
        "fecha_reporte": ["fecha_reporte", "fecha", "fecha_creacion"],
        "categoria": ["categoria", "tipo"],
        "prioridad": ["prioridad", "urgencia"],
        "area_responsable": ["area_responsable", "area", "responsable"],
        "estado": ["estado", "estado_incidencia"],
        "fecha_cierre": ["fecha_cierre", "fecha_resolucion"],
    },
}

# Columnas sin las cuales el archivo completo no se puede cargar
OBLIGATORIAS = {
    "espacios": ["id", "nombre", "aforo"],
    "recursos": ["id", "nombre"],
    "reservas": ["espacio_id", "solicitante", "inicio", "fin", "asistentes"],
    "prestamos": ["recurso_id", "solicitante", "fecha_prestamo"],
    "incidencias": ["descripcion"],
}

# Valores alternativos de los datos de origen -> valor del Enum (ya normalizados: sin tildes, minúsculas, "_")
ALIAS_ESTADO_ESPACIO = {
    "activo": "disponible",
    "habilitado": "disponible",
    "libre": "disponible",
    "en_mantenimiento": "mantenimiento",
    "inactivo": "inhabilitado",
    "deshabilitado": "inhabilitado",
    "fuera_de_servicio": "inhabilitado",
    "cerrado": "inhabilitado",
}
ALIAS_ESTADO_RECURSO = {
    "activo": "disponible",
    "operativo": "disponible",
    "libre": "disponible",
    "en_prestamo": "prestado",
    "ocupado": "prestado",
    "en_mantenimiento": "mantenimiento",
    "en_reparacion": "mantenimiento",
    "averiado": "danado",
    "malo": "danado",
    "inactivo": "inhabilitado",
    "dado_de_baja": "inhabilitado",
    "fuera_de_servicio": "inhabilitado",
}
ALIAS_ESTADO_RESERVA = {
    "confirmada": "activa",
    "vigente": "activa",
    "aprobada": "activa",
    "anulada": "cancelada",
}
ALIAS_ESTADO_PRESTAMO = {
    "en_curso": "activo",
    "prestado": "activo",
    "vigente": "activo",
    "finalizado": "devuelto",
    "cerrado": "devuelto",
}
ALIAS_ESTADO_INCIDENCIA = {
    "nueva": "abierta",
    "pendiente": "abierta",
    "abierto": "abierta",
    "en_curso": "en_proceso",
    "en_progreso": "en_proceso",
    "resuelta": "cerrada",
    "cerrado": "cerrada",
    "solucionada": "cerrada",
}
ALIAS_PRIORIDAD = {
    "urgente": "critica",
    "muy_alta": "critica",
    "normal": "media",
    "moderada": "media",
    "menor": "baja",
}
