# -*- coding: utf-8 -*-
"""
Laboratorio: cuando subes el diseño (STL) desde el detalle del trabajo,
ahora queda más claro si sí se subió o no:

  - Si se sube bien, aparece un mensaje de confirmación (el mismo tipo de
    aviso verde que ya usan otras acciones) además de refrescar la vista,
    que ya mostraba el archivo subido esperando aprobación del estudiante.

  - Si el servidor responde con error (por ejemplo un 502 porque Render
    está a medio redesplegar), en vez de dejarte solo con la alerta y sin
    saber si alcanzó a guardarse antes de que tronara, la app intenta
    refrescar el detalle del trabajo automáticamente para mostrarte el
    estado real: si el archivo sí quedó guardado vas a ver la caja de
    "diseño subido, esperando aprobación"; si no, vas a seguir viendo el
    botón para subirlo. El mensaje de la alerta también lo explica.

Uso: colócalo en la carpeta del repo (junto a backend/ y frontend/) y corre:
    python3 fix_laboratorio_diseno_confirmacion_subida.py
"""
import sys

RUTA = 'frontend/index.html'

VIEJO = '''    await api(`/api/laboratorio/${trabajoId}/subir-diseno`, { method: 'POST', body: JSON.stringify(body) });
    await abrirDetalleLaboratorio(trabajoId);
  } catch (e) {
    alert(e.message);
  }
}'''

NUEVO = '''    await api(`/api/laboratorio/${trabajoId}/subir-diseno`, { method: 'POST', body: JSON.stringify(body) });
    mostrarExito('Diseño subido correctamente');
    await abrirDetalleLaboratorio(trabajoId);
  } catch (e) {
    alert(e.message + '\\n\\nRevisando si el archivo alcanzó a guardarse antes del error...');
    try {
      await abrirDetalleLaboratorio(trabajoId);
    } catch (e2) {
      // El servidor sigue sin responder -- no hay forma de confirmar desde aquí todavía.
      // Cierra y vuelve a abrir el trabajo en un momento para revisar si se subió o no.
    }
  }
}'''


def main():
    try:
        with open(RUTA, 'r', encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        print(f"[{RUTA}] NO ENCONTRADO -- asegúrate de correr este script desde la raíz del repo (junto a backend/ y frontend/).")
        sys.exit(1)

    if VIEJO in contenido:
        contenido = contenido.replace(VIEJO, NUEVO, 1)
    elif NUEVO in contenido:
        print(f"[{RUTA}] Ya estaba aplicado, no se hizo nada.")
        sys.exit(0)
    else:
        print(f"[{RUTA}] No se encontró el bloque esperado. El archivo pudo haber cambiado desde la última vez.")
        print("Avísale a Claude sin correr git add/commit todavía.")
        sys.exit(1)

    with open(RUTA, 'w', encoding='utf-8') as f:
        f.write(contenido)

    print(f"[{RUTA}] Corregido.")
    print()
    print("Todo listo. Ahora corre:")
    print("   git add frontend/index.html")
    print('   git commit -m "Laboratorio: confirmar si el diseno se subio o no (toast de exito + reintento de refresco si truena el servidor)"')
    print("   git push")


if __name__ == "__main__":
    main()
