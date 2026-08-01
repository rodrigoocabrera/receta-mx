# Catálogo de medicamentos

## Objetivo

Receta MX requiere una terminología versionada para que un medicamento no dependa de texto libre. El código identifica un concepto prescribible concreto: denominación genérica, forma, concentración, vía y presentación.

## Fuentes y niveles de autoridad

No toda lista pública de medicamentos representa lo mismo:

- **Compendio Nacional de Insumos para la Salud:** referencia para insumos del sector público.
- **Registro sanitario de COFEPRIS:** evidencia de productos autorizados y sus titulares/presentaciones.
- **Datos abiertos institucionales:** inventarios o adquisiciones de una institución; no constituyen por sí solos un catálogo nacional de prescripción.
- **Catálogo demo Receta MX:** datos sintéticos para desarrollo; no autoritativos y no aptos para atención real.

La alpha no consume automáticamente el visor de COFEPRIS porque no se documentó una API pública estable para integración. El diseño usa un adaptador reemplazable para incorporar en el futuro una fuente oficial, firmada y versionada.

## Modelo mínimo

```json
{
  "code": "RXMX-DEMO-AMOX-500-CAP",
  "generic_name": "AMOXICILINA",
  "form": "CÁPSULA",
  "strength": "500 mg",
  "route": "ORAL",
  "presentation": "Envase con 12 cápsulas",
  "sale_fraction": "IV",
  "controlled_group": "NONE",
  "atc_code": "J01CA04",
  "requires_prescription": true,
  "refill_policy": "NEW_PRESCRIPTION",
  "source_record_id": "DEMO-001"
}
```

## API alpha

Buscar por nombre, código, forma o ATC:

```bash
curl 'http://localhost:8080/api/catalog?q=amoxicilina&limit=10'
```

Filtrar por fracción o grupo regulatorio:

```bash
curl 'http://localhost:8080/api/catalog?sale_fraction=I'
curl 'http://localhost:8080/api/catalog?controlled_group=ESTUPEFACIENTE'
```

Obtener un registro:

```bash
curl 'http://localhost:8080/api/catalog/RXMX-DEMO-AMOX-500-CAP'
```

Cuando una receta incluye `code`, el servidor contrasta denominación, fracción y grupo controlado con la versión activa. Un código desconocido o una discrepancia se rechazan.

## Requisitos para una fuente nacional

Una fuente productiva debe incluir:

- versión, fecha efectiva, emisor y jurisdicción;
- firma del conjunto de datos y hash publicable;
- historial de altas, cambios, suspensiones y bajas;
- identificador estable del concepto clínico;
- vínculo separado con productos comerciales y registros sanitarios;
- reglas regulatorias por fecha;
- equivalencias y sustitución;
- endpoint de consulta y descargas completas para contingencia;
- SLA, control de cambios y mecanismo de corrección.

El catálogo clínico y el inventario de una farmacia son objetos distintos. Que un medicamento exista en el catálogo no implica que esté disponible, cubierto o autorizado para surtirse en cualquier establecimiento.
