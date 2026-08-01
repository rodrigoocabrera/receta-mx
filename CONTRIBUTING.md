# Contribuir a Receta MX

Receta MX está en etapa alpha. Las contribuciones deben distinguir claramente entre:

- requisitos legales vigentes;
- decisiones propuestas por el estándar;
- comportamiento demostrativo de la implementación de referencia.

## Flujo

1. Abra un issue con el problema, caso de uso o cambio normativo.
2. Cree una rama corta y enfocada.
3. Incluya pruebas para cambios funcionales.
4. Ejecute `python -m unittest discover -s tests -v`.
5. Evite datos personales reales, cédulas reales, CURP reales y secretos.

## Seguridad y privacidad

No publique vulnerabilidades explotables ni datos personales en issues públicos. Para la alpha, documente el hallazgo sin incluir material sensible y solicite un canal privado a los mantenedores.

## Alcance clínico

Los catálogos, interacciones y alertas incluidos son sintéticos o incompletos. Ninguna contribución debe presentarlos como soporte clínico certificado sin evidencia, validación y gobernanza explícitas.
