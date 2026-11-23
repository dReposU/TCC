"""
Motor 3D en perspectiva sobre PyGame + NumPy con animaciones articuladas:
- Edificio universitario de 8 pisos, 4 aulas por piso y 3 salidas de emergencia por piso.
- Personajes 3D articulados (torso/cabeza + 4 extremidades animadas por ciclo de marcha/carrera y postura zombie).
- Efectos 3D de infección, salvamento y rayos de mensajes FIPA-ACL.
"""
import math
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple
import numpy as np
import pygame

from agents.acl import AgentPlatform, Performative
from agents.persona_agent import PersonaAgent
from agents.zombie_agent import ZombieAgent
from agents.medico_agent import MedicoAgent
from world.university import UniversityBuilding


@dataclass
class Mesh3D:
    vertices: np.ndarray
    faces: List[Tuple[int, ...]]

    @classmethod
    def load_obj(cls, filepath: str) -> "Mesh3D":
        verts: List[Tuple[float, float, float]] = []
        faces: List[Tuple[int, ...]] = []
        with open(filepath, "r", encoding="utf-8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                parts = line.split()
                if parts[0] == "v" and len(parts) >= 4:
                    verts.append((float(parts[1]), float(parts[2]), float(parts[3])))
                elif parts[0] == "f" and len(parts) >= 4:
                    faces.append(tuple(int(tok.split("/")[0]) - 1 for tok in parts[1:]))
        return cls(vertices=np.array(verts, dtype=np.float64), faces=faces)


class Camera3D:
    def __init__(self, building: UniversityBuilding) -> None:
        self.building = building
        self.yaw: float = 0.56
        self.pitch: float = 0.36
        self.distance: float = 64.0
        mid_y = (building.NUM_FLOORS - 1) * building.FLOOR_HEIGHT * 0.5
        self.target = np.array([0.0, mid_y, 0.0], dtype=np.float64)
        self.desired_target = self.target.copy()
        self.desired_distance = self.distance
        self.focused_floor: Optional[int] = None
        self.fov_deg: float = 54.0

    def focus_all_floors(self) -> None:
        self.focused_floor = None
        mid_y = (self.building.NUM_FLOORS - 1) * self.building.FLOOR_HEIGHT * 0.5
        self.desired_target = np.array([0.0, mid_y, 0.0], dtype=np.float64)
        self.desired_distance = 64.0

    def focus_floor(self, floor_idx: int) -> None:
        floor_idx = max(0, min(self.building.NUM_FLOORS - 1, floor_idx))
        self.focused_floor = floor_idx
        y = self.building.floors_y[floor_idx] + 1.2
        self.desired_target = np.array([0.0, y, 0.0], dtype=np.float64)
        self.desired_distance = 36.0

    def update(self, dt: float) -> None:
        alpha = min(1.0, dt * 6.0)
        self.target += (self.desired_target - self.target) * alpha
        self.distance += (self.desired_distance - self.distance) * alpha

    def get_eye_and_basis(self) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        offset = np.array([
            self.distance * cp * sy,
            self.distance * sp,
            self.distance * cp * cy,
        ], dtype=np.float64)
        eye = self.target + offset
        forward = self.target - eye
        nf = np.linalg.norm(forward)
        forward = forward / nf if nf > 1e-8 else np.array([0.0, 0.0, -1.0])
        right = np.cross(forward, np.array([0.0, 1.0, 0.0]))
        nr = np.linalg.norm(right)
        right = right / nr if nr > 1e-8 else np.array([1.0, 0.0, 0.0])
        up = np.cross(right, forward)
        return eye, right, up, forward


class Renderer3D:
    def __init__(self, assets_dir: str, building: UniversityBuilding) -> None:
        models_dir = os.path.join(assets_dir, "models")
        self.body_mesh = Mesh3D.load_obj(os.path.join(models_dir, "character_body.obj"))
        self.limb_mesh = Mesh3D.load_obj(os.path.join(models_dir, "character_limb.obj"))
        self.desk_mesh = Mesh3D.load_obj(os.path.join(models_dir, "desk.obj"))
        self.exit_mesh = Mesh3D.load_obj(os.path.join(models_dir, "exit_gate.obj"))

        # Mallas 3D para el Médico: Gorrito con cruz roja y cruz roja en el pecho
        self.medico_cap_mesh = self._create_box_mesh(-0.18, 0.18, 1.66, 1.79, -0.18, 0.18)
        self.medico_chest_cross_mesh = self._create_cross_mesh(center_y=0.95, z_pos=0.142, arm_len=0.125, bar_w=0.055, depth=0.008)
        self.medico_cap_cross_mesh = self._create_cross_mesh(center_y=1.725, z_pos=0.181, arm_len=0.042, bar_w=0.020, depth=0.006)

        self.camera = Camera3D(building)
        self.light_dir = np.array([0.42, 0.85, 0.32], dtype=np.float64)
        self.light_dir /= np.linalg.norm(self.light_dir)
        self._font_tag: Optional[pygame.font.Font] = None
        self._font_fx: Optional[pygame.font.Font] = None

    @staticmethod
    def _create_box_mesh(min_x: float, max_x: float, min_y: float, max_y: float, min_z: float, max_z: float) -> Mesh3D:
        verts = np.array([
            [min_x, min_y, min_z],
            [max_x, min_y, min_z],
            [max_x, max_y, min_z],
            [min_x, max_y, min_z],
            [min_x, min_y, max_z],
            [max_x, min_y, max_z],
            [max_x, max_y, max_z],
            [min_x, max_y, max_z],
        ], dtype=np.float64)
        faces = [
            (0, 3, 2, 1),
            (4, 5, 6, 7),
            (0, 1, 5, 4),
            (2, 3, 7, 6),
            (1, 2, 6, 5),
            (3, 0, 4, 7),
        ]
        return Mesh3D(vertices=verts, faces=faces)

    @classmethod
    def _create_cross_mesh(cls, center_y: float, z_pos: float, arm_len: float, bar_w: float, depth: float = 0.008) -> Mesh3D:
        b1 = cls._create_box_mesh(-bar_w * 0.5, bar_w * 0.5, center_y - arm_len, center_y + arm_len, z_pos, z_pos + depth)
        b2 = cls._create_box_mesh(-arm_len, arm_len, center_y - bar_w * 0.5, center_y + bar_w * 0.5, z_pos, z_pos + depth)
        verts = np.vstack([b1.vertices, b2.vertices])
        faces = list(b1.faces) + [tuple(idx + len(b1.vertices) for idx in f) for f in b2.faces]
        return Mesh3D(vertices=verts, faces=faces)

    def _get_fonts(self) -> Tuple[pygame.font.Font, pygame.font.Font]:
        if self._font_tag is None:
            self._font_tag = pygame.font.SysFont("consolas", 11, bold=True)
            self._font_fx = pygame.font.SysFont("consolas", 13, bold=True)
        return self._font_tag, self._font_fx

    @staticmethod
    def _transform(
        verts: np.ndarray,
        pos: Tuple[float, float, float],
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        scale: float = 1.0,
    ) -> np.ndarray:
        v = verts * scale
        if abs(roll) > 1e-5:
            cr, sr = math.cos(roll), math.sin(roll)
            v = v @ np.array([[cr, -sr, 0.0], [sr, cr, 0.0], [0.0, 0.0, 1.0]]).T
        if abs(pitch) > 1e-5:
            cp, sp = math.cos(pitch), math.sin(pitch)
            v = v @ np.array([[1.0, 0.0, 0.0], [0.0, cp, -sp], [0.0, sp, cp]]).T
        if abs(yaw) > 1e-5:
            cy, sy = math.cos(yaw), math.sin(yaw)
            v = v @ np.array([[cy, 0.0, sy], [0.0, 1.0, 0.0], [-sy, 0.0, cy]]).T
        return v + np.array(pos, dtype=np.float64)

    def _project(
        self,
        pts: np.ndarray,
        eye: np.ndarray,
        right: np.ndarray,
        up: np.ndarray,
        forward: np.ndarray,
        w: int,
        h: int,
    ) -> Tuple[np.ndarray, np.ndarray]:
        rel = pts - eye
        xc = rel @ right
        yc = rel @ up
        zc = rel @ forward
        focal = (0.5 * w) / math.tan(math.radians(self.camera.fov_deg * 0.5))
        sz = np.maximum(zc, 0.35)
        sx = (w * 0.5) + (xc * focal) / sz
        sy = (h * 0.5) - (yc * focal) / sz
        return np.stack([sx, sy], axis=-1), zc

    def _queue_mesh(
        self,
        draw_list: list,
        mesh: Mesh3D,
        pos: Tuple[float, float, float],
        color: Tuple[int, int, int],
        eye: np.ndarray,
        right: np.ndarray,
        up: np.ndarray,
        forward: np.ndarray,
        w: int,
        h: int,
        yaw: float = 0.0,
        pitch: float = 0.0,
        roll: float = 0.0,
        scale: float = 1.0,
        outline: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        wv = self._transform(mesh.vertices, pos, yaw, pitch, roll, scale)
        sp, zc = self._project(wv, eye, right, up, forward, w, h)
        for face in mesh.faces:
            zs = [zc[i] for i in face]
            if min(zs) <= 0.5:
                continue
            avg_z = sum(zs) / len(zs)
            p0, p1, p2 = wv[face[0]], wv[face[1]], wv[face[2]]
            normal = np.cross(p1 - p0, p2 - p0)
            nl = np.linalg.norm(normal)
            if nl > 1e-7:
                normal /= nl
            shade = 0.45 + 0.55 * max(0.0, float(np.dot(normal, self.light_dir)))
            col = (
                min(255, int(color[0] * shade)),
                min(255, int(color[1] * shade)),
                min(255, int(color[2] * shade)),
            )
            poly = [(int(sp[i, 0]), int(sp[i, 1])) for i in face]
            draw_list.append((avg_z, "poly", poly, col, outline))

    def _queue_articulated_character(
        self,
        draw_list: list,
        pos: List[float],
        yaw: float,
        walk_phase: float,
        body_color: Tuple[int, int, int],
        limb_color: Tuple[int, int, int],
        is_zombie: bool,
        bite_timer: float,
        eye: np.ndarray,
        right: np.ndarray,
        up: np.ndarray,
        forward: np.ndarray,
        w: int,
        h: int,
        scale: float = 0.92,
        is_medico: bool = False,
    ) -> None:
        s_factor = scale / 0.92
        bob = abs(math.sin(walk_phase)) * 0.12 * s_factor
        body_pitch = 0.18 if is_zombie else 0.06
        if bite_timer > 0.0:
            body_pitch += 0.35 * math.sin((bite_timer / 0.65) * math.pi)

        base_pos = (pos[0], pos[1] + bob, pos[2])
        self._queue_mesh(
            draw_list,
            self.body_mesh,
            base_pos,
            body_color,
            eye,
            right,
            up,
            forward,
            w,
            h,
            yaw=yaw,
            pitch=body_pitch,
            scale=scale,
            outline=(18, 22, 28) if not is_medico else (180, 190, 205),
        )

        if is_medico:
            # Gorrito médico blanco en la cabeza
            self._queue_mesh(
                draw_list,
                self.medico_cap_mesh,
                base_pos,
                (255, 255, 255),
                eye,
                right,
                up,
                forward,
                w,
                h,
                yaw=yaw,
                pitch=body_pitch,
                scale=scale,
                outline=(190, 195, 205),
            )
            # Pequeña cruz roja en el gorrito
            self._queue_mesh(
                draw_list,
                self.medico_cap_cross_mesh,
                base_pos,
                (235, 25, 35),
                eye,
                right,
                up,
                forward,
                w,
                h,
                yaw=yaw,
                pitch=body_pitch,
                scale=scale,
            )
            # Cruz roja visible en el pecho
            self._queue_mesh(
                draw_list,
                self.medico_chest_cross_mesh,
                base_pos,
                (235, 25, 35),
                eye,
                right,
                up,
                forward,
                w,
                h,
                yaw=yaw,
                pitch=body_pitch,
                scale=scale,
            )

        cy, sy = math.cos(yaw), math.sin(yaw)

        def local_to_world(lx: float, ly: float, lz: float) -> Tuple[float, float, float]:
            wx = pos[0] + lx * cy + lz * sy
            wy = pos[1] + ly + bob
            wz = pos[2] - lx * sy + lz * cy
            return (wx, wy, wz)

        leg_swing = math.sin(walk_phase) * 0.65
        if is_zombie:
            arm_l_pitch = -1.25 + math.sin(walk_phase * 0.8) * 0.18
            arm_r_pitch = -1.25 - math.sin(walk_phase * 0.8) * 0.18
            if bite_timer > 0.0:
                arm_l_pitch -= 0.45
                arm_r_pitch -= 0.45
        else:
            arm_l_pitch = -leg_swing * 0.85
            arm_r_pitch = leg_swing * 0.85

        for side, a_pitch in [(-0.31 * s_factor, arm_l_pitch), (0.31 * s_factor, arm_r_pitch)]:
            shoulder_pos = local_to_world(side, 1.18 * s_factor, 0.0)
            self._queue_mesh(
                draw_list,
                self.limb_mesh,
                shoulder_pos,
                limb_color,
                eye,
                right,
                up,
                forward,
                w,
                h,
                yaw=yaw,
                pitch=a_pitch,
                scale=0.88 * s_factor,
            )

        pants_color = (228, 234, 244) if is_medico else ((28, 20, 24) if (is_zombie and scale > 1.2) else (38, 46, 60))
        for side, l_pitch in [(-0.14 * s_factor, leg_swing), (0.14 * s_factor, -leg_swing)]:
            hip_pos = local_to_world(side, 0.58 * s_factor, 0.0)
            self._queue_mesh(
                draw_list,
                self.limb_mesh,
                hip_pos,
                pants_color,
                eye,
                right,
                up,
                forward,
                w,
                h,
                yaw=yaw,
                pitch=l_pitch,
                scale=0.92 * s_factor,
            )

    def render(self, surface: pygame.Surface, platform: AgentPlatform, sim_time: float) -> None:
        w, h = surface.get_size()
        surface.fill((14, 20, 32))

        eye, right, up, forward = self.camera.get_eye_and_basis()
        building: UniversityBuilding = platform.building
        draw_list: list = []

        for f in range(building.NUM_FLOORS):
            if self.camera.focused_floor is not None and f != self.camera.focused_floor:
                if abs(f - self.camera.focused_floor) > 1:
                    continue
                dim_factor = 0.35
            else:
                dim_factor = 1.0

            y = building.floors_y[f]
            hx = building.BUILDING_WIDTH * 0.5
            hz = building.BUILDING_DEPTH * 0.5

            slab_pts = np.array([
                [-hx, y, -hz],
                [hx, y, -hz],
                [hx, y, hz],
                [-hx, y, hz],
            ])
            sp, sz = self._project(slab_pts, eye, right, up, forward, w, h)
            if np.min(sz) > 0.5:
                avg_z = float(np.mean(sz)) + 2.0
                base_slab = (int(34 * dim_factor), int(44 * dim_factor), int(58 * dim_factor))
                border_slab = (int(85 * dim_factor), int(120 * dim_factor), int(150 * dim_factor))
                draw_list.append((
                    avg_z,
                    "poly",
                    [(int(sp[i, 0]), int(sp[i, 1])) for i in range(4)],
                    base_slab,
                    border_slab,
                ))

            for room in building.classrooms[f]:
                rx, _, rz = room.center
                rhx, rhz = room.size[0] * 0.5, room.size[1] * 0.5
                r_corners = np.array([
                    [rx - rhx, y + 0.03, rz - rhz],
                    [rx + rhx, y + 0.03, rz - rhz],
                    [rx + rhx, y + 0.03, rz + rhz],
                    [rx - rhx, y + 0.03, rz + rhz],
                ])
                rp, r_z = self._project(r_corners, eye, right, up, forward, w, h)
                if np.min(r_z) > 0.5:
                    room_fill = (int(46 * dim_factor), int(58 * dim_factor), int(76 * dim_factor))
                    room_edge = (int(110 * dim_factor), int(150 * dim_factor), int(190 * dim_factor))
                    draw_list.append((
                        float(np.mean(r_z)) + 1.5,
                        "poly",
                        [(int(rp[i, 0]), int(rp[i, 1])) for i in range(4)],
                        room_fill,
                        room_edge,
                    ))

                if self.camera.focused_floor == f or f in (0, 7):
                    for dx_off in (-3.2, 3.2):
                        self._queue_mesh(
                            draw_list,
                            self.desk_mesh,
                            (rx + dx_off, y + 0.03, rz),
                            (int(145 * dim_factor), int(115 * dim_factor), int(85 * dim_factor)),
                            eye,
                            right,
                            up,
                            forward,
                            w,
                            h,
                            scale=0.95,
                        )

            for ex in building.exits[f]:
                ex_yaw = 1.5708 if abs(ex.center[0]) > 10.0 else 0.0
                self._queue_mesh(
                    draw_list,
                    self.exit_mesh,
                    (ex.center[0], y, ex.center[2]),
                    (int(65 * dim_factor), int(235 * dim_factor), int(130 * dim_factor)),
                    eye,
                    right,
                    up,
                    forward,
                    w,
                    h,
                    yaw=ex_yaw,
                    scale=0.9,
                )
                beacon_pt, bz = self._project(
                    np.array([[ex.center[0], y + 2.25, ex.center[2]]]),
                    eye,
                    right,
                    up,
                    forward,
                    w,
                    h,
                )
                if bz[0] > 0.6:
                    pulse = 4 + int(2.0 * math.sin(sim_time * 5.0 + f))
                    draw_list.append((
                        float(bz[0]),
                        "circle",
                        (int(beacon_pt[0, 0]), int(beacon_pt[0, 1])),
                        pulse,
                        (80, 255, 145),
                    ))

        top_y = (building.NUM_FLOORS - 1) * building.FLOOR_HEIGHT + 3.5
        hx, hz = building.BUILDING_WIDTH * 0.5, building.BUILDING_DEPTH * 0.5
        for cx in (-hx, hx):
            for cz in (-hz, hz):
                col_pts, col_z = self._project(
                    np.array([[cx, 0.0, cz], [cx, top_y, cz]]), eye, right, up, forward, w, h
                )
                if col_z[0] > 0.6 and col_z[1] > 0.6:
                    draw_list.append((
                        float(np.mean(col_z)),
                        "line",
                        (int(col_pts[0, 0]), int(col_pts[0, 1])),
                        (int(col_pts[1, 0]), int(col_pts[1, 1])),
                        (75, 105, 135),
                        2,
                    ))

        for agent in platform.agents.values():
            if not agent.alive:
                continue
            if self.camera.focused_floor is not None and abs(agent.floor - self.camera.focused_floor) > 1:
                continue

            if isinstance(agent, PersonaAgent):
                self._queue_articulated_character(
                    draw_list,
                    agent.position,
                    agent.yaw,
                    agent.walk_phase,
                    body_color=agent.color,
                    limb_color=getattr(agent, "limb_color", (210, 225, 245)),
                    is_zombie=False,
                    bite_timer=0.0,
                    eye=eye,
                    right=right,
                    up=up,
                    forward=forward,
                    w=w,
                    h=h,
                    scale=getattr(agent, "scale", 0.92),
                )
            elif isinstance(agent, ZombieAgent):
                self._queue_articulated_character(
                    draw_list,
                    agent.position,
                    agent.yaw,
                    agent.walk_phase,
                    body_color=agent.color,
                    limb_color=getattr(agent, "limb_color", (95, 185, 95)),
                    is_zombie=True,
                    bite_timer=agent.bite_anim_timer,
                    eye=eye,
                    right=right,
                    up=up,
                    forward=forward,
                    w=w,
                    h=h,
                    scale=getattr(agent, "scale", 0.92),
                )
            elif isinstance(agent, MedicoAgent):
                self._queue_articulated_character(
                    draw_list,
                    agent.position,
                    agent.yaw,
                    agent.walk_phase,
                    body_color=agent.color,
                    limb_color=getattr(agent, "limb_color", (238, 242, 250)),
                    is_zombie=False,
                    bite_timer=0.0,
                    eye=eye,
                    right=right,
                    up=up,
                    forward=forward,
                    w=w,
                    h=h,
                    scale=getattr(agent, "scale", 0.94),
                    is_medico=True,
                )

        for beam in platform.radio_beams:
            src = platform.agents.get(beam.sender_name)
            dst = platform.agents.get(beam.receiver_name)
            if src is None or dst is None:
                continue
            p0 = np.array(src.position, dtype=np.float64) + np.array([0.0, 1.4, 0.0])
            p1 = np.array(dst.position, dtype=np.float64) + np.array([0.0, 1.4, 0.0])
            bp, bz = self._project(np.array([p0, p1]), eye, right, up, forward, w, h)
            if bz[0] > 0.6 and bz[1] > 0.6:
                col = (255, 85, 85) if beam.performative == Performative.ALERT else (95, 215, 255)
                draw_list.append((
                    float(np.mean(bz)),
                    "line",
                    (int(bp[0, 0]), int(bp[0, 1])),
                    (int(bp[1, 0]), int(bp[1, 1])),
                    col,
                    1,
                ))

        draw_list.sort(key=lambda item: item[0], reverse=True)
        for item in draw_list:
            kind = item[1]
            if kind == "poly":
                _, _, poly, fill, edge = item
                pygame.draw.polygon(surface, fill, poly)
                if edge is not None:
                    pygame.draw.polygon(surface, edge, poly, 1)
            elif kind == "line":
                _, _, a_pt, b_pt, col, lw = item
                pygame.draw.line(surface, col, a_pt, b_pt, lw)
            elif kind == "circle":
                _, _, center, rad, col = item
                pygame.draw.circle(surface, col, center, rad)

        font_tag, font_fx = self._get_fonts()
        for f in range(building.NUM_FLOORS):
            if self.camera.focused_floor is not None and abs(f - self.camera.focused_floor) > 1:
                continue
            y = building.floors_y[f] + 0.5
            pt, zc = self._project(np.array([[-19.8, y, 0.0]]), eye, right, up, forward, w, h)
            if zc[0] > 0.6:
                lbl = font_tag.render(f"PISO {f+1}", True, (160, 210, 245))
                surface.blit(lbl, (int(pt[0, 0]) - lbl.get_width(), int(pt[0, 1])))

        for eff in platform.effects_3d:
            ep, ez = self._project(np.array([eff.position]), eye, right, up, forward, w, h)
            if ez[0] > 0.6:
                txt = font_fx.render(eff.label, True, eff.color)
                surface.blit(txt, (int(ep[0, 0]) - txt.get_width() // 2, int(ep[0, 1])))

        if self.camera.focused_floor is not None:
            for agent in platform.agents.values():
                if not agent.alive or agent.floor != self.camera.focused_floor:
                    continue
                ag_scale = getattr(agent, "scale", 0.92)
                head_y = agent.position[1] + (ag_scale / 0.92) * 1.85
                pt, zc = self._project(np.array([[agent.position[0], head_y, agent.position[2]]]), eye, right, up, forward, w, h)
                if zc[0] > 0.6:
                    if isinstance(agent, PersonaAgent):
                        tag_str = "[FUERTE]" if agent.tipo_humano == "FUERTE" else "[DEBIL]"
                        tag_col = (255, 210, 85) if agent.tipo_humano == "FUERTE" else (150, 215, 255)
                    elif isinstance(agent, ZombieAgent):
                        tag_str = "[ZOMBIE GRANDE]" if agent.tipo_zombie == "GRANDE" else "[ZOMBIE]"
                        tag_col = (255, 65, 75) if agent.tipo_zombie == "GRANDE" else (115, 235, 125)
                    elif isinstance(agent, MedicoAgent):
                        if agent.estado == "ESCOLTANDO":
                            tag_str = f"[MÉDICO ESCOLTA | {agent.dosis}D]"
                        elif agent.dosis <= 0:
                            tag_str = "[MÉDICO SIN DOSIS]"
                        else:
                            tag_str = f"[MÉDICO | {agent.dosis}D]"
                        tag_col = (130, 245, 255)
                    else:
                        continue
                    lbl = font_tag.render(tag_str, True, tag_col)
                    surface.blit(lbl, (int(pt[0, 0]) - lbl.get_width() // 2, int(pt[0, 1]) - lbl.get_height()))
