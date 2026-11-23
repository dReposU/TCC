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
from world.university import UniversityBuilding

# Altura mínima en pantalla (px) para dibujar brazos y piernas; más pequeño = solo cuerpo.
LOD_ALTURA_MIN_PX = 14.0


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

        self.camera = Camera3D(building)
        self.light_dir = np.array([0.42, 0.85, 0.32], dtype=np.float64)
        self.light_dir /= np.linalg.norm(self.light_dir)
        self._font_tag: Optional[pygame.font.Font] = None
        self._font_fx: Optional[pygame.font.Font] = None

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
        # OPTIMIZACIÓN (fix de lag con muchos agentes): antes se calculaba la normal de
        # cada cara por separado con np.cross/np.linalg.norm (~150k llamadas numpy por
        # segundo con 180 personajes -> ~6 FPS). Ahora se calculan todas las caras de la
        # malla en una sola operación vectorizada y el resto del bucle usa listas Python.
        wv = self._transform(mesh.vertices, pos, yaw, pitch, roll, scale)
        sp, zc = self._project(wv, eye, right, up, forward, w, h)

        tri = getattr(mesh, "_tri_idx", None)
        if tri is None:
            tri = np.array([f[:3] for f in mesh.faces], dtype=np.int64)
            mesh._tri_idx = tri  # cache por malla
        p0, p1, p2 = wv[tri[:, 0]], wv[tri[:, 1]], wv[tri[:, 2]]
        a = p1 - p0
        b = p2 - p0
        nx = a[:, 1] * b[:, 2] - a[:, 2] * b[:, 1]   # producto cruz manual (np.cross es más lento
        ny = a[:, 2] * b[:, 0] - a[:, 0] * b[:, 2]   # para mallas tan pequeñas)
        nz = a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]
        nl = np.sqrt(nx * nx + ny * ny + nz * nz)
        nl[nl < 1e-7] = 1.0
        ld = self.light_dir
        dot = (nx * ld[0] + ny * ld[1] + nz * ld[2]) / nl
        shades = (0.45 + 0.55 * np.maximum(0.0, dot)).tolist()

        zc_l = zc.tolist()
        sp_l = sp.astype(np.int64).tolist()
        cr, cg, cb = color
        for k, face in enumerate(mesh.faces):
            zs = [zc_l[i] for i in face]
            if min(zs) <= 0.5:
                continue
            shade = shades[k]
            col = (min(255, int(cr * shade)), min(255, int(cg * shade)), min(255, int(cb * shade)))
            poly = [tuple(sp_l[i]) for i in face]
            draw_list.append((sum(zs) / len(zs), "poly", poly, col, outline))

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
    ) -> None:
        # OPTIMIZACIÓN: culling + nivel de detalle (LOD).
        # - Si el personaje está detrás de la cámara o fuera de pantalla, no se dibuja.
        # - Si se ve muy pequeño (lejos), se dibuja solo el cuerpo (1 malla en vez de 5).
        c_rel = np.array(pos, dtype=np.float64) - eye
        c_z = float(c_rel @ forward)
        if c_z <= 0.5:
            return
        focal = (0.5 * w) / math.tan(math.radians(self.camera.fov_deg * 0.5))
        c_sx = w * 0.5 + float(c_rel @ right) * focal / c_z
        c_sy = h * 0.5 - float(c_rel @ up) * focal / c_z
        alto_px = 1.8 * focal / c_z
        if c_sx < -alto_px or c_sx > w + alto_px or c_sy < -2 * alto_px or c_sy > h + alto_px:
            return
        detalle_completo = alto_px >= LOD_ALTURA_MIN_PX

        bob = abs(math.sin(walk_phase)) * 0.12
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
            scale=0.92,
            outline=(18, 22, 28),
        )

        if not detalle_completo:
            return  # lejos: solo cuerpo (el color sigue identificando persona/zombie/horda)

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

        for side, a_pitch in [(-0.31, arm_l_pitch), (0.31, arm_r_pitch)]:
            shoulder_pos = local_to_world(side, 1.18, 0.0)
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
                scale=0.88,
            )

        for side, l_pitch in [(-0.14, leg_swing), (0.14, -leg_swing)]:
            hip_pos = local_to_world(side, 0.58, 0.0)
            self._queue_mesh(
                draw_list,
                self.limb_mesh,
                hip_pos,
                (38, 46, 60),
                eye,
                right,
                up,
                forward,
                w,
                h,
                yaw=yaw,
                pitch=l_pitch,
                scale=0.92,
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
                    limb_color=(210, 225, 245),
                    is_zombie=False,
                    bite_timer=0.0,
                    eye=eye,
                    right=right,
                    up=up,
                    forward=forward,
                    w=w,
                    h=h,
                )
            elif isinstance(agent, ZombieAgent):
                self._queue_articulated_character(
                    draw_list,
                    agent.position,
                    agent.yaw,
                    agent.walk_phase,
                    # Zombies de la horda: naranja si están emboscando, amarillo si fueron avisados
                    # y se lanzaron desde la emboscada; color normal en patrulla/persecución propia.
                    body_color=(255, 150, 40) if agent.emboscada is not None
                    else (255, 225, 70) if agent.desde_emboscada else agent.color,
                    limb_color=(95, 185, 95) if not agent.is_converted else (205, 70, 90),
                    is_zombie=True,
                    bite_timer=agent.bite_anim_timer,
                    eye=eye,
                    right=right,
                    up=up,
                    forward=forward,
                    w=w,
                    h=h,
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
                if beam.content == "presa_detectada":
                    col = (255, 175, 70)   # INFORM de caza coordinada entre zombies
                elif beam.performative == Performative.ALERT:
                    col = (255, 85, 85)
                else:
                    col = (95, 215, 255)
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
