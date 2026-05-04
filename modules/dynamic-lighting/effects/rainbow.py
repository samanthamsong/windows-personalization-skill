import math
import colorsys
from _runner import EffectRunner, hex_color

runner = EffectRunner("Rainbow")


def render_frame(device, t):
    colors = {}
    for lamp in device.lamps:
        lx = lamp["x"]
        # Hue shifts based on x position and time for a cycling rainbow
        hue = (lx + t * 0.15) % 1.0
        r, g, b = colorsys.hsv_to_rgb(hue, 1.0, 1.0)
        colors[str(lamp["idx"])] = hex_color(r * 255, g * 255, b * 255)
    return colors


runner.run(render_frame, fps=8)
