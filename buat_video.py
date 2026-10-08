#!/usr/bin/env python3
"""
buat_video.py — merekam undangan (index -> pembukaan -> namapengantin -> cerita -> gif -> map)
menjadi satu video MP4 9:16 lengkap dengan musik (lagu1-3.mp3).

Cara pakai (di folder yang berisi SEMUA file undangan: html, png, jpg, mp3):
    pip install playwright
    playwright install chromium
    (ffmpeg harus terpasang)
    python buat_video.py

Hasil: undangan.mp4 di folder yang sama.  Taruh di folder situs, tombol unduh di map.html akan muncul otomatis.
"""
import argparse, functools, http.server, os, shutil, socketserver, subprocess, sys, tempfile, threading, time

TRACKS = ['lagu1.mp3', 'lagu2.mp3', 'lagu3.mp3']
START_TIMES = [15, 20, 13]          # sama persis dengan di situs


def serve(folder):
    class Q(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a): pass
    handler = functools.partial(Q, directory=folder)
    srv = socketserver.ThreadingTCPServer(('127.0.0.1', 0), handler)
    srv.daemon_threads = True
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f'http://127.0.0.1:{srv.server_address[1]}'


def probe(path):
    r = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                        '-of', 'default=nw=1:nk=1', path], capture_output=True, text=True)
    return float(r.stdout.strip())


def record(base, w, h, tmp):
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(args=['--autoplay-policy=no-user-gesture-required', '--mute-audio'])
        ctx = b.new_context(viewport={'width': w, 'height': h}, device_scale_factor=1,
                            record_video_dir=tmp, record_video_size={'width': w, 'height': h})
        t_create = time.time()
        page = ctx.new_page()
        page.goto(base + '/index.html', wait_until='load')
        t_ready = time.time()
        print('• index.html')

        for nama in ['pembukaan', 'namapengantin', 'cerita', 'gif']:
            page.wait_for_url(f'**/{nama}.html', timeout=60000)
            print(f'• {nama}.html')

        # gif.html: tunggu pintu terbuka, lalu gulir pelan sampai bawah
        page.wait_for_selector('.stage.opened', timeout=20000)
        page.wait_for_timeout(1800)
        page.evaluate("""() => new Promise(res => {
            const el = document.querySelector('.wrap'); if(!el) return res();
            const max = el.scrollHeight - el.clientHeight, dur = 7000, t0 = performance.now();
            (function step(t){ const k = Math.min(1,(t-t0)/dur); el.scrollTop = max*k*k*(3-2*k);
              k<1 ? requestAnimationFrame(step) : setTimeout(res,1500); })(t0);
        })""")

        # ending: halaman map
        page.goto(base + '/map.html', wait_until='load')
        print('• map.html (ending)')
        page.wait_for_timeout(6500)

        durasi = time.time() - t_ready + 0.2
        trim = max(0.0, t_ready - t_create - 0.3)
        video = page.video.path()
        ctx.close(); b.close()
    return video, trim, durasi


def susun_audio(folder, durasi):
    """Playlist: lagu1 -> lagu2 -> lagu3 -> ulang, tiap lagu mulai dari START_TIMES, dipotong sepanjang video."""
    if not all(os.path.exists(os.path.join(folder, t)) for t in TRACKS):
        return None
    segs, total, i = [], 0.0, 0
    while total < durasi + 1:
        path = os.path.join(folder, TRACKS[i % 3])
        dur = max(1.0, probe(path) - START_TIMES[i % 3])
        segs.append((path, START_TIMES[i % 3], dur)); total += dur; i += 1
    return segs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', default='.', help='folder berisi semua file undangan')
    ap.add_argument('--out', default=None, help='nama file hasil (default: undangan.mp4 di folder tsb)')
    ap.add_argument('--w', type=int, default=720)
    ap.add_argument('--h', type=int, default=1280)
    a = ap.parse_args()
    folder = os.path.abspath(a.dir)
    out = os.path.abspath(a.out or os.path.join(folder, 'undangan.mp4'))
    if not os.path.exists(os.path.join(folder, 'index.html')):
        sys.exit('index.html tidak ditemukan di ' + folder)

    tmp = tempfile.mkdtemp()
    srv, base = serve(folder)
    print('Merekam… (sekitar 1,5 menit, jangan ditutup)')
    video, trim, durasi = record(base, a.w, a.h, tmp)
    srv.shutdown()
    print(f'Selesai merekam: {durasi:.1f} detik')

    segs = susun_audio(folder, durasi)
    cmd = ['ffmpeg', '-y', '-v', 'error', '-ss', f'{trim:.2f}', '-t', f'{durasi:.2f}', '-i', video]
    if segs:
        for path, ss, dur in segs:
            cmd += ['-ss', f'{ss}', '-t', f'{dur:.2f}', '-i', path]
        n = len(segs)
        fc = ''.join(f'[{k+1}:a]aresample=44100,aformat=channel_layouts=stereo[a{k}];' for k in range(n))
        fc += ''.join(f'[a{k}]' for k in range(n)) + f'concat=n={n}:v=0:a=1[c];'
        fc += f'[c]atrim=0:{durasi:.2f},afade=t=out:st={max(0, durasi-2):.2f}:d=2[aout]'
        cmd += ['-filter_complex', fc, '-map', '0:v', '-map', '[aout]', '-c:a', 'aac', '-b:a', '128k']
    else:
        print('PERINGATAN: lagu1-3.mp3 tidak ditemukan di folder -> video tanpa suara.')
        cmd += ['-an']
    cmd += ['-vf', f'fps=30,scale={a.w}:{a.h}:flags=lanczos,format=yuv420p',
            '-c:v', 'libx264', '-preset', 'medium', '-crf', '20', '-movflags', '+faststart', out]
    subprocess.run(cmd, check=True)
    shutil.rmtree(tmp, ignore_errors=True)
    print(f'\nBERHASIL: {out}  ({os.path.getsize(out)/1e6:.1f} MB)')


if __name__ == '__main__':
    main()
