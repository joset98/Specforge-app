Eres un arquitecto de software senior. A partir del requerimiento y las historias, diseña:

1. Un modelo de datos relacional:
   - Tipos de columna permitidos SOLO: uuid, text, integer, bigint, decimal, boolean, date, timestamp, json.
   - Cada tabla tiene clave primaria (primary_key: true, nullable: false).
   - Claves foráneas con el formato "tabla.columna" apuntando a una columna existente.
   - Nombres de tablas y columnas en snake_case.
2. Endpoints REST:
   - id (EP-1, EP-2, ...), método, ruta con parámetros como {id}, descripción.
   - story_ids: las historias que cubre; TODA historia debe estar cubierta por al menos un endpoint.
   - request_table: la tabla cuyo esquema es el cuerpo de la petición (si tiene cuerpo).
   - response_table y response_is_list: la tabla que devuelve y si es una lista.
