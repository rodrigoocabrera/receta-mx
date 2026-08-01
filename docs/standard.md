# Estándar Receta MX 0.1 Alpha

## 1. Propósito

Definir una representación nacional, abierta e interoperable de la receta electrónica y de su ciclo de vida, utilizable por instituciones públicas, privadas y sociales, sin convertir la receta en un expediente clínico completo.

## 2. Principios

1. **Seguridad del paciente:** validación de identidad, autorización profesional, interacciones, advertencias y trazabilidad.
2. **Neutralidad tecnológica:** ningún proveedor es indispensable para emitir, verificar o surtir una receta.
3. **Interoperabilidad:** contratos abiertos, identificadores persistentes, catálogos versionados y exportación FHIR.
4. **Privacidad por diseño:** datos mínimos, acceso por propósito, consentimiento verificable y auditoría.
5. **Continuidad rural:** identificadores alternativos, representación impresa y contingencia offline.
6. **Portabilidad público–privada:** la receta conserva validez técnica al cruzar instituciones, sujeta a la regulación y financiamiento aplicables.
7. **No repudio:** firma avanzada o equivalente regulado, sello de tiempo, integridad y registro de eventos.

## 3. Actores

- **Autoridad sanitaria:** define catálogos, permisos, sanciones, reglas y supervisión.
- **Registro Nacional de Prescriptores:** asigna el Número Nacional de Prescriptor y publica atributos verificables.
- **PARC:** proveedor autorizado que enrola y verifica identidad, e.firma, cédula, prueba de vida y atributos; certifica la integridad de recetas y reporta eventos. No diagnostica, prescribe ni modifica el contenido clínico.
- **Prescriptor:** profesional autorizado conforme a la LGS y su ámbito de competencia.
- **Farmacia:** establecimiento autorizado para dispensar las fracciones que correspondan.
- **Personal de farmacia:** persona identificada individualmente, autenticada y vinculada a una farmacia.
- **Paciente o representante:** titular de la receta y del mecanismo de autorización de acceso.
- **Pagador:** institución pública, aseguradora, empleador, paciente u otro responsable financiero.

## 4. Número Nacional de Prescriptor

Formato alpha:

```text
MXP-<CLASE>-<10 DÍGITOS>
```

Ejemplos de clase: `MED`, `HOM`, `DEN`, `VET`, `ENF`, `PAS`.

El número:

- no sustituye la cédula profesional;
- no revela directamente la cédula;
- se asigna después de validar identidad y atributos;
- puede suspenderse, revocarse o limitarse;
- debe firmarse o vincularse criptográficamente con la e.firma del profesional;
- incorpora atributos separados para controlados, ámbito humano/veterinario, especialidad, institución y vigencia.

## 5. Validación de prescriptores

El expediente de enrolamiento debe registrar como mínimo:

- CURP o identidad equivalente;
- cédula y título aplicables;
- identificación oficial;
- prueba de vida;
- certificado de e.firma y estado de vigencia;
- cotejo automatizado;
- revisión manual;
- profesión y ámbito de competencia;
- permisos para medicamentos controlados;
- teléfono y medio de contacto profesional;
- evidencia, fecha, operador y versión de las reglas utilizadas.

La clave privada de e.firma permanece siempre bajo control exclusivo del titular.

## 6. Catálogo de autorizaciones

Los atributos deben ser explícitos y verificables. Ejemplo:

```json
{
  "can_prescribe_general": true,
  "allowed_controlled_groups": ["PSICOTROPICO_IV"],
  "allowed_drug_codes": [],
  "scope": "HUMAN",
  "valid_from": "2026-07-31",
  "valid_until": "2027-07-31"
}
```

Los catálogos de fracciones, sustancias y productos deben venir de una fuente autoritativa versionada. Ningún PARC puede autodeclarar permisos de controlados: sólo aplica atributos emitidos o reconocidos por la autoridad y el registro nacional.

## 7. Identidad del paciente

Identificador primario: CURP.

Alternativas controladas: `TEMP_RURAL`, `NEWBORN`, `FOREIGN`, `OTHER`.

La consulta por farmacia exige:

1. autenticación del empleado mediante CURP y contraseña o factor equivalente;
2. vinculación a una farmacia activa;
3. identificador del paciente;
4. autorización del paciente mediante código, OTP, credencial o contingencia autorizada;
5. registro de finalidad, fecha, farmacia y persona que consultó.

La farmacia recibe como máximo las diez recetas recientes necesarias para seguridad de dispensación. No obtiene un expediente clínico general.

## 8. Contenido mínimo de receta

- versión del esquema;
- folio nacional único;
- fecha y vigencia;
- paciente e identificador;
- prescriptor, número nacional y cédula;
- medio de contacto;
- medicamento por denominación genérica;
- código de catálogo;
- forma, concentración, dosis, vía, frecuencia y duración;
- cantidad;
- fracción de venta y grupo controlado;
- sustitución permitida;
- resurtidos autorizados;
- advertencias e interacciones;
- origen público/privado;
- ruta de surtimiento;
- pagador;
- firma y sello de tiempo;
- estado de ciclo de vida.

## 9. Código bidimensional

La representación impresa contiene un código QR o Data Matrix con una URL HTTPS o un objeto firmado compacto. No debe incluir diagnóstico ni datos clínicos sensibles en texto abierto.

El verificador debe mostrar:

- autenticidad e integridad;
- estado vigente, cancelado, vencido, parcial o surtido;
- datos mínimos del paciente;
- prescriptor y contacto;
- medicamentos y remanentes;
- advertencias;
- eventos de surtimiento permitidos.

## 10. Estados

- `DRAFT`
- `ACTIVE`
- `PARTIALLY_DISPENSED`
- `DISPENSED`
- `CANCELLED`
- `EXPIRED`
- `SUSPENDED`

Cada transición genera un evento inmutable y auditable.

## 11. Surtimiento

La farmacia captura por partida:

- cantidad;
- marca efectivamente surtida;
- lote;
- caducidad cuando aplique;
- sustitución;
- modo: inicial, parcial, resurtido o transferencia por desabasto;
- establecimiento;
- CURP del empleado;
- fecha y hora;
- saldo y resurtidos restantes.

Para controlados deben bloquearse duplicados, surtimientos fuera de vigencia, cantidades superiores, resurtidos no autorizados y establecimientos sin permiso.

## 12. Interoperabilidad pública–privada

Una institución pública puede emitir `PUBLIC_FIRST_PRIVATE_FALLBACK`. Cuando no exista abasto, se registra un evento de transferencia con causa, institución, producto faltante y farmacia privada. La fase de pago deberá usar una autorización financiera independiente de la receta clínica.

BIN y PCN pueden incorporarse en el módulo de enrutamiento y reclamaciones de pagadores, pero no forman parte del núcleo clínico ni deben ser obligatorios para personas sin seguro.

## 13. Relación con expediente clínico

Receta MX no pretende almacenar toda la historia clínica. Sin embargo, la receta y sus eventos son registros electrónicos de salud y deben cumplir controles de autenticidad, confidencialidad, integridad, disponibilidad, conservación e interoperabilidad compatibles con NOM-004 y NOM-024.

## 14. Conformidad

Una implementación sólo puede declararse conforme después de superar:

- pruebas de esquema;
- pruebas de ciclo de vida;
- seguridad y privacidad;
- catálogos autoritativos;
- validación criptográfica;
- interoperabilidad;
- auditoría;
- requisitos regulatorios y de autoridad.
