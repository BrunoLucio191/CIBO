#!/usr/bin/env python3
"""Prepare the approved SEBRAE guest windows with one enhanced audio track."""
import argparse
import importlib.util
import json
import os
import subprocess
import unicodedata


CLIPS = [
    {"guest": "Gabriel", "master": "14:08:26/2026-08-14 17-32-17.mkv", "srt": "14:08:26/legendas/2026-08-14 17-32-17_davinci.srt", "id": "corte_01", "start": 74, "end": 118, "audio_track": 1, "headline": "INOVAÇÃO NÃO É\nFAZER O MESMO\nDE SEMPRE"},
    {"guest": "Gabriel", "master": "14:08:26/2026-08-14 17-32-17.mkv", "srt": "14:08:26/legendas/2026-08-14 17-32-17_davinci.srt", "id": "corte_02", "start": 118, "end": 160, "headline": "MENOS OBRAS\nMAIS QUALIDADE\nE MAIS TEMPO"},
    {"guest": "Lula Filho", "master": "14:08:26/2026-08-15 19-06-13.mkv", "srt": "14:08:26/legendas/2026-08-15 19-06-13_davinci.srt", "id": "corte_01", "start": 127, "end": 184, "headline": "EQUILÍBRIO NÃO É\nDIVIDIR TUDO\nEM PARTES IGUAIS"},
    {"guest": "Lula Filho", "master": "14:08:26/2026-08-15 19-06-13.mkv", "srt": "14:08:26/legendas/2026-08-15 19-06-13_davinci.srt", "id": "corte_02", "start": 419, "end": 454, "headline": "3 CRENÇAS QUE\nDEFINEM SUA\nTRANSFORMAÇÃO"},
    {"guest": "Rodrigo Mamed", "master": "14:08:26/2026-08-16 11-31-59.mkv", "srt": "14:08:26/legendas/2026-08-16 11-31-59_davinci.srt", "id": "corte_01", "start": 234, "end": 291, "headline": "MISTURAR AS CONTAS\nESCONDE O LUCRO\nDA SUA CLÍNICA"},
    {"guest": "Rodrigo Mamed", "master": "14:08:26/2026-08-16 11-31-59.mkv", "srt": "14:08:26/legendas/2026-08-16 11-31-59_davinci.srt", "id": "corte_02", "start": 384, "end": 443, "headline": "O FATOR R PODE\nREDUZIR O IMPOSTO\nDA SUA CLÍNICA"},
    {"guest": "Márcio", "master": "14:08:26/2026-08-16 17-24-59.mkv", "srt": "14:08:26/legendas/2026-08-16 17-24-59_davinci.srt", "id": "corte_01", "start": 232, "end": 289, "headline": "A PESQUISA PRECISA\nSAIR DO PAPEL E\nCHEGAR AO MERCADO"},
    {"guest": "Márcio", "master": "14:08:26/2026-08-16 17-24-59.mkv", "srt": "14:08:26/legendas/2026-08-16 17-24-59_davinci.srt", "id": "corte_02", "start": 300, "end": 356, "headline": "PROTEJA A IDEIA\nANTES DE PUBLICAR\nSUA PESQUISA"},
    {"guest": "Felipe Mussalem", "master": "14:08:26/2026-08-16 18-13-30.mkv", "srt": "14:08:26/legendas/2026-08-16 18-13-30_davinci.srt", "id": "corte_01", "start": 231, "end": 291, "headline": "O EMPREENDEDOR\nPRECISA TER\nBRILHO NOS OLHOS"},
    {"guest": "Felipe Mussalem", "master": "14:08:26/2026-08-16 18-13-30.mkv", "srt": "14:08:26/legendas/2026-08-16 18-13-30_davinci.srt", "id": "corte_02", "start": 771, "end": 829, "audio_track": 1, "headline": "TODO CAMINHO É\nDIFÍCIL\nESCOLHA O SEU"},
    {"guest": "Vilena Silva", "master": "14:08:26/2026-08-16 20-03-45.mkv", "srt": "14:08:26/legendas/2026-08-16 20-03-45_davinci.srt", "id": "corte_01", "start": 410, "end": 468, "headline": "UM NEGÓCIO DE\nIMPACTO COMEÇA\nPELO PROPÓSITO"},
    {"guest": "Vilena Silva", "master": "14:08:26/2026-08-16 20-03-45.mkv", "srt": "14:08:26/legendas/2026-08-16 20-03-45_davinci.srt", "id": "corte_02", "start": 548, "end": 606, "headline": "SUSTENTABILIDADE\nVIROU ESTRATÉGIA\nDE MERCADO"},
]


