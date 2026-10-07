import base64

def uri(p):
    return 'data:image/png;base64,' + base64.b64encode(open(p, 'rb').read()).decode()

h = open('ucapan.html', encoding='utf-8').read()
for k in ['bunga4', 'bunga7']:
    h = h.replace(f"{k}:'{k}.png'", f"{k}:'{uri(k + '.png')}'")
open('ucapan_embed.html', 'w', encoding='utf-8').write(h)
print('Selesai: ucapan_embed.html')