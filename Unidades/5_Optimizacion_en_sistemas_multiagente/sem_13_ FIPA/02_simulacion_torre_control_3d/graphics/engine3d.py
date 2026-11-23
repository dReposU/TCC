"""
Motor de renderizado 3D en tiempo real sobre PyGame + NumPy.
Carga modelos .obj, aplica transformaciones 3D (traslación, yaw, pitch, roll),
iluminación direccional, ordenamiento por profundidad (Painter's Algorithm),
pista de aterrizaje iluminada, torre de control con baliza de estado y ondas de radio ACL.
"""
import math
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import numpy as np
import pygame

from agents.acl import AgentPlatform, Performative
from agents.avion_agent import AvionAgent
from agents.torre_agent import TorreAgent


@dataclass
class Mesh3D:
    vertices: np.ndarray  # shape (N, 3)
    faces: List[Tuple[int, ...]]

    @classmethod
    def load_obj(cls, filepath: str) -> "Mesh3D":
        verts: List[Tuple[float, float, float]] = []
        faces: List[Tuple[int, ...]] = []
        with open(filepath, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts[0] == "v" and len(parts) >= 4:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif parts[0] == "f" and len(parts) >= 4:
                    idxs = []
                    for token in parts[1:]:
                        v_idx = int(token.split("/")[0]) - 1
                        idxs.append(v_idx)
                    faces.append(tuple(idxs))
        return cls(vertices=np.array(verts, dtype=np.float64), faces=faces)


class Camera3D:
    MODES = [
        "1: Órbita Libre",
        "2: Vista Torre de Control",
        "3: Seguir Avión Aterrizando",
        "4: Panorámica Aérea",
    ]

    def __init__(self) -> None:
        self.yaw: float = 0.68
        self.pitch: float = 0.44
        self.distance: float = 78.0
        self.target = np.array([0.0, 4.0, 0.0], dtype=np.float64)
        self.fov_deg: float = 55.0
        self.mode_index: int = 0

    def set_mode(self, idx: int) -> None:
        self.mode_index = idx % len(self.MODES)
        if self.mode_index == 0:
            self.target = np.array([0.0, 4.0, 0.0], dtype=np.float64)
            self.distance = 78.0
            self.pitch = 0.44
        elif self.mode_index == 1:
            # Cerca de la cabina de la Torre mirando hacia la pista
            self.target = np.array([0.0, 3.0, 2.0], dtype=np.float64)
            self.yaw = -1.25
            self.pitch = 0.18
            self.distance = 22.0
        elif self.mode_index == 3:
            # Vista cenital inclinada
            self.target = np.array([0.0, 0.0, 0.0], dtype=np.float64)
            self.pitch = 1.18
            self.distance = 96.0

    def update(self, dt: float, platform: AgentPlatform) -> None:
        if self.mode_index == 2:
            # Buscar avión aterrizando o el primero activo
            landing = [
                a for a in platform.agents.values()
                if isinstance(a, AvionAgent) and a.estado in ("ATERRIZANDO", "EN_PISTA")
            ]
            if not landing:
                landing = [a for a in platform.agents.values() if isinstance(a, AvionAgent)]
            if landing:
                plane = landing[0]
                desired = np.array(plane.position, dtype=np.float64)
                self.target += (desired - self.target) * min(1.0, dt * 4.5)
                self.distance = 26.0
                self.pitch = 0.30
        elif self.mode_index == 0:
            # Suave rotación automática opcional si no se arrastra
            pass

    def get_eye_and_basis(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        cos_p = math.cos(self.pitch)
        sin_p = math.sin(self.pitch)
        cos_y = math.cos(self.yaw)
        sin_y = math.sin(self.yaw)

        offset = np.array([
            self.distance * cos_p * sin_y,
            self.distance * sin_p,
            self.distance * cos_p * cos_y,
        ], dtype=np.float64)
        eye = self.target + offset

        forward = self.target - eye
        norm_f = np.linalg.norm(forward)
        forward = forward / norm_f if norm_f > 1e-8 else np.array([0.0, 0.0, -1.0])

        world_up = np.array([0.0, 1.0, 0.0], dtype=np.float64)
        right = np.cross(forward, world_up)
        norm_r = np.linalg.norm(right)
        right = right / norm_r if norm_r > 1e-8 else np.array([1.0, 0.0, 0.0])

        up = np.cross(right, forward)
        return eye, right, up, forward


class Renderer3D:
    def __init__(self, assets_dir: str) -> None:
        models_dir = os.path.join(assets_dir, "models")
        self.airplane_mesh = Mesh3D.load_obj(os.path.join(models_dir, "airplane.obj"))
        self.tower_mesh = Mesh3D.load_obj(os.path.join(models_dir, "control_tower.obj"))
        self.hangar_mesh = Mesh3D.load_obj(os.path.join(models_dir, "hangar.obj"))
        self.camera = Camera3D()
        self.light_dir = np.array([0.45, 0.82, 0.35], dtype=np.float64)
        self.light_dir /= np.linalg.norm(self.light_dir)
        self.label_font: Optional[pygame.font.Font] = None

    def _ensure_font(self) -> pygame.font.Font:
        if self.label_font is None:
            self.label_font = pygame.font.SysFont("consolas", 13, bold=True)
        return self.label_font

    @staticmethod
    def _transform_vertices(
        verts: np.ndarray,
        pos: Tuple[float, float, float],
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        scale: float = 1.0,
    ) -> np.ndarray:
        v = verts * scale
        # Rotación Roll (Z), Pitch (X), Yaw (Y)
        if abs(roll) > 1e-5:
            cr, sr = math.cos(roll), math.sin(roll)
            rz = np.array([[cr, -sr, 0.0], [sr, cr, 0.0], [0.0, 0.0, 1.0]])
            v = v @ rz.T
        if abs(pitch) > 1e-5:
            cp, sp = math.cos(pitch), math.sin(pitch)
            rx = np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]])
            v = v @ rx.T
        if abs(yaw) > 1e-5:
            cy, sy = math.cos(yaw), math.sin(yaw)
            ry = np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]])
            v = v @ ry.T
        return v + np.array(pos, dtype=np.float64)

    def _project_points(
        self,
        world_pts: np.ndarray,
        eye: np.ndarray,
        right: np.ndarray,
        up: np.ndarray,
        forward: np.ndarray,
        width: int,
        height: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        rel = world_pts - eye
        x_cam = rel @ right
        y_cam = rel @ up
        z_cam = rel @ forward

        focal = (0.5 * width) / math.tan(math.radians(self.camera.fov_deg * 0.5))
        safe_z = np.maximum(z_cam, 0.35)
        sx = (width * 0.5) + (x_cam * focal) / safe_z
        sy = (height * 0.5) - (y_cam * focal) / safe_z
        screen_pts = np.stack([sx, sy], axis=-1)
        return screen_pts, z_cam

    def _draw_sky_and_ground(self, surface: pygame.Surface, width: int, height: int) -> None:
        # Cielo degradado nocturno/crepúsculo aeronáutico
        top_col = np.array([12, 22, 42], dtype=np.float64)
        hor_col = np.array([32, 58, 92], dtype=np.float64)
        bands = 24
        band_h = math.ceil(height / bands)
        for i in range(bands):
            t = i / max(1, bands - 1)
            c = (top_col * (1.0 - t) + hor_col * t).astype(int)
            pygame.draw.rect(surface, tuple(c), (0, i * band_h, width, band_h + 1))

    def _queue_mesh(
        self,
        draw_list: list,
        mesh: Mesh3D,
        pos: Tuple[float, float, float],
        base_color: Tuple[int, int, int],
        eye: np.ndarray,
        right: np.ndarray,
        up: np.ndarray,
        forward: np.ndarray,
        width: int,
        height: int,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        scale: float = 1.0,
        outline_color: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        w_verts = self._transform_vertices(mesh.vertices, pos, yaw, pitch, roll, scale)
        s_pts, z_cam = self._project_points(w_verts, eye, right, up, forward, width, height)

        for face in mesh.faces:
            zs = [z_cam[i] for i in face]
            if min(zs) <= 0.5:
                continue
            avg_z = sum(zs) / len(zs)
            p0, p1, p2 = w_verts[face[0]], w_verts[face[1]], w_verts[face[2]]
            normal = np.cross(p1 - p0, p2 - p0)
            norm_len = np.linalg.norm(normal)
            if norm_len > 1e-7:
                normal /= norm_len
            intensity = 0.42 + 0.58 * max(0.0, float(np.dot(normal, self.light_dir)))
            shaded = (
                min(255, int(base_color[0] * intensity)),
                min(255, int(base_color[1] * intensity)),
                min(255, int(base_color[2] * intensity)),
            )
            poly_2d = [(int(s_pts[i, 0]), int(s_pts[i, 1])) for i in face]
            draw_list.append((avg_z, "poly", poly_2d, shaded, outline_color))

    def render(self, surface: pygame.Surface, platform: AgentPlatform, sim_time: float) -> None:
        width, height = surface.get_size()
        self._draw_sky_and_ground(surface, width, height)

        eye, right, up, forward = self.camera.get_eye_and_basis()

        # 1. Plano de terreno y cuadrícula 3D del aeródromo
        grid_lines = []
        extent = 75
        step = 15
        for g in range(-extent, extent + 1, step):
            grid_lines.append(((g, 0.0, -extent), (g, 0.0, extent)))
            grid_lines.append(((-extent, 0.0, g), (extent, 0.0, g)))

        # Polígono base del terreno
        ground_corners = np.array([
            [-85.0, -0.02, -85.0],
            [85.0, -0.02, -85.0],
            [85.0, -0.02, 85.0],
            [-85.0, -0.02, 85.0],
        ])
        g_pts, g_z = self._project_points(ground_corners, eye, right, up, forward, width, height)
        if np.min(g_z) > 0.5:
            pygame.draw.polygon(
                surface,
                (22, 36, 44),
                [(int(g_pts[i, 0]), int(g_pts[i, 1])) for i in range(4)],
            )

        for p_a, p_b in grid_lines:
            pts, zs = self._project_points(np.array([p_a, p_b]), eye, right, up, forward, width, height)
            if zs[0] > 0.6 and zs[1] > 0.6:
                pygame.draw.line(
                    surface,
                    (34, 54, 66),
                    (int(pts[0, 0]), int(pts[0, 1])),
                    (int(pts[1, 0]), int(pts[1, 1])),
                    1,
                )

        # 2. Pista de Aterrizaje 3D (Runway 36/18 en X=0, Z=[-36, 36])
        runway_quad = np.array([
            [-4.6, 0.01, -36.0],
            [4.6, 0.01, -36.0],
            [4.6, 0.01, 36.0],
            [-4.6, 0.01, 36.0],
        ])
        rw_pts, rw_z = self._project_points(runway_quad, eye, right, up, forward, width, height)
        if np.min(rw_z) > 0.5:
            pygame.draw.polygon(
                surface,
                (44, 48, 56),
                [(int(rw_pts[i, 0]), int(rw_pts[i, 1])) for i in range(4)],
            )
            pygame.draw.polygon(
                surface,
                (170, 180, 195),
                [(int(rw_pts[i, 0]), int(rw_pts[i, 1])) for i in range(4)],
                2,
            )

        # Marcas centrales de pista y luces de borde
        for z_mark in range(-30, 31, 6):
            seg = np.array([[0.0, 0.03, z_mark - 1.5], [0.0, 0.03, z_mark + 1.5]])
            sp, sz = self._project_points(seg, eye, right, up, forward, width, height)
            if sz[0] > 0.6 and sz[1] > 0.6:
                pygame.draw.line(
                    surface,
                    (235, 240, 245),
                    (int(sp[0, 0]), int(sp[0, 1])),
                    (int(sp[1, 0]), int(sp[1, 1])),
                    2,
                )
            # Luces laterales de pista (verdes en cabecera, ámbar en resto)
            light_col = (80, 255, 130) if z_mark <= -24 else (255, 195, 70)
            edge_pts = np.array([[-4.8, 0.15, float(z_mark)], [4.8, 0.15, float(z_mark)]])
            ep, ez = self._project_points(edge_pts, eye, right, up, forward, width, height)
            for k in range(2):
                if ez[k] > 0.6:
                    pygame.draw.circle(surface, light_col, (int(ep[k, 0]), int(ep[k, 1])), 3)

        # Lista de elementos 3D ordenados por profundidad (Painter's algorithm)
        draw_list: list = []

        # 3. Torre de Control y Hangares
        torre = platform.agents.get("Torre")
        torre_pos = tuple(torre.position) if torre else (-11.5, 0.0, -3.0)
        self._queue_mesh(
            draw_list,
            self.tower_mesh,
            torre_pos,
            (185, 200, 215),
            eye,
            right,
            up,
            forward,
            width,
            height,
            scale=1.25,
            outline_color=(50, 70, 90),
        )
        # Hangares aeroportuarios
        for h_pos in [(-14.0, 0.0, 14.0), (-14.0, 0.0, -18.0)]:
            self._queue_mesh(
                draw_list,
                self.hangar_mesh,
                h_pos,
                (110, 135, 160),
                eye,
                right,
                up,
                forward,
                width,
                height,
                scale=1.15,
                outline_color=(45, 60, 75),
            )

        # Antena radar giratoria + Baliza de estado en la cima de la Torre
        radar_ang = torre.radar_angle if isinstance(torre, TorreAgent) else sim_time * 1.8
        top_y = 12.4
        r_dx, r_dz = math.cos(radar_ang) * 2.3, math.sin(radar_ang) * 2.3
        radar_seg = np.array([
            [torre_pos[0] - r_dx, top_y, torre_pos[2] - r_dz],
            [torre_pos[0] + r_dx, top_y, torre_pos[2] + r_dz],
            [torre_pos[0], top_y + 0.8, torre_pos[2]],
        ])
        rp, rz = self._project_points(radar_seg, eye, right, up, forward, width, height)
        if np.min(rz) > 0.6:
            draw_list.append((
                float(np.mean(rz)),
                "line",
                (int(rp[0, 0]), int(rp[0, 1])),
                (int(rp[1, 0]), int(rp[1, 1])),
                (120, 240, 255),
                3,
            ))
            beacon_col = (255, 65, 65) if TorreAgent.pista_ocupada else (70, 255, 135)
            pulse_r = 7 + int(2.5 * math.sin(sim_time * 6.0)) if TorreAgent.pista_ocupada else 6
            draw_list.append((
                float(rz[2]),
                "circle",
                (int(rp[2, 0]), int(rp[2, 1])),
                pulse_r,
                beacon_col,
            ))

        # 4. Aviones 3D (Avion_1..Avion_N), sombras en tierra y estelas
        labels_to_draw = []
        for agent in platform.agents.values():
            if not isinstance(agent, AvionAgent) or not agent.alive:
                continue

            px, py, pz = agent.position
            # Sombra proyectada en el suelo (y = 0.04)
            shadow_pt, shadow_z = self._project_points(
                np.array([[px, 0.04, pz]]), eye, right, up, forward, width, height
            )
            if shadow_z[0] > 0.6:
                rad = max(3, int(220.0 / shadow_z[0]))
                draw_list.append((
                    float(shadow_z[0]) + 1.0,
                    "circle",
                    (int(shadow_pt[0, 0]), int(shadow_pt[0, 1])),
                    rad,
                    (14, 24, 30),
                ))

            # Estela de trayectoria 3D
            if len(agent.trail) >= 2:
                trail_arr = np.array(list(agent.trail), dtype=np.float64)
                tp, tz = self._project_points(trail_arr, eye, right, up, forward, width, height)
                for i in range(len(tp) - 1):
                    if tz[i] > 0.6 and tz[i + 1] > 0.6:
                        fade = (i + 1) / len(tp)
                        t_col = (
                            int(agent.color[0] * fade * 0.7),
                            int(agent.color[1] * fade * 0.7),
                            int(agent.color[2] * fade * 0.7),
                        )
                        draw_list.append((
                            float((tz[i] + tz[i + 1]) * 0.5),
                            "line",
                            (int(tp[i, 0]), int(tp[i, 1])),
                            (int(tp[i + 1, 0]), int(tp[i + 1, 1])),
                            t_col,
                            2,
                        ))

            # Malla 3D del avión
            self._queue_mesh(
                draw_list,
                self.airplane_mesh,
                (px, py, pz),
                agent.color,
                eye,
                right,
                up,
                forward,
                width,
                height,
                yaw=agent.yaw,
                pitch=agent.pitch,
                roll=agent.roll,
                scale=1.15,
                outline_color=(25, 30, 38),
            )

            # Guardar posición de etiqueta flotante
            lbl_pt, lbl_z = self._project_points(
                np.array([[px, py + 2.3, pz]]), eye, right, up, forward, width, height
            )
            if lbl_z[0] > 0.6:
                labels_to_draw.append((
                    int(lbl_pt[0, 0]),
                    int(lbl_pt[0, 1]),
                    agent.local_name,
                    agent.estado,
                    agent.color,
                ))

        # 5. Ondas / Rayos de Radio ACL en 3D entre Avion y Torre
        for beam in platform.radio_beams:
            a_src = platform.agents.get(beam.sender_name)
            a_dst = platform.agents.get(beam.receiver_name)
            if a_src is None or a_dst is None:
                continue
            p_src = np.array(a_src.position, dtype=np.float64) + np.array([0.0, 1.0, 0.0])
            p_dst = np.array(a_dst.position, dtype=np.float64) + np.array([0.0, 3.0, 0.0])
            if beam.sender_name == "Torre":
                p_src[1] += 7.0
            if beam.receiver_name == "Torre":
                p_dst[1] += 7.0

            b_pts, b_z = self._project_points(np.array([p_src, p_dst]), eye, right, up, forward, width, height)
            if b_z[0] > 0.6 and b_z[1] > 0.6:
                if beam.performative == Performative.INFORM:
                    b_col = (90, 215, 255)
                elif beam.performative == Performative.PROPOSE:
                    b_col = (255, 225, 85)
                elif beam.performative == Performative.ACCEPT_PROPOSAL:
                    b_col = (85, 255, 145)
                else:
                    b_col = (255, 95, 95)

                p0 = (int(b_pts[0, 0]), int(b_pts[0, 1]))
                p1 = (int(b_pts[1, 0]), int(b_pts[1, 1]))
                draw_list.append((float(np.mean(b_z)), "line", p0, p1, b_col, 2))

                # Paquete viajando por el rayo
                progress = 1.0 - (beam.ttl / beam.max_ttl)
                mx = int(p0[0] + (p1[0] - p0[0]) * progress)
                my = int(p0[1] + (p1[1] - p0[1]) * progress)
                draw_list.append((float(np.mean(b_z)) - 0.1, "circle", (mx, my), 5, b_col))

        # Ordenar de más lejano a más cercano (Painter's Algorithm)
        draw_list.sort(key=lambda item: item[0], reverse=True)
        for item in draw_list:
            kind = item[1]
            if kind == "poly":
                _, _, poly_2d, fill_col, out_col = item
                pygame.draw.polygon(surface, fill_col, poly_2d)
                if out_col is not None:
                    pygame.draw.polygon(surface, out_col, poly_2d, 1)
            elif kind == "line":
                _, _, p0, p1, col, w = item
                pygame.draw.line(surface, col, p0, p1, w)
            elif kind == "circle":
                _, _, center, rad, col = item
                pygame.draw.circle(surface, col, center, rad)

        # Dibujar etiquetas flotantes de cada avión y de la Torre
        font = self._ensure_font()
        t_lbl_pt, t_lbl_z = self._project_points(
            np.array([[torre_pos[0], 14.3, torre_pos[2]]]), eye, right, up, forward, width, height
        )
        if t_lbl_z[0] > 0.6:
            txt = font.render("TORRE DE CONTROL", True, (150, 235, 255))
            surface.blit(txt, (int(t_lbl_pt[0, 0]) - txt.get_width() // 2, int(t_lbl_pt[0, 1])))

        for lx, ly, name, estado, col in labels_to_draw:
            tag = f"{name}" if estado == "VOLANDO" else f"{name} [{estado}]"
            txt = font.render(tag, True, col)
            bg_rect = pygame.Rect(lx - txt.get_width() // 2 - 4, ly - 2, txt.get_width() + 8, txt.get_height() + 4)
            pygame.draw.rect(surface, (12, 18, 28), bg_rect, border_radius=4)
            surface.blit(txt, (lx - txt.get_width() // 2, ly))
