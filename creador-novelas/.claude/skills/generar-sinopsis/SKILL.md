---
name: generar-sinopsis
description: Fase 2 (RF-02.1). A partir de premisa.md produce 04_estado/tres_actos.md con gancho inicial, punto medio y clímax/final.
allowed-tools: Read, Write, Bash(.venv/Scripts/python.exe -m app:*)
disable-model-invocation: true
---

Premisa:
!`cat 01_concepto/premisa.md 2>/dev/null || echo "(no existe 01_concepto/premisa.md: corré /generar-premisa)"`

Guía de estilo (si existe):
!`cat 04_estado/style_guide.md 2>/dev/null || echo "(sin style_guide.md)"`

# Fase 2: sinopsis en tres actos

Condición de entrada: `01_concepto/premisa.md` existe.

Pasos:
1. Escribí, en el idioma configurado, tres secciones nombradas explícitamente con encabezados: **Gancho inicial**, **Punto medio (giro)** y **Clímax / final**. Cada una con al menos un párrafo.
2. Regla de coherencia (RF-02.1): ningún personaje que aparezca en el clímax/final puede aparecer por primera vez ahí; tiene que estar mencionado en el gancho o en el punto medio. Revisalo antes de guardar.
3. Guardá con Write en `.tanda/borradores/tres_actos.md` y persistí con
   `.venv/Scripts/python.exe -m app guardar tres_actos --desde .tanda/borradores/tres_actos.md`
4. Si `guardar` falla, corregí y repetí.

Retorno: una línea con la ruta escrita. Nada más.
