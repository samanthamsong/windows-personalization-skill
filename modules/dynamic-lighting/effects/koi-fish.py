import os
import subprocess, json, time, threading, sys, math
from PIL import Image, ImageDraw, ImageFont

EXE = os.path.join(os.path.expanduser('~'), 'DLDriverBin', 'DynamicLightingDriver.exe')
OUT_DIR = os.path.dirname(os.path.abspath(__file__))

proc = subprocess.Popen([EXE], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
threading.Thread(target=lambda: [proc.stderr.readline() for _ in iter(int,1)], daemon=True).start()

def send(cmd):
    proc.stdin.write((cmd + '\n').encode())
    proc.stdin.flush()
def recv():
    return proc.stdout.readline().decode().strip()

# Wait for driver ready
ready = recv()
assert ready == 'READY', f'Driver not ready: {ready}'

# Tell the driver which effect is running
send("SET_EFFECT_NAME Koi Fish Pond")
recv()

# === KOI FISH POND EFFECT ===
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

# Colors
POND_DEEP   = (8, 25, 60)
POND_MID    = (15, 45, 90)
POND_LIGHT  = (25, 65, 110)
RIPPLE      = (40, 90, 140)
KOI_ORANGE  = (255, 120, 15)
KOI_WHITE   = (240, 235, 220)
KOI_RED     = (220, 40, 30)
KOI_GOLD    = (255, 180, 30)
LILY_GREEN  = (30, 110, 45)
LILY_PINK   = (220, 100, 130)

# Lily pad positions (fixed)
lily_pads = [(0.15, 0.12), (0.75, 0.25), (0.45, 0.75), (0.88, 0.65), (0.25, 0.55)]

def lerp(c1, c2, t):
    t = max(0, min(1, t))
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))

def render_frame(t):
    """Render one frame of koi pond at time t."""
    # Fish swims back and forth with slight vertical wave
    cycle = t * 0.15  # slow swim
    fish_x = 0.5 + 0.4 * math.sin(cycle * math.pi * 2)
    fish_y = 0.45 + 0.15 * math.sin(cycle * math.pi * 2 * 0.7 + 1.0)
    fish_dir = math.cos(cycle * math.pi * 2)  # +1 = right, -1 = left

    colors = {}
    for lamp in lamps:
        lx, ly = lamp['x'], lamp['y']

        # --- Pond water base with subtle ripples ---
        ripple1 = math.sin(lx * 8 + t * 1.2) * math.sin(ly * 6 + t * 0.8) * 0.5 + 0.5
        ripple2 = math.sin(lx * 5 - t * 0.9 + ly * 4) * 0.5 + 0.5
        water = lerp(POND_DEEP, POND_MID, ripple1 * 0.4)
        water = lerp(water, POND_LIGHT, ripple2 * 0.2)

        # Caustic shimmer near water surface (top rows)
        if ly < 0.3:
            caustic = math.sin(lx * 12 + t * 2.5) * math.sin(t * 1.8 + lx * 7) * 0.5 + 0.5
            water = lerp(water, RIPPLE, caustic * 0.3 * (1 - ly / 0.3))

        color = water

        # --- Lily pads ---
        for plx, ply in lily_pads:
            dx = lx - plx
            dy = ly - ply
            dist = math.sqrt(dx*dx + dy*dy)
            if dist < 0.07:
                color = LILY_GREEN
                # Pink flower at center of some pads
                if dist < 0.03 and (plx + ply) * 10 % 2 < 1:
                    color = LILY_PINK

        # --- Koi fish ---
        # Fish body is an ellipse oriented in swim direction
        dx = lx - fish_x
        dy = ly - fish_y

        # Rotate into fish-local space based on direction
        if fish_dir < 0:
            dx = -dx  # flip when swimming left

        # Body ellipse (wider than tall)
        body_dist = math.sqrt((dx * 3.5)**2 + (dy * 7)**2)

        if body_dist < 1.0:
            # Inside fish body
            if dx > 0.06:
                # Head - orange/gold
                head_blend = min((dx - 0.06) / 0.08, 1.0)
                color = lerp(KOI_ORANGE, KOI_GOLD, head_blend * 0.5)
            elif dx > -0.02:
                # Upper body - white with orange patches
                patch = math.sin(dx * 40 + dy * 25) * 0.5 + 0.5
                if patch > 0.5:
                    color = KOI_ORANGE
                else:
                    color = KOI_WHITE
            elif dx > -0.08:
                # Mid body - red/orange patches on white
                patch = math.sin(dx * 30 + dy * 20 + 2) * 0.5 + 0.5
                if patch > 0.6:
                    color = KOI_RED
                else:
                    color = KOI_WHITE
            else:
                # Tail - tapers, orange fading to translucent
                tail_t = min((-dx - 0.08) / 0.08, 1.0)
                # Tail wag
                wag = math.sin(t * 4 + dx * 20) * 0.03
                tail_dy = abs(ly - (fish_y + wag))
                if tail_dy < 0.08 * (1 - tail_t * 0.5):
                    color = lerp(KOI_ORANGE, KOI_RED, tail_t)
                else:
                    # Outside tail fin
                    pass

            # Eye
            eye_x = fish_x + (0.1 if fish_dir >= 0 else -0.1)
            eye_y = fish_y - 0.02
            eye_dist = math.sqrt((lx - eye_x)**2 + (ly - eye_y)**2)
            if eye_dist < 0.02:
                color = (10, 10, 10)

        # Shimmer/caustics near the fish
        elif body_dist < 1.8:
            shimmer_t = (1.8 - body_dist) / 0.8
            shimmer = math.sin(lx * 15 + t * 3) * 0.5 + 0.5
            color = lerp(color, RIPPLE, shimmer * shimmer_t * 0.25)

        colors[str(lamp['idx'])] = '#{:02x}{:02x}{:02x}'.format(*color)

    return colors

