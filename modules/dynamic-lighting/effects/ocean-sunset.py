import os, subprocess, json, time, threading, sys, math, random
from PIL import Image, ImageDraw, ImageFont

# Launch lighting driver
EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingDriver', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int, 1)], daemon=True).start()

def send(cmd):
    proc.stdin.write((cmd + '\n').encode())
    proc.stdin.flush()
def recv():
    return proc.stdout.readline().decode().strip()

# Wait for driver ready
ready = recv()
assert ready == 'READY', f'Driver not ready: {ready}'

# === OCEAN SUNSET EFFECT ===
# 87-key TKL layout
rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_kw = [1, 1, 1, 1, 1, 1.5, 1]

key_labels = [
    "Esc","","F1","F2","F3","F4","","F5","F6","F7","F8","","F9","F10","F11",
    "`","1","2","3","4","5","6","7","8","9","0","-","=","Bks","Ins",
    "Tab","Q","W","E","R","T","Y","U","I","O","P","[","]","\\","Del",
    "Cap","A","S","D","F","G","H","J","K","L",";","'","Ent","PgU",
    "Shf","Z","X","C","V","B","N","M",",",".","/","Shf","Up",
    "Ctl","Win","Alt","Spc","Spc","Alt","Fn","Ctl",
    "","","Lft","Dn","Rt","",""
]

lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        x = (row_offsets[ri] + ci * row_kw[ri]) / 15.0
        y = ri / 6.0
        lamps.append({"idx": idx, "x": x, "y": y, "label": key_labels[idx] if idx < len(key_labels) else "", "row": ri, "col": ci})
        idx += 1

# Palette — base colors (blended by sun_progress for time-varying sky)
# Early sky (sun high) — bright, warm pastels
EARLY_SKY_TOP    = (80, 50, 120)    # soft lavender
EARLY_SKY_MID    = (200, 120, 140)  # warm pink
EARLY_SKY_LOW    = (240, 170, 90)   # bright peach-orange
EARLY_HORIZON    = (255, 210, 130)  # bright gold horizon

# Mid sky (sun halfway) — fiery reds and oranges
MID_SKY_TOP      = (60, 20, 70)     # darkening purple
MID_SKY_MID      = (200, 60, 70)    # vivid red-pink
MID_SKY_LOW      = (240, 100, 40)   # deep orange
MID_HORIZON      = (255, 170, 50)   # rich gold

# Late sky (sun at horizon) — deep twilight purples
LATE_SKY_TOP     = (12, 5, 25)      # near-black purple
LATE_SKY_MID     = (60, 15, 45)     # dark magenta
LATE_SKY_LOW     = (140, 35, 35)    # dusky red
LATE_HORIZON     = (200, 90, 40)    # dim amber

SUN_CORE     = (255, 255, 230)  # blazing white-gold sun center
SUN_INNER    = (255, 200, 100)  # bright inner ring
SUN_GLOW     = (255, 140, 50)   # orange sun glow
SUN_EDGE     = (240, 70, 45)    # reddish outer glow
OCEAN_DEEP   = (4, 8, 28)      # very deep ocean
OCEAN_MID    = (8, 18, 45)     # mid ocean
OCEAN_SURF   = (14, 30, 60)    # ocean surface
REFLECT_CORE = (255, 210, 120) # bright golden reflection directly under sun
REFLECT_GOLD = (220, 150, 55)  # golden sun reflection on water
REFLECT_PINK = (180, 70, 80)   # pink reflection shimmer

