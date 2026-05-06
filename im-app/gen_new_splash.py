"""Splash — matching ideal icon: wide white border, small blue circle, slim lightning"""
from PIL import Image, ImageDraw, ImageFont

FONT_PATH = "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc"

def draw_icon_crisp(target_size):
    s = target_size * 4
    img = Image.new('RGBA', (s,s), (0,0,0,0))
    d = ImageDraw.Draw(img)
    corner = int(s * 0.30)
    # White squircle
    d.rounded_rectangle([0,0,s,s], radius=corner, fill=(255,255,255,255))
    # Blue circle — 60% of area, centered
    cd = int(s * 0.60)
    m = (s-cd)//2
    d.ellipse([m,m,m+cd,m+cd], fill=(0,98,235,255))
    # Slim lightning — 82% of circle
    ba = int(cd * 0.82)
    bm = (cd-ba)//2
    pts = [(13,2),(3,14),(12,14),(11,22),(21,10),(12,10)]
    sx = ba/24; sy = ba/24
    d.polygon([(m+bm+p[0]*sx,m+bm+p[1]*sy) for p in pts], fill=(255,255,255,255))
    return img.resize((target_size,target_size), Image.LANCZOS)

def draw_splash(w, h):
    img = Image.new('RGBA', (w,h), (255,255,255,255))
    d = ImageDraw.Draw(img)
    for y in range(h):
        r = int(245-(y/h)*20); g = int(248-(y/h)*15); b = 255
        d.line([(0,y),(w,y)], fill=(max(0,r),max(0,g),b))
    dia = int(w * 0.16); x = (w-dia)//2; y = int(h * 0.30)
    icon = draw_icon_crisp(dia)
    img.paste(icon, (x,y), icon)
    fs = max(int(w*0.05),18)
    font = ImageFont.truetype(FONT_PATH,fs) if FONT_PATH else ImageFont.load_default()
    bbox = d.textbbox((0,0),"清云",font=font)
    tx = (w-(bbox[2]-bbox[0]))//2; ty = y+dia+int(dia*0.20)
    so = max(int(fs*0.015),1)
    d.text((tx+so,ty+so),"清云",fill=(0,98,235,25),font=font)
    d.text((tx,ty),"清云",fill=(255,255,255,255),font=font)
    return img

D = {'mdpi':(480,800),'hdpi':(720,1280),'xhdpi':(960,1600),'xxhdpi':(1440,2400),'xxxhdpi':(1920,3200)}
L = {'mdpi':(800,480),'hdpi':(1280,720),'xhdpi':(1600,960),'xxhdpi':(2400,1440),'xxxhdpi':(3200,1920)}
B = '/root/webui/capacitor/android/app/src/main/res'
for k,v in D.items():
    img = draw_splash(*v)
    for p in [f'drawable-{k}/splash.png',f'drawable-port-{k}/splash.png]: img.save(f'{B}/{p}','PNG')
    if k=='mdpi': img.save(f'{B}/drawable/splash.png','PNG')
for k,v in L.items(): draw_splash(*v).save(f'{B}/drawable-land-{k}/splash.png','PNG')
draw_splash(1920,3200).save('/root/webui/static/splash_preview_hd.png','PNG')
print('Done!')
