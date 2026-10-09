#!/usr/bin/env python3
"""Fecha o corte com film burn INTEIRO terminando em tela PRETA (regra fixa do usuario).

uso: burn_end.py ENTRADA.mp4 SAIDA.mp4 [FILMBURN.mp4]
A entrada deve ter sido renderizada com BURN_OUT=0. O script:
  - congela o ultimo quadro por 1,2 s (a ultima palavra nunca e engolida);
  - comeca o burn 0,5 s antes do fim da fala; o asset (1,4 s, pico em 0,53 s) toca inteiro;
  - escurece a imagem por baixo do burn a partir do pico, entao o burn some sobre o preto
    e o video termina preto;
  - musica/voz: apad + afade de 1,3 s.
"""
import os, subprocess, sys
src, out = sys.argv[1], sys.argv[2]
fb = sys.argv[3] if len(sys.argv) > 3 else os.path.join(os.path.dirname(__file__), '..', 'assets', 'filmburn_blue.mp4')
D = float(subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', src],
                         capture_output=True, text=True).stdout)
w, h = subprocess.run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0:s=x', src],
                      capture_output=True, text=True).stdout.strip().split('x')
tail = out + '.burntail.mp4'
# burn + 2,5 s de preto (tpad de cauda no burn nao funciona encadeado: o video acabava junto com o asset)
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', fb, '-f', 'lavfi', '-i', f'color=black:s={w}x{h}:r=30:d=2.5', '-filter_complex',
                f'[0:v]fps=30,scale={w}:{h},format=yuv420p,setsar=1[a];[1:v]format=yuv420p,setsar=1[b];[a][b]concat=n=2:v=1:a=0[v]',
                '-map', '[v]', '-c:v', 'libx264', '-crf', '10', '-preset', 'fast', tail], check=True)
st, fd, tot, af = D - 0.5, D - 0.05, D + 1.2, D - 0.4
fc = (f'[0:v]tpad=stop_mode=clone:stop_duration=1.2,fade=t=out:st={fd:.3f}:d=0.55,format=gbrp[v];'
      f'[1:v]format=gbrp,tpad=start_mode=add:start_duration={st:.3f}:color=black[b];'
      f'[v][b]blend=all_mode=screen:shortest=1,format=yuv420p[vo];'
      f'[0:a]apad=pad_dur=1.2,afade=t=out:st={af:.3f}:d=1.3[ao]')
tmp = out + '.tmp.mp4'
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-i', tail, '-filter_complex', fc, '-map', '[vo]', '-map', '[ao]',
                '-t', f'{tot:.3f}', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-c:a', 'aac', '-b:a', '160k',
                '-movflags', '+faststart', tmp], check=True)
subprocess.run(['ffmpeg', '-v', 'error', '-i', tmp, '-f', 'null', '-'], check=True)
os.replace(tmp, out); os.remove(tail); print('ok', out, f'{tot:.2f}s')
