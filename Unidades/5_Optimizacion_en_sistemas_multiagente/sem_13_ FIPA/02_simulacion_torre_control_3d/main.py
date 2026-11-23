"""
Punto de entrada principal de la simulación 3D de Torre de Control Multi-Agente.
Adapta HostAgent.java, TorreAgent.java y AvionAgent.java a Python con PyGame en 3D.
"""
import os
import sys
import pygame

from agents.acl import AgentPlatform
from agents.host_agent import HostAgent
from graphics.engine3d import Renderer3D
from graphics.hud import SimulationHUD


def load_sounds(assets_dir: str) -> dict:
    sounds = {}
    sound_files = {
        "radio_ping": "radio_ping.wav",
        "landing_accept": "landing_accept.wav",
        "landing_reject": "landing_reject.wav",
        "touchdown": "touchdown.wav",
    }
    if not pygame.mixer.get_init():
        return sounds
    for key, filename in sound_files.items():
        path = os.path.join(assets_dir, "sounds", filename)
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

    width, height = 1280, 760
    screen = pygame.display.set_mode((width, height), pygame.RESIZABLE)
    pygame.display.set_caption("Torre de Control 3D · Sistema Multi-Agente (JADE -> Python/PyGame)")

    icon_path = os.path.join(assets_dir, "textures", "radar_icon.png")
    if os.path.exists(icon_path):
        try:
            pygame.display.set_icon(pygame.image.load(icon_path))
        except Exception:
            pass

    clock = pygame.time.Clock()
    sounds = load_sounds(assets_dir)

    platform = AgentPlatform()
    host = HostAgent("Host", numero_aviones=10)
    platform.register_agent(host)

    renderer = Renderer3D(assets_dir)
    hud = SimulationHUD(assets_dir)

    sim_speed = 1.0
    paused = False
    muted = False
    dragging = False
    last_mouse = (0, 0)

    running = True
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
                elif event.button == 4:  # Rueda arriba (acercar)
                    renderer.camera.distance = max(14.0, renderer.camera.distance - 4.5)
                elif event.button == 5:  # Rueda abajo (alejar)
                    renderer.camera.distance = min(145.0, renderer.camera.distance + 4.5)
            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1:
                    dragging = False
            elif event.type == pygame.MOUSEMOTION and dragging:
                dx = event.pos[0] - last_mouse[0]
                dy = event.pos[1] - last_mouse[1]
                last_mouse = event.pos
                renderer.camera.yaw -= dx * 0.0065
                renderer.camera.pitch = max(0.08, min(1.42, renderer.camera.pitch + dy * 0.0065))
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    sim_speed = min(5.0, round(sim_speed + 0.5, 1))
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    sim_speed = max(0.5, round(sim_speed - 0.5, 1))
                elif event.key == pygame.K_n:
                    host.spawn_avion()
                elif event.key == pygame.K_m:
                    muted = not muted
                elif event.key == pygame.K_r:
                    platform.reset()
                    host = HostAgent("Host", numero_aviones=10)
                    platform.register_agent(host)
                elif event.key == pygame.K_1:
                    renderer.camera.set_mode(0)
                elif event.key == pygame.K_2:
                    renderer.camera.set_mode(1)
                elif event.key == pygame.K_3:
                    renderer.camera.set_mode(2)
                elif event.key == pygame.K_4:
                    renderer.camera.set_mode(3)

        # Control continuo de cámara con teclas de dirección
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            renderer.camera.yaw -= 1.4 * real_dt
        if keys[pygame.K_RIGHT]:
            renderer.camera.yaw += 1.4 * real_dt
        if keys[pygame.K_UP]:
            renderer.camera.pitch = min(1.42, renderer.camera.pitch + 1.1 * real_dt)
        if keys[pygame.K_DOWN]:
            renderer.camera.pitch = max(0.08, renderer.camera.pitch - 1.1 * real_dt)

        # Paso de simulación Multi-Agente
        if not paused:
            sim_dt = real_dt * sim_speed
            platform.step(sim_dt)

        # Reproducir efectos sonoros generados por mensajes ACL
        if platform.sound_events:
            if not muted:
                for snd_key in platform.sound_events:
                    snd = sounds.get(snd_key)
                    if snd is not None:
                        snd.play()
            platform.sound_events.clear()

        renderer.camera.update(real_dt, platform)
        renderer.render(screen, platform, platform.sim_time)
        hud.render(screen, platform, renderer.camera, sim_speed, paused, muted)
        pygame.display.flip()

    pygame.quit()
    sys.exit(0)


if __name__ == "__main__":
    main()
