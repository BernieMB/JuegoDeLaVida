"""Configuracion compartida de pytest.

Fuerza el driver de video 'dummy' de SDL para que pygame pueda crear
Surfaces y usar pygame.transform/surfarray en un entorno sin pantalla (CI,
sandboxes), sin necesidad de un display real.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame
import pytest


@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    """Inicializa pygame UNA sola vez para toda la sesion de tests y lo
    cierra al final. Igual que en la aplicacion real (pygame.init()/quit()
    ocurren una unica vez por proceso), esto evita invalidar los objetos
    Font cacheados en el Theme singleton (vida.ui.theme) si distintos
    modulos de test hicieran su propio init/quit intermedio."""
    pygame.init()
    yield
    pygame.quit()

