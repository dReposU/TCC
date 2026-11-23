"""
Punto de entrada principal de la simulación 3D: Invasión Zombie en la Universidad.
Edificio de 8 pisos, 4 aulas por piso, 3 salidas de emergencia por piso.
Simula N personas y M zombies y determina cuántos se salvan y cuántos se infectan.
"""
import os
import sys
import pygame

from agents.acl import AgentPlatform
from agents.host_agent import HostAgent
from graphics.engine3d import Renderer3D
from graphics.hud import SimulationHUD
from world.university import UniversityBuilding


def load_sounds(assets_dir: str) -> dict:
    sounds = {}
    if not pygame.mixer.get_init():
        return sounds
    mapping = {
        "alarm_start": "alarm_start.wav",
        "alert_bite": "alert_bite.wav",
        "escape_safe": "escape_safe.wav",
        "radio_report": "radio_report.wav",
    }
    for key, fn in mapping.items():
        path = os.path.join(assets_dir, "sounds", fn)
        if os.path.exists(path):
            try:
                sounds[key] = pygame.mixer.Sound(path)
            except Exception:
                pass
    return sounds


def main() -> None:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    assets_dir = os.path.join(base_dir, "assets")

    pygame.init()
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1)
    except Exception:
        pass

    screen = pygame.display.set_mode((1320, 780), pygame.RESIZABLE)
    pygame.display.set_caption("Práctica Multi-Agente 3D · Invasión Zombie en la Universidad (8 Pisos)")

    icon_path = os.path.join(assets_dir, "textures", "biohazard_icon.png")
    if os.path.exists(icon_path):
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception:
            pass

    clock = pygame.time.Clock()
    sounds = load_sounds(assets_dir)

    num_personas = 32
    num_zombies = 12

    building = UniversityBuilding()
    platform = AgentPlatform(building)
    host = HostAgent("Host", num_personas=num_personas, num_zombies=num_zombies)
    platform.register_agent(host)

    renderer = Renderer3D(assets_dir, building)
    hud = SimulationHUD(assets_dir)

    sim_speed = 1.0
    paused = False
    muted = False
    dragging = False
    last_mouse = (0, 0)

    def restart_simulation() -> None:
        nonlocal building, host
        building = UniversityBuilding()
        platform.reset(building)
        host = HostAgent("Host", num_personas=num_personas, num_zombies=num_zombies)
        platform.register_agent(host)

    running = True
    speed = 1.0
    while running:
        real_dt = min(0.05, clock.tick(60) / 1000.0)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.VIDEORESIZE:
                screen = pygame.display.set_mode((event.w, event.h), pygame.RESIZABLE)
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    dragging = True
                    last_mouse = event.pos
                elif event.button == 4:
                    renderer.camera.desired_distance = max(16.0, renderer.camera.desired_distance - 4.5)
                elif event.button == 5:
                    renderer.camera.desired_distance = min(115.0, renderer.camera.desired_distance + 4.5)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                last_mouse = event.pos
                renderer.camera.yaw -= dx * 0.0065
                renderer.camera.pitch = max(0.06, min(1.38, renderer.camera.pitch + dy * 0.0065))
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    sim_speed = min(5.0, round(sim_speed + 0.5, 1))
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    sim_speed = max(0.5, round(sim_speed - 0.5, 1))
                elif event.key == pygame.K_m:
                    muted = not muted
                elif event.key == pygame.K_r:
                    restart_simulation()
                elif event.key == pygame.K_q:
                    num_personas = max(4, num_personas - 4)
                    restart_simulation()
                elif event.key == pygame.K_w:
                    num_personas = min(120, num_personas + 4)
                    restart_simulation()
                elif event.key == pygame.K_a:
                    num_zombies = max(1, num_zombies - 2)
                    restart_simulation()
                elif event.key == pygame.K_s:
                    num_zombies = min(60, num_zombies + 2)
                    restart_simulation()
                elif event.key == pygame.K_0:
                    renderer.camera.focus_all_floors()
                elif pygame.K_1 <= event.key <= pygame.K_8:
                    renderer.camera.focus_floor(event.key - pygame.K_1)

        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            renderer.camera.yaw -= 1.4 * real_dt
        if keys[pygame.K_RIGHT]:
            renderer.camera.yaw += 1.4 * real_dt
        if keys[pygame.K_UP]:
            renderer.camera.pitch = min(1.38, renderer.camera.pitch + 1.1 * real_dt)
        if keys[pygame.K_DOWN]:
            renderer.camera.pitch = max(0.06, renderer.camera.pitch - 1.1 * real_dt)

        if not paused:
            platform.step(real_dt * speed)

        if platform.sound_events:
            if not muted:
                for sk in platform.sound_events:
                    snd = sounds.get(sk)
                    if snd is not None:
                        snd.play()
            platform.sound_events.clear()

        renderer.camera.update(real_dt)
        renderer.render(screen, platform, platform.sim_time)
        hud.render(screen, platform, renderer.camera, num_personas, num_zombies, sim_speed, paused, muted)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