def lerp(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def smoothstep(edge0, edge1, x):
    t = max(0, min(1, (x - edge0) / (edge1 - edge0)))
    return t * t * (3 - 2 * t)

def sky_color_at(sky_t, p):
    """Get sky color at vertical position sky_t (0=top, 1=horizon) for sun progress p (0=high, 1=set)."""
    # Interpolate between early/mid/late sky palettes based on sun progress
    if p < 0.5:
        pp = p / 0.5
        top = lerp(EARLY_SKY_TOP, MID_SKY_TOP, pp)
        mid = lerp(EARLY_SKY_MID, MID_SKY_MID, pp)
        low = lerp(EARLY_SKY_LOW, MID_SKY_LOW, pp)
        hor = lerp(EARLY_HORIZON, MID_HORIZON, pp)
    else:
        pp = (p - 0.5) / 0.5
        top = lerp(MID_SKY_TOP, LATE_SKY_TOP, pp)
        mid = lerp(MID_SKY_MID, LATE_SKY_MID, pp)
        low = lerp(MID_SKY_LOW, LATE_SKY_LOW, pp)
        hor = lerp(MID_HORIZON, LATE_HORIZON, pp)

    if sky_t < 0.33:
        return lerp(top, mid, sky_t / 0.33)
    elif sky_t < 0.66:
        return lerp(mid, low, (sky_t - 0.33) / 0.33)
    else:
        return lerp(low, hor, (sky_t - 0.66) / 0.34)

# Sun descends over ~30 seconds then resets
CYCLE_DURATION = 30.0

def render_frame(t):
    """Render one frame of ocean sunset at time t."""
    cycle = (t % CYCLE_DURATION) / CYCLE_DURATION
    sun_progress = smoothstep(0.0, 1.0, cycle)
    sun_x = 0.5 + 0.03 * math.sin(t * 0.15)
    sun_y = 0.0 + sun_progress * 0.55  # descends from very top to horizon

    horizon = 0.55

    # Ocean also darkens as sun sets
    ocean_brightness = 1.0 - sun_progress * 0.5

    colors = {}
    for lamp in lamps:
        lx, ly = lamp['x'], lamp['y']

        dx = lx - sun_x
        dy = ly - sun_y
        sun_dist = math.sqrt(dx * dx + dy * dy)

        if ly < horizon:
            # === SKY — colors shift with sun_progress ===
            sky_t = ly / horizon

            color = sky_color_at(sky_t, sun_progress)

            # Sun glow — large, bright, unmistakable orb
            if sun_dist < 0.65:
                glow_t = 1.0 - (sun_dist / 0.65)
                glow_t = glow_t ** 1.2

                if sun_dist < 0.10:
                    core_t = 1.0 - (sun_dist / 0.10)
                    color = lerp(SUN_INNER, SUN_CORE, core_t ** 0.4)
                elif sun_dist < 0.20:
                    inner_t = (sun_dist - 0.10) / 0.10
                    color = lerp(SUN_INNER, SUN_GLOW, inner_t)
                elif sun_dist < 0.35:
                    mid_t = (sun_dist - 0.20) / 0.15
                    glow_color = lerp(SUN_GLOW, SUN_EDGE, mid_t * 0.7)
                    color = lerp(color, glow_color, 0.85 - mid_t * 0.3)
                else:
                    color = lerp(color, SUN_EDGE, glow_t * 0.55)

            # Subtle cloud wisps — more vivid as sun gets lower
            cloud = math.sin(lx * 10 + ly * 3 + t * 0.3) * math.cos(lx * 7 - t * 0.2) * 0.5 + 0.5
            if cloud > 0.65 and sky_t > 0.15 and sky_t < 0.75:
                cloud_intensity = (cloud - 0.65) / 0.35
                cloud_color = lerp(MID_SKY_MID, MID_HORIZON, sky_t)
                color = lerp(color, cloud_color, cloud_intensity * 0.3 * (0.5 + sun_progress * 0.5))

        else:
            # === OCEAN — also shifts as sun sets ===
            ocean_depth = (ly - horizon) / (1.0 - horizon)

            # Ocean darkens as sun sets
            surf = lerp(OCEAN_SURF, (8, 20, 40), sun_progress * 0.6)
            mid = lerp(OCEAN_MID, (4, 10, 30), sun_progress * 0.5)
            deep = lerp(OCEAN_DEEP, (2, 4, 15), sun_progress * 0.4)

            if ocean_depth < 0.3:
                color = lerp(surf, mid, ocean_depth / 0.3)
            else:
                color = lerp(mid, deep, (ocean_depth - 0.3) / 0.7)

            # Wave ripples
            wave1 = math.sin(lx * 12 + t * 1.5 + ocean_depth * 4) * 0.5 + 0.5
            wave2 = math.sin(lx * 8 - t * 1.1 + ly * 6) * 0.5 + 0.5
            wave_blend = wave1 * 0.3 + wave2 * 0.2
            color = lerp(color, OCEAN_SURF, wave_blend * (1 - ocean_depth * 0.6))

            # Sun reflection column — bright golden path on water below the sun
            reflect_dx = abs(lx - sun_x)
            # Reflection widens with depth, much wider than before
            reflect_width = 0.10 + ocean_depth * 0.18
            if reflect_dx < reflect_width:
                reflect_intensity = 1.0 - (reflect_dx / reflect_width)
                reflect_intensity = reflect_intensity ** 1.2
                # Stronger near surface, fades with depth
                depth_fade = 1.0 - ocean_depth * 0.5
                # Shimmer animation
                shimmer = math.sin(lx * 20 + t * 3.0 + ly * 8) * 0.25 + 0.75
                # Near center of reflection, use bright core color
                if reflect_dx < reflect_width * 0.35 and ocean_depth < 0.4:
                    reflect_color = lerp(REFLECT_CORE, REFLECT_GOLD, ocean_depth)
                else:
                    reflect_color = lerp(REFLECT_GOLD, REFLECT_PINK, ocean_depth * 0.6)
                color = lerp(color, reflect_color, reflect_intensity * depth_fade * shimmer * 0.9)

            # Sparkle glints on wave crests
            sparkle = math.sin(lx * 25 + t * 4.0) * math.sin(ly * 18 - t * 2.5)
            if sparkle > 0.85 and ocean_depth < 0.25:
                glint_t = (sparkle - 0.85) / 0.15
                color = lerp(color, HORIZON_GOLD, glint_t * 0.6)

        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)

    return colors