# === GENERATE VISUALIZATION (4 snapshots) ===
key_w, key_h = 52, 42
gap = 4
margin = 25
label_h = 22
snapshots = [0.0, 2.0, 4.5, 7.0]

total_w = 15 * (key_w + gap) + margin * 2
single_h = len(rows) * (key_h + gap) + label_h + 8
total_h = len(snapshots) * single_h + margin * 2

img = Image.new('RGB', (total_w, total_h), (5, 15, 35))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("consola.ttf", 11)
    title_font = ImageFont.truetype("consola.ttf", 13)
except:
    font = ImageFont.load_default()
    title_font = font

draw.text((margin, 6), "Koi Fish Pond  -  4 animation snapshots", fill=(180, 200, 220), font=title_font)

for si, t in enumerate(snapshots):
    frame_colors = render_frame(t)
    y_off = margin + 14 + si * single_h
    draw.text((margin, y_off), f"t = {t:.1f}s", fill=(150, 170, 200), font=title_font)
    y_off += label_h

    idx = 0
    for ri, count in enumerate(rows):
        for ci in range(count):
            lamp = lamps[idx]
            hx = frame_colors[str(idx)]
            cr, cg, cb = int(hx[1:3],16), int(hx[3:5],16), int(hx[5:7],16)
            px = int(margin + (row_offsets[ri] + ci * row_kw[ri]) / 15.0 * (total_w - margin*2))
            py = y_off + ri * (key_h + gap)
            draw.rounded_rectangle([px, py, px+key_w-2, py+key_h-2], radius=4, fill=(cr,cg,cb), outline=(40,50,70))
            label = lamp['label']
            if label:
                lum = cr*0.299 + cg*0.587 + cb*0.114
                tc = (0,0,0) if lum > 128 else (140,160,180)
                bbox = draw.textbbox((0,0), label, font=font)
                tw, th = bbox[2]-bbox[0], bbox[3]-bbox[1]
                draw.text((px+(key_w-2-tw)//2, py+(key_h-2-th)//2), label, fill=tc, font=font)
            idx += 1

img_path = f"{OUT_DIR}\\_koi_viz.png"
img.save(img_path)
print(f"Visualization saved to: {img_path}")

# === RUN ANIMATION LOOP ===
print("Starting koi fish animation (~8fps)...")
sys.stdout.flush()

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame = 0
start = time.time()
while True:
    # Check for alert override — flash the requested color, then resume
    if os.path.exists(PAUSE_FILE):
        try:
            with open(PAUSE_FILE, 'r') as f:
                alert_data = f.read().strip()
            # Parse color and duration from pause file (format: "#FF69B4|3")
            parts = alert_data.split('|')
            flash_color = parts[0] if parts[0].startswith('#') else '#FF69B4'
            flash_duration = float(parts[1]) if len(parts) > 1 else 3.0

            # Flash using OUR driver connection (which already has the device)
            all_pink = {str(lamp['idx']): flash_color for lamp in lamps}
            flash_start = time.time()
            while time.time() - flash_start < flash_duration:
                send(f"SET_LAMPS {json.dumps(all_pink)}")
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
    # ~8 fps
    elapsed = time.time() - start
    target = frame / 8.0
    if target > elapsed:
        time.sleep(target - elapsed)
