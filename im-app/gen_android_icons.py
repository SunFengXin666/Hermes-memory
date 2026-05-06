"""Generate app icons — plain blue circle + white lightning (no border)"""
from PIL import Image, ImageDraw

MIPMAP_DIR = '/root/webui/capacitor/android/app/src/main/res'
ICON_SIZES = {'mdpi': 48, 'hdpi': 72, 'xhdpi': 96, 'xxhdpi': 144, 'xxxhdpi': 192}

def draw_crisp(target, is_foreground=False):
    s = target * 4
    img = Image.new('RGBA', (s, s), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)

    if is_foreground:
        cd = int(s * 0.72)
        m = (s - cd) // 2
        draw.ellipse([m, m, m + cd, m + cd], fill=(0, 122, 255, 255))
        bm = int(cd * 0.22)
    else:
        draw.ellipse([0, 0, s, s], fill=(0, 122, 255, 255))
        bm = int(s * 0.20)

    pts = [(13, 2), (3, 14), (12, 14), (11, 22), (21, 10), (12, 10)]
    area = s if not is_foreground else cd
    offset = 0 if not is_foreground else m
    sx = (area - bm * 2) / 24
    sy = (area - bm * 2) / 24
    draw.polygon([(offset + bm + p[0] * sx, offset + bm + p[1] * sy) for p in pts],
                 fill=(255, 255, 255, 255))

    return img.resize((target, target), Image.LANCZOS)


for density, size in ICON_SIZES.items():
    icon = draw_crisp(size)
    for name in ['ic_launcher.png', 'ic_launcher_round.png']:
        icon.save(f'{MIPMAP_DIR}/mipmap-{density}/{name}', 'PNG')
    print(f'  Standard {density} ({size}x{size})')

for density, size in ICON_SIZES.items():
    draw_crisp(size, is_foreground=True).save(
        f'{MIPMAP_DIR}/mipmap-{density}/ic_launcher_foreground.png', 'PNG')
    print(f'  Foreground {density} ({size}x{size})')

# Adaptive background = white (foreground has the blue circle)
with open(f'{MIPMAP_DIR}/values/ic_launcher_background.xml', 'w') as f:
    f.write('<?xml version="1.0" encoding="utf-8"?>\n<resources>\n')
    f.write('    <color name="ic_launcher_background">#FFFFFF</color>\n')
    f.write('</resources>\n')
print('  Background: #FFFFFF')

# Web icons
draw_crisp(512, is_foreground=True).save('/root/webui/static/icon-512.png', 'PNG')
draw_crisp(192, is_foreground=True).save('/root/webui/static/icon-192.png', 'PNG')
print('  Web icons updated')
print('\nDone!')