def load_audio_module(script_dir):
    path = os.path.join(script_dir, "audio_select_enhance.py")
    spec = importlib.util.spec_from_file_location("content_hub_audio", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def ffmpeg_source(master, audio, start, duration, output):
    subprocess.run([
        "ffmpeg", "-y", "-v", "error", "-ss", str(start), "-t", str(duration),
        "-i", master, "-i", audio, "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
        "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k",
        "-shortest", "-movflags", "+faststart", output,
    ], check=True)


def safe_filename(item):
    text = " - ".join(item["headline"].splitlines())
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return f"{item['id'][-2:]} - {text}"


def write_jobs(root, outroot, reports):
    music = os.path.join(root, "14:08:26", "mixkit-driving-ambition-32.mp3")
    by_guest = {}
    for report in reports:
        by_guest.setdefault(report["guest"], []).append(report)
    for guest, items in by_guest.items():
        guest_dir = os.path.join(outroot, guest)
        clips = {}
        for item in items:
            clips[item["id"]] = {
                "src": os.path.basename(item["source"]),
                "master_in": item["start"],
                "headline": item["headline"],
                "filename": safe_filename(item),
                "cropx": 0.5,
                "cropx_timeline": [],
                "scene_burn_times": [],
                "cover_t": min(12, item["duration"] / 3),
                "music": music,
                "click_times": [],
                "impact_pulses": [],
                "long_moves": [{"t": max(2, item["duration"] * 0.45), "amount": 0.035, "duration": 2.6}],
                "keeps": [[0.0, item["duration"]]],
            }
        job = {
            "srt": os.path.join(root, items[0]["srt"]),
            "srcdir": os.path.join(guest_dir, "sources"),
            "work": os.path.join(guest_dir, "work"),
            "outdir": os.path.join(root, "cortes_content_hub", guest),
            "click_gain": 0.09,
            "mix": {"music_db": -25, "duck_threshold": 0.07, "duck_ratio": 6,
                    "outro_burn_db": -10, "limiter": 0.85, "limiter_level": False},
            "preset": "medium",
            "crf": 22,
            "emph": "inovação qualidade equilíbrio transformação lucro fator pesquisa mercado ideia empreendedor brilho difícil impacto propósito sustentabilidade estratégia",
            "fix": [["Conte de Rube", "Content Hub"], ["Cebraio", "Sebrae"], ["Cebrae", "Sebrae"]],
            "clips": clips,
        }
        with open(os.path.join(guest_dir, "job.json"), "w", encoding="utf-8") as handle:
            json.dump(job, handle, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=os.getcwd())
    parser.add_argument("--output", default="content_hub_work")
    parser.add_argument("--only", action="append", help="nome exato do convidado")
    parser.add_argument("--jobs-only", action="store_true")
    args = parser.parse_args()
    root = os.path.abspath(args.root)
    outroot = os.path.abspath(args.output)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    audio = load_audio_module(script_dir)
    os.makedirs(outroot, exist_ok=True)
    report_path = os.path.join(outroot, "audio_selection.json")
    if args.jobs_only:
        reports = json.load(open(report_path, encoding="utf-8"))
        write_jobs(root, outroot, reports)
        return
    reports = []
    for item in CLIPS:
        if args.only and item["guest"] not in args.only:
            continue
        duration = item["end"] - item["start"]
        guest_dir = os.path.join(outroot, item["guest"])
        source_dir = os.path.join(guest_dir, "sources")
        os.makedirs(source_dir, exist_ok=True)
        master = os.path.join(root, item["master"])
        enhanced = os.path.join(source_dir, item["id"] + "_enhanced.wav")
        output = os.path.join(source_dir, item["id"] + ".mp4")
        selected, tracks = audio.choose(master, item["start"], duration)
        if "audio_track" in item:
            selected = next(track for track in tracks if track["audio_index"] == item["audio_track"])
        enhancement = audio.enhance(master, selected["audio_index"], enhanced, item["start"], duration)
        ffmpeg_source(master, enhanced, item["start"], duration, output)
        report = dict(item, duration=duration, selected_audio=selected, tracks=tracks,
                      enhancement=enhancement, source=output)
        reports.append(report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    with open(report_path, "w", encoding="utf-8") as handle:
        json.dump(reports, handle, ensure_ascii=False, indent=2)
    write_jobs(root, outroot, reports)


if __name__ == "__main__":
    main()
