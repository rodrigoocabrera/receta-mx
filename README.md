# Receta MX

**Receta MX** es una propuesta abierta de estándar nacional para representar, firmar, certificar, verificar y surtir recetas electrónicas interoperables en México. Define contratos y responsabilidades; no obliga a utilizar una sola aplicación ni un operador privado único.

Esta primera versión `0.1.0-alpha` implementa un flujo completo y demostrable:

1. alta y validación de prescriptores;
2. número nacional de prescriptor separado de la cédula profesional;
3. atributos de autorización por profesión y medicamentos controlados;
4. identificación de pacientes por CURP o identificadores alternativos de contingencia;
5. emisión de receta con folio verificable y payload para código bidimensional;
6. verificación pública de integridad;
7. consulta auditada de hasta diez recetas recientes por personal de farmacia;
8. revisión básica de interacciones y advertencias;
9. surtimiento total, parcial, resurtimiento y transferencia por desabasto público;
10. captura de marca, lote, cantidad, empleado y farmacia;
11. exportación de referencia basada en recursos FHIR R4.

> [!IMPORTANT]
> Este repositorio **no es una Norma Oficial Mexicana**, no sustituye autorizaciones de COFEPRIS, no valida cédulas, CURP o e.firma contra sistemas gubernamentales reales y no debe utilizarse para atención clínica o dispensación real en su estado alpha.

## En una frase

El **prescriptor toma la decisión clínica y firma**; el **PARC verifica quién firma, sus facultades y la integridad**, sin prescribir; la **farmacia verifica, dispensa y reporta**, sin modificar la orden clínica; y el **registro nacional conserva estados y atributos interoperables**.

Consulte [`docs/architecture.md`](docs/architecture.md) para las secuencias completas.

## Arquitectura propuesta

Receta MX separa tres capas:

- **Estándar abierto:** modelos, estados, identificadores, reglas de interoperabilidad y contratos API.
- **Registro nacional:** prescriptores, farmacias, personal autorizado, recetas, surtimientos y trazabilidad.
- **PARC (Proveedor Autorizado de Registro y Certificación):** operadores interoperables que verifican identidad, e.firma, cédula, prueba de vida y requisitos regulatorios; asignan folios y transmiten eventos al registro nacional. La autoridad conserva las reglas, catálogos, sanciones y autorizaciones.

El modelo evita depender de un operador privado único. Una implementación nacional debería admitir múltiples PARC certificados y portabilidad completa.

## Ejecutar localmente

Requiere Python 3.11 o superior. El servidor usa únicamente la biblioteca estándar. Para generar QR SVG reales puede instalarse el extra opcional `qrcode`.

```bash
export RECETAMX_OPERATOR_KEY='cambie-esta-clave'
export RECETAMX_SIGNING_SECRET='cambie-este-secreto-largo'
export RECETAMX_PUBLIC_BASE_URL='http://localhost:8080'
python3 -m recetamx.server
```

Abra `http://localhost:8080`.

Para cargar datos sintéticos de demostración:

```bash
curl -X POST http://localhost:8080/api/operator/bootstrap \
  -H 'X-Operator-Key: cambie-esta-clave' \
  -H 'Content-Type: application/json' \
  -d '{}'
```

Credenciales demo creadas por `bootstrap`:

- Prescriptor: `MEDD900101HDFMXX09` / `demo-medico`
- Farmacia: `FARD900101MDFMXX02` / `demo-farmacia`
- Paciente: `TEMP_RURAL` + `RURAL-DEMO-001` / código `123456`

Todos los identificadores son sintéticos.

## Pruebas

```bash
python3 -m unittest discover -s tests -v
```

## Seguridad de la alpha

- contraseñas con PBKDF2-HMAC-SHA256;
- tokens de sesión aleatorios almacenados como hash;
- folio y token de verificación independientes;
- firma HMAC de referencia sobre JSON canónico;
- auditoría de acceso al historial y de cada surtimiento;
- código del paciente obligatorio para consulta de antecedentes por farmacia;
- límite estricto de diez recetas recientes;
- catálogos demo marcados como no autoritativos.

La firma HMAC de esta alpha debe sustituirse por un esquema regulado de firma avanzada y sellado de tiempo. La clave privada de e.firma del prescriptor nunca debe entregarse ni custodiarse por el PARC.

## Identificación de pacientes y población rural

La CURP es el identificador preferente, pero el estándar admite identificadores temporales controlados:

- `TEMP_RURAL` para contingencia o falta de documentos;
- `NEWBORN` para recién nacidos sin CURP;
- `FOREIGN` para personas extranjeras;
- `OTHER` para identificadores institucionales autorizados.

Cada identidad temporal debe reconciliarse posteriormente sin perder trazabilidad. El paciente recibe un código de acceso de seis dígitos para autorizar la consulta en farmacia; una implementación real debe admitir además OTP, credencial física, biometría local opcional y contingencia sin conectividad.

## Sector público y privado

Una receta puede declarar:

- `PUBLIC_ONLY`;
- `PRIVATE_ONLY`;
- `ANY_AUTHORIZED_PHARMACY`;
- `PUBLIC_FIRST_PRIVATE_FALLBACK`.

El evento `PUBLIC_SHORTAGE_TRANSFER` permite documentar que una receta pública fue surtida en una farmacia privada. El pago o reclamación al sector público se modela como una fase posterior y no está implementado como obligación financiera real.

## Fundamento normativo de diseño

La propuesta toma como referencia, sin afirmar cumplimiento certificado:

- Ley General de Salud, artículos 28 Bis, 226 y 240 a 252;
- Reglamento de Insumos para la Salud;
- NOM-004-SSA3-2012, del expediente clínico;
- NOM-024-SSA3-2012, sistemas de información de registro electrónico para la salud e intercambio de información;
- Ley de Firma Electrónica Avanzada y mecanismos de validación de e.firma del SAT;
- estándares HL7 FHIR R4 para intercambio de información clínica.

Fuentes oficiales:

- https://www.diputados.gob.mx/LeyesBiblio/pdf/LGS.pdf
- https://www.diputados.gob.mx/LeyesBiblio/regley/Reg_LGS_IS.pdf
- https://www.dof.gob.mx/normasOficiales/4956/SALUD1/SALUD1.html
- https://www.sat.gob.mx/portal/public/tramites/firma-electronica-avanzada-efirma
- https://hl7.org/fhir/R4/

## Documentación

- [`docs/architecture.md`](docs/architecture.md): separación detallada entre autoridad, PARC, prescriptor, farmacia, paciente y pagador.
- [`docs/medication-catalog.md`](docs/medication-catalog.md): modelo, API y fuentes del catálogo de medicamentos.
- [`docs/glossary.md`](docs/glossary.md): definiciones comunes.
- [`docs/standard.md`](docs/standard.md): propuesta normativa y reglas funcionales.
- [`docs/security.md`](docs/security.md): modelo de amenazas y controles.
- [`docs/roadmap.md`](docs/roadmap.md): ruta hacia beta y operación nacional.
- [`schemas/prescription.schema.json`](schemas/prescription.schema.json): esquema JSON de receta.
- [`openapi.yaml`](openapi.yaml): contrato inicial de API.

## Licencia

MIT. Consulte [`LICENSE`](LICENSE).
