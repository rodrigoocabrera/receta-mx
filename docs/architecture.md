# Arquitectura operativa de Receta MX

## Qué es Receta MX

Receta MX es un **estándar abierto de intercambio y ciclo de vida de recetas electrónicas**, acompañado por una implementación de referencia. No es una aplicación única, una farmacia, un expediente clínico ni una autoridad sanitaria.

El estándar define qué datos deben viajar, cómo se identifica a cada actor, cómo se firma una receta, qué eventos pueden ocurrir y cómo cualquier sistema autorizado puede verificar el resultado.

## Separación de responsabilidades

| Actor | Decide o realiza | No debe realizar |
|---|---|---|
| Autoridad sanitaria | Reglas nacionales, catálogos autoritativos, permisos, vigilancia y sanciones | Diagnosticar, prescribir o surtir |
| Registro nacional | Publicar identificadores y atributos vigentes; recibir estados y eventos | Guardar la clave privada del prescriptor |
| PARC | Enrolar, verificar identidad/cédula/e.firma, validar facultades, certificar integridad, asignar folio y transmitir eventos | Elegir medicamentos, modificar dosis o sustituir criterio clínico |
| Prescriptor | Evaluar al paciente, decidir tratamiento, construir y firmar la receta | Autodeclararse facultades o alterar eventos ya certificados |
| Farmacia | Autenticar personal, verificar receta, revisar seguridad, surtir y reportar lote/cantidad | Modificar la orden clínica o reabrir saldos agotados |
| Paciente | Identificarse, presentar o compartir la receta y autorizar accesos adicionales | Transferir derechos de prescripción |
| Pagador | Autorizar y liquidar la cobertura económica | Cambiar el contenido clínico de la receta |

## Qué es un PARC

**PARC** significa **Proveedor Autorizado de Registro y Certificación**. Es la capa de confianza que conecta al prescriptor con el registro nacional. Una autoridad podría autorizar varios PARC para evitar dependencia de un operador único.

El PARC opera en dos momentos:

### 1. Enrolamiento del prescriptor

1. Recibe identidad, CURP, cédula, identificación y evidencia de vida.
2. Consulta o valida las fuentes autorizadas.
3. Comprueba la e.firma sin custodiar su clave privada.
4. Ejecuta controles automáticos y revisión manual.
5. Obtiene del registro el Número Nacional de Prescriptor.
6. Publica atributos vigentes: profesión, alcance, controlados permitidos y fechas de vigencia.

### 2. Certificación de cada receta

1. Recibe del sistema del prescriptor una receta ya construida clínicamente.
2. Comprueba identidad, sesión, vigencia y atributos del prescriptor.
3. Valida esquema, catálogo, fracción y facultades.
4. Comprueba la firma del prescriptor.
5. Agrega folio, sello de tiempo y evidencia de certificación.
6. Registra la receta o su huella en el registro nacional.
7. Devuelve el documento certificable y su código bidimensional.

El PARC **rechaza** una receta inválida, pero no la corrige clínicamente. Ante una interacción, puede exigir que el prescriptor reconozca la advertencia; la decisión clínica sigue siendo del prescriptor.

## Secuencia de emisión

```mermaid
sequenceDiagram
    participant P as Prescriptor
    participant SP as Sistema de prescripción
    participant C as Catálogo nacional
    participant R as PARC
    participant RN as Registro nacional
    participant PX as Paciente

    P->>SP: Identifica paciente y captura tratamiento
    SP->>C: Busca producto clínico y reglas vigentes
    C-->>SP: Código, forma, concentración, fracción y atributos
    SP->>SP: Revisa interacciones y completitud
    P->>SP: Confirma y firma
    SP->>R: Envía receta firmada
    R->>RN: Verifica número y atributos vigentes
    RN-->>R: Estado del prescriptor
    R->>R: Valida firma, esquema, catálogo y facultades
    R->>RN: Registra folio, hash y estado ACTIVE
    R-->>SP: Receta certificada + QR/Data Matrix
    SP-->>PX: Entrega digital o impresa
```

## Secuencia de surtimiento

```mermaid
sequenceDiagram
    participant PX as Paciente
    participant F as Personal de farmacia
    participant SF as Sistema de farmacia
    participant R as PARC/Registro

    PX->>F: Presenta QR, folio o identificador
    F->>SF: Se autentica de forma individual
    SF->>R: Consulta receta y estado
    R-->>SF: Integridad, vigencia, partidas y saldo
    PX->>SF: Autoriza consulta adicional cuando aplique
    SF->>SF: Revisa alertas e interacciones pertinentes
    F->>SF: Captura cantidad, marca, lote y modo
    SF->>R: Reporta evento de surtimiento firmado
    R-->>SF: Nuevo saldo y estado
    SF-->>PX: Entrega medicamento y comprobante
```

## Desabasto público

La portabilidad público-privada no significa que toda farmacia pueda cobrar automáticamente al gobierno. Se separan tres objetos:

1. **Receta clínica:** orden firmada y portable.
2. **Evento de desabasto:** evidencia de que la institución pública no surtió una partida.
3. **Autorización financiera:** compromiso independiente del pagador con reglas, tarifas y auditoría propias.

Así, una receta pública puede verificarse en una farmacia privada, mientras que el pago sólo ocurre cuando existe una autorización financiera válida.

## Despliegue lógico

```mermaid
flowchart LR
    A[Autoridad sanitaria] -->|reglas y catálogos| RN[Registro nacional]
    A -->|autoriza y supervisa| R1[PARC A]
    A -->|autoriza y supervisa| R2[PARC B]
    P1[Sistema público] --> R1
    P2[Consultorio privado] --> R2
    R1 <--> RN
    R2 <--> RN
    RN <--> F1[Farmacia institucional]
    RN <--> F2[Farmacia privada]
    RN <--> PG[Pagadores]
```

## Límites de esta alpha

La implementación actual combina PARC y registro en un solo proceso para facilitar la demostración local. Esa combinación **no es la arquitectura final**. Los módulos deberán separarse antes de una operación real, usar certificados y sellos de tiempo regulados, catálogos firmados y conectores oficiales.
