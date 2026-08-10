from __future__ import annotations

import pygame
import pytest

from vida.ui.widgets import Button, ScrollableSidebar


def _mouse_down(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=pos, button=button)


def _mouse_up(pos, button=1):
    return pygame.event.Event(pygame.MOUSEBUTTONUP, pos=pos, button=button)


def _wheel(y):
    return pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=y, flipped=False)


class TestScrollableSidebarScrolling:
    def test_no_scroll_needed_when_content_fits(self):
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 800))
        sidebar.content_height = 400
        assert sidebar._max_scroll() == 0

    def test_wheel_scrolls_down_and_clamps_at_bottom(self):
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400))
        sidebar.content_height = 1000
        for _ in range(100):
            sidebar.handle_event(_wheel(-1))
        assert sidebar.scroll == sidebar._max_scroll()

    def test_wheel_scrolls_up_and_clamps_at_top(self):
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400))
        sidebar.content_height = 1000
        sidebar.scroll = 300
        for _ in range(100):
            sidebar.handle_event(_wheel(1))
        assert sidebar.scroll == 0

    def test_wheel_outside_sidebar_is_ignored(self, monkeypatch):
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400))
        sidebar.content_height = 1000
        monkeypatch.setattr(pygame.mouse, "get_pos", lambda: (500, 500))
        consumed = sidebar.handle_event(_wheel(-1))
        assert consumed is False
        assert sidebar.scroll == 0


class TestScrollableSidebarEventShifting:
    def test_click_reaches_child_at_scroll_zero(self):
        calls = []
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400))
        sidebar.content_height = 1000
        sidebar.add(Button(pygame.Rect(10, 50, 100, 30), "Boton", on_click=lambda: calls.append(1)))
        sidebar.handle_event(_mouse_down((50, 60)))
        sidebar.handle_event(_mouse_up((50, 60)))
        assert calls == [1]

    def test_click_reaches_child_below_fold_when_scrolled(self):
        calls = []
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400))
        sidebar.content_height = 1000
        # Boton colocado en coordenadas de CONTENIDO y=500 (fuera de la
        # vista inicial, que solo abarca 0..400).
        sidebar.add(Button(pygame.Rect(10, 500, 100, 30), "Abajo", on_click=lambda: calls.append(1)))
        sidebar.scroll = 400  # ahora la vista abarca el contenido 400..800
        # La pantalla y=100 corresponde a contenido y=500 (100+scroll=500).
        sidebar.handle_event(_mouse_down((50, 100)))
        sidebar.handle_event(_mouse_up((50, 100)))
        assert calls == [1]

    def test_click_does_not_reach_child_when_not_scrolled_to_it(self):
        calls = []
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400))
        sidebar.content_height = 1000
        sidebar.add(Button(pygame.Rect(10, 500, 100, 30), "Abajo", on_click=lambda: calls.append(1)))
        sidebar.scroll = 0
        sidebar.handle_event(_mouse_down((50, 100)))
        sidebar.handle_event(_mouse_up((50, 100)))
        assert calls == []

    def test_sidebar_offset_from_origin_is_respected(self):
        calls = []
        sidebar = ScrollableSidebar(pygame.Rect(20, 0, 300, 400))
        sidebar.content_height = 400
        sidebar.add(Button(pygame.Rect(10, 50, 100, 30), "Boton", on_click=lambda: calls.append(1)))
        # La pantalla x=30 corresponde a contenido x=10 (30 - rect.x=20).
        sidebar.handle_event(_mouse_down((30, 60)))
        sidebar.handle_event(_mouse_up((30, 60)))
        assert calls == [1]


class TestScrollableSidebarDraw:
    def test_draw_does_not_crash_with_tall_content(self):
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 400), background=(20, 20, 20))
        sidebar.content_height = 2000
        sidebar.add(Button(pygame.Rect(10, 1500, 100, 30), "Muy abajo"))
        sidebar.scroll = 1000
        sidebar.draw(pygame.Surface((300, 400)))

    def test_draw_does_not_crash_when_content_shorter_than_rect(self):
        sidebar = ScrollableSidebar(pygame.Rect(0, 0, 300, 800))
        sidebar.content_height = 200
        sidebar.draw(pygame.Surface((300, 800)))
