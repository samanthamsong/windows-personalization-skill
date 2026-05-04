import math
import random
from _runner import EffectRunner, lerp, hex_color

runner = EffectRunner("Starlight")

# Stars: each has a position, twinkle speed, brightness phase, and color warmth
NUM_STARS = 30
stars = [
    {
        "x": random.random(),
        "y": random.random(),
        "speed": random.uniform(1.5, 4.0),
        "phase": random.random() * math.tau,
        "radius": random.uniform(0.08, 0.22),
        "warm": random.random(),  # 0 = cool lavender, 1 = warm gold
    }
    for _ in range(NUM_STARS)
]

# Slow-drifting shooting stars
NUM_STREAKS = 3
streaks = [
    {
        "start_x": random.random(),
        "start_y": random.uniform(0.0, 0.4),
        "angle": random.uniform(-0.3, 0.3),
        "speed": random.uniform(0.6, 1.2),
        "period": random.uniform(8.0, 15.0),
        "offset": random.random() * 20,
        "length": random.uniform(0.15, 0.3),
    }
    for _ in range(NUM_STREAKS)
]

# Night sky palette
SKY_DEEP = (26, 26, 62)       # #1A1A3E
SKY_MID = (44, 44, 84)        # #2C2C54
LAVENDER = (184, 169, 212)     # #B8A9D4
SOFT_WHITE = (240, 230, 255)   # #F0E6FF
WARM_GOLD = (232, 213, 183)    # #E8D5B7
PURPLE = (107, 91, 149)        # #6B5B95


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx, ly = lamp["x"], lamp["y"]

        # Base: deep night sky with subtle vertical gradient
        grad = ly * 0.3
        r = SKY_DEEP[0] + (SKY_MID[0] - SKY_DEEP[0]) * grad
        g = SKY_DEEP[1] + (SKY_MID[1] - SKY_DEEP[1]) * grad
        b = SKY_DEEP[2] + (SKY_MID[2] - SKY_DEEP[2]) * grad

        # Twinkling stars
        for star in stars:
            dx = lx - star["x"]
            dy = ly - star["y"]
            dist = math.sqrt(dx * dx + dy * dy)
            if dist < star["radius"]:
                brightness = (math.sin(t * star["speed"] + star["phase"]) + 1) * 0.5
                brightness *= 1.0 - (dist / star["radius"])
                brightness = brightness ** 1.5  # sharpen falloff

                # Blend between lavender and warm gold
                w = star["warm"]
                star_color = lerp(LAVENDER, WARM_GOLD, w)

                # Occasional bright flash (full white)
                flash = max(0, math.sin(t * star["speed"] * 2.3 + star["phase"] * 3) - 0.85) / 0.15
                star_color = lerp(star_color, SOFT_WHITE, flash * 0.6)

                base = (r, g, b)
                blended = lerp(base, star_color, brightness * 0.9)
                r, g, b = blended

        # Shooting streaks
        for streak in streaks:
            cycle = (t + streak["offset"]) % streak["period"]
            if cycle < 1.5:
                progress = cycle / 1.5
                head_x = streak["start_x"] + progress * 0.8
                head_y = streak["start_y"] + math.sin(streak["angle"]) * progress * 0.3
                tail_x = head_x - streak["length"]

                # Distance from lamp to streak line
                if tail_x <= lx <= head_x:
                    along = (lx - tail_x) / max(streak["length"], 0.01)
                    perp = abs(ly - head_y)
                    if perp < 0.08:
                        intensity = along * (1.0 - perp / 0.08) * (1.0 - progress * 0.5)
                        blended = lerp((r, g, b), SOFT_WHITE, intensity * 0.8)
                        r, g, b = blended

        # Gentle purple nebula glow that drifts slowly
        nebula_x = 0.5 + math.sin(t * 0.15) * 0.3
        nebula_y = 0.5 + math.cos(t * 0.12) * 0.3
        nd = math.sqrt((lx - nebula_x) ** 2 + (ly - nebula_y) ** 2)
        if nd < 0.4:
            nebula_strength = (1.0 - nd / 0.4) * 0.2
            blended = lerp((r, g, b), PURPLE, nebula_strength)
            r, g, b = blended

        colors[str(lamp["idx"])] = hex_color(int(r), int(g), int(b))

    return colors


runner.run(render_frame, fps=8)