# === GENERATE VISUALIZATION (4 snapshots) ===
key_w, key_h = 52, 42
gap = 4
margin = 25
label_h = 22
snapshots = [0.0, 8.0, 18.0, 27.0]

total_w = 15 * (key_w + gap) + margin * 2
single_h = len(rows) * (key_h + gap) + label_h + 8
total_h = len(snapshots) * single_h + margin * 2

img = Image.new('RGB', (total_w, total_h), (5, 10, 25))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("consola.ttf", 11)
    title_font = ImageFont.truetype("consola.ttf", 13)
except:
    font = ImageFont.load_default()
    title_font = font

draw.text((margin, 6), "Ocean Sunset  -  4 animation snapshots", fill=(220, 180, 140), font=title_font)

for si, t in enumerate(snapshots):
    frame_colors = render_frame(t)
    y_off = margin + 14 + si * single_h
    draw.text((margin, y_off), f"t = {t:.1f}s", fill=(200, 160, 120), font=title_font)
    y_off += label_h

    idx = 0
    for ri, count in enumerate(rows):
        for ci in range(count):
            lamp = lamps[idx]
            hx = frame_colors[str(idx)]
            cr, cg, cb = int(hx[1:3], 16), int(hx[3:5], 16), int(hx[5:7], 16)
            px = int(margin + (row_offsets[ri] + ci * row_kw[ri]) / 15.0 * (total_w - margin * 2))
            py = y_off + ri * (key_h + gap)
            draw.rounded_rectangle([px, py, px + key_w - 2, py + key_h - 2], radius=4, fill=(cr, cg, cb), outline=(40, 50, 70))
            label = lamp['label']
            if label:
                lum = cr * 0.299 + cg * 0.587 + cb * 0.114
                tc = (0, 0, 0) if lum > 128 else (200, 190, 170)
                bbox = draw.textbbox((0, 0), label, font=font)
                tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
                draw.text((px + (key_w - 2 - tw) // 2, py + (key_h - 2 - th) // 2), label, fill=tc, font=font)
            idx += 1

img_path = f"{OUT_DIR}\\_ocean_sunset_viz.png"
img.save(img_path)
print(f"Visualization saved to: {img_path}")

# === RUN ANIMATION LOOP ===
print("Starting ocean sunset animation (~8fps)...")
sys.stdout.flush()

# Alert flash coordination — DO NOT REMOVE
PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame = 0
start = time.time()
while True:
    # Check for notification flash override
    if os.path.exists(PAUSE_FILE):
        try:
            with open(PAUSE_FILE, 'r') as f:
                alert_data = f.read().strip()
            parts = alert_data.split('|')
            flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
            flash_duration = float(parts[1]) if len(parts) > 1 else 3.0
            all_flash = {str(lamp['idx']): flash_color for lamp in lamps}
            flash_start = time.time()
            while time.time() - flash_start < flash_duration:
                send(f"SET_LAMPS {json.dumps(all_flash)}")
                recv()
                frame += 1
                time.sleep(0.125)
        except Exception as e:
            print(f"Alert flash error: {e}")
        finally:
            try:
                os.remove(PAUSE_FILE)
            except Exception:
                pass
        continue

    t = time.time() - start
    colors = render_frame(t)
    send(f"SET_LAMPS {json.dumps(colors)}")
    recv()
    frame += 1
    elapsed = time.time() - start
    target = frame / 8.0
    if target > elapsed:
        time.sleep(target - elapsed)
