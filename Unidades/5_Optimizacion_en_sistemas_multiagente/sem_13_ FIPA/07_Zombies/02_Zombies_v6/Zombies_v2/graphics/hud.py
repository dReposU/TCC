"""
HUD en tiempo real para la simulación de Invasión Zombie en la Universidad:
- Muestra conteos de N personas, M zombies, Salvados, Infectados y En peligro.
- Consola de mensajes FIPA-ACL en vivo y distribución por piso.
"""
import os
from typing import Optional
import pygame

from agents.acl import AgentPlatform
from agents.persona_agent import PersonaAgent
from agents.zombie_agent import ZombieAgent
from graphics.engine3d import Camera3D


class SimulationHUD:
    def __init__(self, assets_dir: str) -> None:
        self.font_title: Optional[pygame.font.Font] = None
        self.font_med: Optional[pygame.font.Font] = None
        self.font_small: Optional[pygame.font.Font] = None
        self.icon: Optional[pygame.Surface] = None
        icon_path = os.path.join(assets_dir, "textures", "biohazard_icon.png")
        if os.path.exists(icon_path):
            try:
                self.icon = pygame.image.load(icon_path)
            except Exception:
                self.icon = None

    def _init_fonts(self) -> None:
        if self.font_title is None:
            self.font_title = pygame.font.SysFont("consolas", 16, bold=True)
            self.font_med = pygame.font.SysFont("consolas", 13, bold=True)
            self.font_small = pygame.font.SysFont("consolas", 12)

    def render(
        self,
        surface: pygame.Surface,
        platform: AgentPlatform,
        camera: Camera3D,
        num_n: int,
        num_m: int,
        sim_speed: float,
        paused: bool,
        muted: bool,
    ) -> None:
        self._init_fonts()
        assert self.font_title and self.font_med and self.font_small
        w, h = surface.get_size()

        personas_activas = [a for a in platform.agents.values() if isinstance(a, PersonaAgent) and a.alive]
        zombies_activos = [a for a in platform.agents.values() if isinstance(a, ZombieAgent) and a.alive]

        top_box = pygame.Surface((w - 24, 58), pygame.SRCALPHA)
        top_box.fill((12, 16, 26, 215))
        pygame.draw.rect(top_box, (70, 105, 140, 220), top_box.get_rect(), 1, border_radius=8)
        surface.blit(top_box, (12, 10))

        title = "INVASIÓN ZOMBIE EN LA UNIVERSIDAD · 8 PISOS | 4 AULAS/PISO | 3 SALIDAS/PISO"
        surface.blit(self.font_title.render(title, True, (245, 205, 85)), (24, 16))

        vista_str = "Todos los pisos (0)" if camera.focused_floor is None else f"Piso {camera.focused_floor + 1}"
        sub = (
            f"Config: N={num_n} Personas, M={num_m} Zombies  |  "
            f"En edificio: {len(personas_activas)} sanos, {len(zombies_activos)} zombies "
            f"({sum(1 for z in zombies_activos if z.emboscada is not None)} emboscando)  |  "
            f"Vista: {vista_str}  |  Vel: {sim_speed:.1f}x {'[PAUSA]' if paused else ''}"
        )
        surface.blit(self.font_small.render(sub, True, (205, 220, 235)), (24, 41))

        # Indicador del modo horda (tecla H)
        if platform.modo_horda:
            horda_str = (
                f"HORDA: ON  |  avisos presa_detectada: {platform.total_avisos_horda}  |  "
                f"infectados por emboscada: {platform.infectados_por_horda}"
            )
            horda_col = (255, 175, 70)
        else:
            horda_str = "HORDA: OFF (comportamiento original)  [H] activar"
            horda_col = (165, 175, 190)
        h_surf = self.font_small.render(horda_str, True, horda_col)
        self._horda_surf = h_surf  # se dibuja en la barra inferior

        salv_txt = self.font_med.render(f"SALVADOS: {platform.total_salvados}", True, (85, 250, 145))
        inf_txt = self.font_med.render(f"INFECTADOS: {platform.total_infectados}", True, (255, 85, 85))
        surface.blit(salv_txt, (w - salv_txt.get_width() - inf_txt.get_width() - 46, 20))
        surface.blit(inf_txt, (w - inf_txt.get_width() - 26, 20))


        panel_w = 380
        panel_h = h - 128
        px = w - panel_w - 12
        py = 76
        side = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        side.fill((12, 16, 26, 205))
        pygame.draw.rect(side, (70, 105, 140, 210), side.get_rect(), 1, border_radius=8)
        surface.blit(side, (px, py))

        hy = py + 10
        if self.icon is not None:
            surface.blit(pygame.transform.smoothscale(self.icon, (32, 32)), (px + 12, hy))
            tx = px + 52
        else:
            tx = px + 14

        surface.blit(self.font_med.render("ESTADO POR PISO & MENSAJES ACL", True, (130, 225, 255)), (tx, hy + 2))
        surface.blit(self.font_small.render("Teclas [1-8] enfocar piso | [0] edificio completo", True, (165, 185, 205)), (tx, hy + 19))

        row_y = hy + 42
        for f in range(7, -1, -1):
            p_cnt = sum(1 for p in personas_activas if p.floor == f)
            z_cnt = sum(1 for z in zombies_activos if z.floor == f)
            is_sel = camera.focused_floor == f
            row_col = (245, 210, 90) if is_sel else (195, 210, 225)
            line_str = f"Piso {f+1}:  Sanos={p_cnt:02d}   Zombies={z_cnt:02d}   (4 Aulas, 3 Salidas)"
            surface.blit(self.font_small.render(line_str, True, row_col), (px + 14, row_y))
            row_y += 17

        pygame.draw.line(surface, (65, 95, 125), (px + 12, row_y + 4), (px + panel_w - 12, row_y + 4), 1)
        log_y = row_y + 12
        avail_h = (py + panel_h) - log_y - 8
        max_logs = max(4, avail_h // 17)
        for idx, (stamp, text, col) in enumerate(platform.console_logs[-max_logs:]):
            msg_line = f"[{stamp}] {text}"
            if len(msg_line) > 50:
                msg_line = msg_line[:47] + "..."
            surface.blit(self.font_small.render(msg_line, True, col), (px + 12, log_y + idx * 17))

        bot = pygame.Surface((w - 24, 34), pygame.SRCALPHA)
        bot.fill((12, 16, 26, 215))
        pygame.draw.rect(bot, (70, 105, 140, 210), bot.get_rect(), 1, border_radius=6)
        surface.blit(bot, (12, h - 44))

        snd_tag = "Audio:OFF(M)" if muted else "Audio:ON(M)"
        ctrl = (
            f"[Arrastrar/Flechas] Orbitar 3D  [Rueda] Zoom  [0..8] Pisos  [Espacio] Pausa  "
            f"[+/-] Vel  [Q/W] N  [A/S] M  [H] Horda  [R] Reiniciar  [{snd_tag}]"
        )
        surface.blit(self.font_small.render(ctrl, True, (195, 215, 235)), (20, h - 34))
        hb = pygame.Surface((self._horda_surf.get_width() + 20, 24), pygame.SRCALPHA)
        hb.fill((12, 16, 26, 215))
        pygame.draw.rect(hb, (70, 105, 140, 210), hb.get_rect(), 1, border_radius=6)
        surface.blit(hb, (12, h - 72))
        surface.blit(self._horda_surf, (22, h - 68))
