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
from agents.medico_agent import MedicoAgent
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
        medicos_activos = [a for a in platform.agents.values() if isinstance(a, MedicoAgent) and a.alive]
        dosis_totales = sum(m.dosis for m in medicos_activos)

        fuertes_activos = sum(1 for p in personas_activas if getattr(p, "tipo_humano", "") == "FUERTE")
        debiles_activos = sum(1 for p in personas_activas if getattr(p, "tipo_humano", "") == "DEBIL")
        z_grandes_activos = sum(1 for z in zombies_activos if getattr(z, "tipo_zombie", "") == "GRANDE")
        z_normales_activos = sum(1 for z in zombies_activos if getattr(z, "tipo_zombie", "") == "NORMAL")

        top_box = pygame.Surface((w - 24, 58), pygame.SRCALPHA)
        top_box.fill((12, 16, 26, 215))
        pygame.draw.rect(top_box, (70, 105, 140, 220), top_box.get_rect(), 1, border_radius=8)
        surface.blit(top_box, (12, 10))

        title = "INVASIÓN ZOMBIE EN LA UNIVERSIDAD · 8 PISOS | MÉDICOS CON ANTÍDOTO EN PISOS PARES"
        surface.blit(self.font_title.render(title, True, (245, 205, 85)), (24, 16))

        vista_str = "Todos los pisos (0)" if camera.focused_floor is None else f"Piso {camera.focused_floor + 1}"
        sub = (
            f"Config: N={num_n} ({platform.initial_personas_fuertes}F/{platform.initial_personas_debiles}D), M={num_m}  |  "
            f"Sanos: {len(personas_activas)} ({fuertes_activos}F/{debiles_activos}D)  |  "
            f"Zombies: {len(zombies_activos)} ({z_grandes_activos}G/{z_normales_activos}N)  |  "
            f"Médicos: {len(medicos_activos)} ({dosis_totales} Dosis)  |  "
            f"Vista: {vista_str}  |  Vel: {sim_speed:.1f}x {'[PAUSA]' if paused else ''}"
        )
        surface.blit(self.font_small.render(sub, True, (205, 220, 235)), (24, 41))

        cur_txt = self.font_med.render(
            f"CURADOS: {platform.total_curados} (G:{platform.total_curados_grandes}|N:{platform.total_curados_normales})",
            True,
            (70, 245, 220),
        )
        salv_txt = self.font_med.render(
            f"SALVADOS: {platform.total_salvados} (F:{platform.total_salvados_fuertes}|D:{platform.total_salvados_debiles})",
            True,
            (85, 250, 145),
        )
        inf_txt = self.font_med.render(
            f"TRANSFORMADOS: {platform.total_infectados} (G:{platform.total_transformados_grandes}|N:{platform.total_transformados_normales})",
            True,
            (255, 85, 85),
        )
        rx = w - 26
        surface.blit(inf_txt, (rx - inf_txt.get_width(), 20))
        rx -= inf_txt.get_width() + 20
        surface.blit(cur_txt, (rx - cur_txt.get_width(), 20))
        rx -= cur_txt.get_width() + 20
        surface.blit(salv_txt, (rx - salv_txt.get_width(), 20))

        if len(personas_activas) == 0 and platform.initial_personas > 0:
            done_banner = pygame.Surface((660, 58), pygame.SRCALPHA)
            done_banner.fill((16, 24, 36, 230))
            pygame.draw.rect(done_banner, (245, 205, 85, 240), done_banner.get_rect(), 2, border_radius=8)
            bx = (w - 390 - 660) // 2
            surface.blit(done_banner, (max(20, bx), 78))
            res1 = f"SIMULACIÓN FINALIZADA EN {platform.sim_time:.1f}s"
            res2 = (
                f"Salvados: {platform.total_salvados}   |   "
                f"Curados: {platform.total_curados} (G:{platform.total_curados_grandes}, N:{platform.total_curados_normales})   |   "
                f"Infectados: {platform.total_infectados}"
            )
            surface.blit(self.font_med.render(res1, True, (245, 205, 85)), (max(34, bx + 16), 86))
            surface.blit(self.font_small.render(res2, True, (225, 235, 245)), (max(34, bx + 16), 108))

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
            p_f = [p for p in personas_activas if p.floor == f]
            z_f = [z for z in zombies_activos if z.floor == f]
            m_f = [m for m in medicos_activos if m.floor == f]
            p_cnt = len(p_f)
            z_cnt = len(z_f)
            m_cnt = len(m_f)
            f_cnt = sum(1 for p in p_f if getattr(p, "tipo_humano", "") == "FUERTE")
            d_cnt = sum(1 for p in p_f if getattr(p, "tipo_humano", "") == "DEBIL")
            zg_cnt = sum(1 for z in z_f if getattr(z, "tipo_zombie", "") == "GRANDE")
            zn_cnt = sum(1 for z in z_f if getattr(z, "tipo_zombie", "") == "NORMAL")
            m_dosis = sum(m.dosis for m in m_f)
            is_sel = camera.focused_floor == f
            row_col = (245, 210, 90) if is_sel else (195, 210, 225)
            med_str = f" Med={m_cnt}({m_dosis}D)" if (f + 1) % 2 == 0 or m_cnt > 0 else "          "
            line_str = f"P{f+1}: San={p_cnt:02d}({f_cnt}F/{d_cnt}D) Zomb={z_cnt:02d}({zg_cnt}G/{zn_cnt}N){med_str}"
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
            f"[+/-] Vel  [Q/W] N Personas  [A/S] M Zombies  [R] Reiniciar  [{snd_tag}]"
        )
        surface.blit(self.font_small.render(ctrl, True, (195, 215, 235)), (20, h - 34))
