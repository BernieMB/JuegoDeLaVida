# Controles — El Juego de la Vida

Chuleta completa de atajos de teclado y ratón. También disponible dentro de
la aplicación pulsando **F1** o **H**.

## Simulación

| Atajo | Acción |
|---|---|
| `Espacio` | Pausar / continuar la simulación |
| `→` o `N` | Avanzar una única generación (solo con la simulación en pausa) |
| `+` / `-` | Subir / bajar la velocidad (escala de 12 niveles: 1, 2, 5, 10, 20, 30, 60, 120, 250, 500, 1000, MAX) |
| `C` | Limpiar el tablero (lo vacía y pone el contador de generación a 0) |
| `R` | Resetear al estado que tenía el tablero al empezar esta simulación (o **rotar** el sello activo, si hay uno) |
| `G` | Rellenar el tablero aleatoriamente (según la densidad configurada en el panel) |

El panel lateral ofrece los mismos controles como botones y deslizadores,
incluyendo el selector de **regla** (Life, HighLife, Day & Night, Seeds,
Diamoeba, 2x2, Morley, Anneal, Life without Death, Replicator) y de
**topología** (toroidal / acotada).

## Edición del tablero

| Atajo | Acción |
|---|---|
| Clic izquierdo (mantener y arrastrar) | Pintar celdas vivas (sin huecos aunque el ratón se mueva rápido) |
| Clic derecho (mantener y arrastrar) | Borrar celdas |
| `Mayús` + arrastrar | Seleccionar una región rectangular |
| `Ctrl+C` | Copiar la selección al portapapeles interno |
| `Ctrl+X` | Cortar la selección (copiar y vaciar esa región) |
| `Ctrl+V` | Pegar el portapapeles como un sello que sigue al cursor |
| `Supr` o `Retroceso` | Borrar el contenido de la selección (sin copiarlo) |
| `Escape` | Cancelar el sello activo, o si no hay ninguno, deseleccionar |
| `Ctrl+Z` / `Ctrl+Y` | Deshacer / rehacer (también `Ctrl+Mayús+Z` para rehacer) |

La edición funciona **con la simulación en marcha**: se puede "tocar" un
patrón mientras evoluciona, no hace falta pausar primero.

## Sellos (patrones prefabricados)

Al elegir un patrón de la biblioteca (botón "Elegir patrón…" en el panel, o
tras un `Ctrl+V`), este queda "en la mano", centrado en el cursor:

| Atajo | Acción |
|---|---|
| Mover el ratón | Reposicionar el sello (se centra en el cursor) |
| Clic izquierdo | Colocar una copia (el sello permanece activo para colocar más copias seguidas) |
| `R` | Rotar 90° en sentido horario |
| `F` | Voltear horizontalmente |
| Clic derecho o `Escape` | Cancelar el sello |

## Vista (cámara)

| Atajo | Acción |
|---|---|
| Rueda del ratón | Zoom centrado en la posición del cursor (no en la esquina) |
| Botón central + arrastrar | Desplazar la vista (paneo) |
| `F` | Ajustar el zoom para ver la rejilla entera (cuando no hay un sello activo) |
| `1` | Zoom real: 1 celda = 1 píxel |

## Archivos

| Atajo | Acción |
|---|---|
| `Ctrl+S` | Guardar el tablero completo (recortado a las celdas vivas) en `patterns/` |
| `Ctrl+Mayús+S` | Guardar **solo la selección activa** |
| Botón "Abrir biblioteca de archivos…" | Navegar los `.rle`/`.cells` guardados, cargarlos como sello o reemplazando el tablero |

Los ficheros usan el formato **RLE estándar**, compatible con Golly y
LifeWiki: se pueden abrir patrones descargados de esos sitios, y los que
guarde esta aplicación se pueden abrir allí.

## Estadísticas y otros

| Atajo | Acción |
|---|---|
| `P` | Exportar la vista actual como imagen PNG |
| Casilla "Auto-pausar al estabilizar" | Pausa automáticamente en cuanto el tablero se vuelve una forma estable o un oscilador (se indica también el periodo detectado) |
| `F1` o `H` | Mostrar/ocultar esta ayuda dentro de la aplicación |

## Notas

- Todos los diálogos emergentes (biblioteca de patrones, navegador de
  archivos, ayuda) se cierran con `Escape` o haciendo clic fuera de ellos.
- El panel lateral tiene más contenido del que cabe en una ventana pequeña:
  se puede desplazar con la rueda del ratón sobre él.
- La barra inferior muestra generación, población (y su porcentaje sobre el
  total de celdas), generaciones/segundo **reales** medidas, y los FPS de
  renderizado.
