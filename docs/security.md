# Seguridad y privacidad

## Activos críticos

- identidad y atributos del prescriptor;
- certificados y evidencia de enrolamiento;
- recetas y surtimientos;
- identificadores de pacientes;
- credenciales de farmacias y empleados;
- catálogos regulatorios;
- claves de firma, sellado y cifrado;
- bitácoras de auditoría.

## Amenazas principales

1. suplantación de prescriptor;
2. uso de cédula válida por una persona distinta;
3. emisión o duplicación fraudulenta de controlados;
4. modificación de una receta después de firmarla;
5. consulta masiva de historiales usando CURP;
6. colusión entre farmacia y empleado;
7. reutilización de folios o códigos impresos;
8. caída de conectividad en comunidades rurales;
9. compromiso de un PACR;
10. catálogos obsoletos o adulterados;
11. filtración de diagnósticos y tratamientos;
12. reclamaciones financieras falsas.

## Controles requeridos para beta

- WebAuthn/passkeys y MFA para prescriptores y farmacias;
- firma de cada receta mediante JWS/CMS y certificado válido;
- validación OCSP/CRL y sello de tiempo;
- HSM o KMS para claves del operador;
- cifrado de campos sensibles y respaldos;
- separación de funciones entre alta, aprobación y suspensión;
- rate limiting y detección de anomalías;
- consentimiento o prueba de presencia del paciente;
- bitácora append-only con encadenamiento hash;
- acceso de farmacia limitado a propósito y ventana temporal;
- revocación inmediata de sesiones y atributos;
- pruebas de penetración, SAST, SBOM y gestión de vulnerabilidades;
- plan de continuidad y operación offline con reconciliación;
- minimización y plazos de conservación definidos jurídicamente.

## Decisiones de la alpha

La alpha usa PBKDF2 para contraseñas, hashes de tokens y HMAC para demostrar integridad. Estos mecanismos permiten probar el flujo, pero no constituyen firma electrónica avanzada ni infraestructura nacional segura.

La consulta de últimas recetas no se habilita sólo con CURP. Exige una sesión individual del empleado y un código del paciente, y siempre genera auditoría.
