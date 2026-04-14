import os
import subprocess, json, time, threading, sys, math
from PIL import Image, ImageDraw, ImageFont

EXE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'src', 'DynamicLightingDriver', 'bin', 'Debug', 'net9.0-windows10.0.26100.0', 'DynamicLightingDriver.exe')
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

# Get lamp layout
send("GET_LAYOUT")
resp = recv()
layout_json = resp[3:]  # strip "OK " prefix
print(layout_json[:500])

# Apply shooting star effect
effect_cmd = "CREATE_EFFECT shooting_star #050510 #88CCFF 1.0 shooting stars across keyboard"
send(effect_cmd)
resp = recv()
print("\n" + resp)

# === VISUALIZATION ===
# Simulate the shooting star algorithm at a few time snapshots
# to show what the effect looks like

# 87-key TKL layout: physical key positions (normalized 0-1)
key_labels = [
    # Row 0: F-keys (15 keys)
    "Esc","","F1","F2","F3","F4","","F5","F6","F7","F8","","F9","F10","F11",
    # Row 1: Numbers (15 keys)
    "` ","1","2","3","4","5","6","7","8","9","0","-","=","Bks","Ins",
    # Row 2: QWERTY (15 keys)
    "Tab","Q","W","E","R","T","Y","U","I","O","P","[","]","\\","Del",
    # Row 3: Home (14 keys)
    "Cap","A","S","D","F","G","H","J","K","L",";","'","Ent","PgU",
    # Row 4: Shift (13 keys)
    "Shf","Z","X","C","V","B","N","M",",",".","/","Shf","Up",
    # Row 5: Mods (8 keys)
    "Ctl","Win","Alt","Space","Space","Alt","Fn","Ctl",
    # Row 6: Arrows (7 keys)
    "","","Lft","Dn","Rt","",""
]

rows = [15, 15, 15, 14, 13, 8, 7]
row_offsets = [0, 0, 0.075, 0.12, 0.15, 0, 0.85]
row_key_widths = [1, 1, 1, 1, 1, 1.5, 1]

# Build normalized positions
lamps = []
idx = 0
for ri, count in enumerate(rows):
    for ci in range(count):
        kw = row_key_widths[ri]
        x = (row_offsets[ri] + ci * kw) / 15.0
        y = ri / (len(rows) - 1)
        label = key_labels[idx] if idx < len(key_labels) else ""
        lamps.append({"idx": idx, "x": x, "y": y, "label": label})
        idx += 1

# Simulate shooting star algorithm (matching EffectEngine.cs logic)
def shooting_star_color(lamp_x, lamp_y, elapsed, base_rgb, accent_rgb):
    star_slots = 6
    tail_length = 0.25
    head_glow = 0.04
    best_brightness = 0.0

    for i in range(star_slots):
        h1 = ((i * 73856093) ^ 19349663) & 0x7FFFFFFF
        h2 = ((i * 19349663) ^ 83492791) & 0x7FFFFFFF
        h3 = ((i * 83492791) ^ 73856093) & 0x7FFFFFFF

        star_y = (h1 % 1000) / 1000.0
        period = 2.0 + (h2 % 1000) / 250.0
        speed_var = 0.8 + (h3 % 1000) / 1000.0 * 0.6

        cycle_time = elapsed * speed_var / period
        phase = cycle_time - math.floor(cycle_time)
        star_x = 1.0 + tail_length - phase * (1.0 + tail_length + head_glow)

        dx = lamp_x - star_x
        dy = lamp_y - star_y
        y_proximity = math.exp(-dy * dy / 0.01)

        if y_proximity < 0.05:
            continue

        if -head_glow <= dx <= head_glow:
            head_intensity = 1.0 - abs(dx) / head_glow
            best_brightness = max(best_brightness, head_intensity * y_proximity)
        elif 0 < dx < tail_length:
            tail_intensity = 1.0 - dx / tail_length
            tail_intensity *= tail_intensity
            best_brightness = max(best_brightness, tail_intensity * y_proximity * 0.7)

    if best_brightness < 0.01:
        return base_rgb

    # Head is white/bright, tail is accent
    star_r = int(accent_rgb[0] + (255 - accent_rgb[0]) * best_brightness)
    star_g = int(accent_rgb[1] + (255 - accent_rgb[1]) * best_brightness)
    star_b = int(accent_rgb[2] + (255 - accent_rgb[2]) * best_brightness)
    
    blend = min(best_brightness * 1.5, 1.0)
    r = int(base_rgb[0] + (star_r - base_rgb[0]) * blend)
    g = int(base_rgb[1] + (star_g - base_rgb[1]) * blend)
    b = int(base_rgb[2] + (star_b - base_rgb[2]) * blend)
    return (min(r,255), min(g,255), min(b,255))

base_rgb = (5, 5, 16)
accent_rgb = (136, 204, 255)

# Render 4 snapshots at different times
snapshots = [0.5, 1.5, 2.8, 4.2]
key_w, key_h = 52, 42
gap = 4
margin = 20
label_h = 20

total_w = 15 * (key_w + gap) + margin * 2
single_h = len(rows) * (key_h + gap) + margin + label_h
total_h = len(snapshots) * single_h + margin

img = Image.new('RGB', (total_w, total_h), (20, 20, 30))
draw = ImageDraw.Draw(img)

try:
    font = ImageFont.truetype("consola.ttf", 11)
    title_font = ImageFont.truetype("consola.ttf", 13)
except:
    font = ImageFont.load_default()
    title_font = font

for si, t in enumerate(snapshots):
    y_off = si * single_h + margin
    draw.text((margin, y_off - 2), f"t = {t:.1f}s", fill=(200,200,200), font=title_font)
    y_off += label_h

    idx = 0
    for ri, count in enumerate(rows):
        for ci in range(count):
            lamp = lamps[idx]
            color = shooting_star_color(lamp['x'], lamp['y'], t, base_rgb, accent_rgb)
            
            # Physical position on image
            px = int(margin + (row_offsets[ri] + ci * row_key_widths[ri]) / 15.0 * (total_w - margin*2))
            py = y_off + ri * (key_h + gap)
            
            # Draw key
            draw.rounded_rectangle([px, py, px+key_w-2, py+key_h-2], radius=4, fill=color, outline=(60,60,70))
            
            # Label
            label = lamp['label']
            if label:
                lum = color[0]*0.299 + color[1]*0.587 + color[2]*0.114
                text_color = (0,0,0) if lum > 128 else (150,150,160)
                bbox = draw.textbbox((0,0), label, font=font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((px + (key_w-2-tw)//2, py + (key_h-2-th)//2), label, fill=text_color, font=font)
            
            idx += 1

img_path = f"{OUT_DIR}\\_shooting_stars_viz.png"
img.save(img_path)
print(f"\nVisualization saved to: {img_path}")
print(f"Shows {len(snapshots)} snapshots at times: {snapshots}")
print("Effect is running on keyboard!")
sys.stdout.flush()

PAUSE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'rules', '.pause')

frame = 0
try:
    while True:
        # Alert flash coordination — check for notification override
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
            # Resume the effect after flash
            send(effect_cmd)
            recv()
            continue
        if proc.poll() is not None:
            break
        time.sleep(0.25)
except KeyboardInterrupt:
    proc.terminate()
