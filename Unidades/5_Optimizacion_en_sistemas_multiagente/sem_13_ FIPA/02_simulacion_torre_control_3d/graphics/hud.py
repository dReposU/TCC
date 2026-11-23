"""
Interfaz HUD en tiempo real para visualizar el estado de TorreAgent,
la consola de mensajes FIPA-ACL, radar 2D auxiliar y controles interactivos.
"""
import os
from typing import Optional
import pygame

from agents.acl import AgentPlatform
from agents.avion_agent import AvionAgent
from agents.torre_agent import TorreAgent
from graphics.engine3d import Camera3D


class SimulationHUD:
    def __init__(self, assets_dir: str) -> None:
        self.font_title: Optional[pygame.font.Font] = None
        self.font_med: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None
        self.radar_icon: Optional[pygame.Surface] = None
        icon_path = os.path.join(assets_dir, "textures", "radar_icon.png")
        if os.path.exists(icon_path):
            try:
                self.radar_icon = pygame.image.load(icon_path)
            except Exception:
                self.radar_icon = None

    def _init_fonts(self) -> None:
        if self.font_title is None:
            self.font_title = pygame.font.SysFont("consolas", 17, bold=True)
            self.font_med = pygame.font.SysFont("consolas", 14, bold=True)
            self.font_small = pygame.font.SysFont("consolas", 12)

    def render(
        self,
        surface: pygame.Surface,
        platform: AgentPlatform,
        camera: Camera3D,
        sim_speed: float,
        paused: bool,
        muted: bool,
    ) -> None:
        self._init_fonts()
        assert self.font_title and self.font_med and self.font_small

        w, h = surface.get_size()

        # 1. Barra superior de telemetría
        top_panel = pygame.Surface((w - 24, 52), pygame.SRCALPHA)
        top_panel.fill((10, 18, 28, 205))
        pygame.draw.rect(top_panel, (55, 95, 130, 220), top_panel.get_rect(), 1, border_radius=8)
        surface.blit(top_panel, (12, 10))

        title_surf = self.font_title.render(
            "SIMULACIÓN MULTI-AGENTE 3D · TORRE DE CONTROL (JADE -> PYGAME)",
            True,
            (130, 225, 255),
        )
        surface.blit(title_surf, (24, 17))

        active_planes = [a for a in platform.agents.values() if isinstance(a, AvionAgent) and a.alive]
        torre = platform.agents.get("Torre")
        occupant = torre.avion_en_pista if isinstance(torre, TorreAgent) else None

        pista_txt = f"PISTA OCUPADA ({occupant})" if TorreAgent.pista_ocupada else "PISTA LIBRE"
        pista_col = (255, 95, 95) if TorreAgent.pista_ocupada else (90, 250, 145)

        stats_line = (
            f"Aviones en aire: {len(active_planes)}  |  "
            f"Aterrizados: {platform.total_landed}  |  "
            f"Velocidad: {sim_speed:.1f}x {'[PAUSA]' if paused else ''}  |  "
            f"Cámara: {camera.MODES[camera.mode_index]}"
        )
        surface.blit(self.font_small.render(stats_line, True, (200, 215, 230)), (24, 40))

        badge = self.font_med.render(pista_txt, True, pista_col)
        surface.blit(badge, (w - badge.get_width() - 28, 26))

        # 2. Panel lateral derecho: Consola de Mensajes FIPA-ACL + Radar 2D
        panel_w = 390
        panel_h = h - 125
        px = w - panel_w - 12
        py = 72

        right_panel = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        right_panel.fill((10, 16, 26, 195))
        pygame.draw.rect(right_panel, (55, 90, 120, 200), right_panel.get_rect(), 1, border_radius=8)
        surface.blit(right_panel, (px, py))

        header_y = py + 10
        if self.radar_icon is not None:
            icon_scaled = pygame.transform.smoothscale(self.radar_icon, (34, 34))
            surface.blit(icon_scaled, (px + 12, header_y))
            hdr_x = px + 54
        else:
            hdr_x = px + 14

        surface.blit(self.font_med.render("CONSOLA DE MENSAJES ACL", True, (130, 225, 255)), (hdr_x, header_y + 2))
        legend = "INFORM(cyan) PROPOSE(amarillo) ACCEPT(verde) REJECT(rojo)"
        surface.blit(self.font_small.render(legend, True, (150, 175, 195)), (hdr_x, header_y + 20))

        # Dibujar últimas líneas del log ACL
        log_start_y = header_y + 46
        line_h = 18
        max_lines = max(5, (panel_h - 60) // line_h)
        visible_logs = platform.console_logs[-max_lines:]
        for idx, (stamp, text, col) in enumerate(visible_logs):
            full_str = f"[{stamp}] {text}"
            if len(full_str) > 51:
                full_str = full_str[:48] + "..."
            surf_line = self.font_small.render(full_str, True, col)
            surface.blit(surf_line, (px + 12, log_start_y + idx * line_h))

        # 3. Barra inferior de controles
        bot_panel = pygame.Surface((w - 24, 34), pygame.SRCALPHA)
        bot_panel.fill((10, 18, 28, 205))
        pygame.draw.rect(bot_panel, (55, 95, 130, 200), bot_panel.get_rect(), 1, border_radius=6)
        surface.blit(bot_panel, (12, h - 44))

        audio_lbl = "Audio: OFF (M)" if muted else "Audio: ON (M)"
        controls_txt = (
            f"[Arrastrar Ratón / Flechas] Orbitar 3D   [Rueda] Zoom   [1-4] Cámaras   "
            f"[Espacio] Pausa   [+/-] Velocidad   [N] +Avión   [R] Reiniciar   [{audio_lbl}]"
        )
        surface.blit(self.font_small.render(controls_txt, True, (195, 215, 235)), (22, h - 34))
