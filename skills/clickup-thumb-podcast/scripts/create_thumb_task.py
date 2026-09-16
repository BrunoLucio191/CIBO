#!/usr/bin/env python3
"""Cria a demanda de thumb de podcast no ClickUp (ContentHub > Max > Edição).

Uso:
  python3 create_thumb_task.py job.json            # mostra a prévia (dry-run)
  python3 create_thumb_task.py job.json --send     # cria a tarefa de verdade

job.json:
{
  "podcast": "Pod Acontecer",
  "ep": "20",
  "convidado": "Paulo Marinho Júnior",
  "titulo_thumb": "O QUE CAUSOU O ROMPIMENTO?",
  "subtitulo": "Paulo Marinho Júnior e Fábio Gentil",
  "hosts": ["Mota", "John Cutrim"],
  "instagram_convidado": "instagram.com/...", # opcional
  "orientacoes": ["..."],                 # opcional, soma às orientações padrão
  "gravacao": "https://drive...",          # opcional
  "subir_aqui": "https://drive...",        # opcional
  "prazo": "2026-09-16 12:00"              # opcional; padrão: amanhã 12:00 (BRT)
}
"""
import json, sys, datetime, urllib.request
from pathlib import Path

LIST_ID = "901112367271"  # ContentHub > Max > Edição
ASSIGNEES = {"Bruno Lucio BeGrow": 81565536, "Jorge Luis": 75568670}
STATUS = "pendente"
PRIORITY = 3  # 1 urgente, 2 alta, 3 normal, 4 baixa
BRT = datetime.timezone(datetime.timedelta(hours=-3))
API = "https://api.clickup.com/api/v2"
# Instagram fixo dos hosts, repetido em toda demanda
HOST_INSTAGRAM = {
    "Mota": "instagram.com/portaldomota_",
    "John Cutrim": "instagram.com/john.cutrim",
}


def token():
    return (Path.home() / ".config/clickup/token").read_text().strip()


def due_ms(prazo):
    if prazo:
        dt = datetime.datetime.strptime(prazo, "%Y-%m-%d %H:%M").replace(tzinfo=BRT)
    else:
        amanha = datetime.datetime.now(BRT).date() + datetime.timedelta(days=1)
        dt = datetime.datetime.combine(amanha, datetime.time(12, 0), BRT)
    return int(dt.timestamp() * 1000), dt


def build(job):
    ep = str(job["ep"]).zfill(2)
    name = f"[Podcast - {job['podcast']}] - Thumb EP {ep} - {job['convidado'].upper()}: {job['titulo_thumb'].upper()}"
    hosts = job.get("hosts", [])
    orient = [
        "ATENÇÃO: pegar as imagens do convidado e dos hosts diretamente da gravação do episódio.",
    ]
    if hosts:
        quem = " e ".join(f"**{h}**" for h in hosts)
        orient.append(f"Nesta thumb {'terá' if len(hosts) > 1 else 'terá apenas'} {quem} como host{'s' if len(hosts) > 1 else ''}.")
    orient += job.get("orientacoes", [])
    lines = [
        f"**Ep: {ep}**",
        f"**Título da Thumb:** {job['titulo_thumb']}",
        f"**Subtítulo:** {job['subtitulo']}",
        f"**Convidado:** {job['convidado']}",
        "**Orientações para a thumb:**",
        "",
        *[f"*   {o}" for o in orient],
        "",
        "**Instagram dos hosts e convidados:**" if job.get("instagram_convidado") else "**Instagram dos hosts:**",
        *[f"Instagram {HOST_INSTAGRAM.get(h, f'[LINK DO INSTAGRAM DE {h.upper()}]')}" for h in hosts],
        *([f"Instagram {job['instagram_convidado']}"] if job.get("instagram_convidado") else []),
        "",
        f"**Gravação:** {job.get('gravacao') or '[LINK DA GRAVAÇÃO]'}",
        f"**Subir aqui:** {job.get('subir_aqui') or '[LINK DA PASTA PARA UPLOAD DA THUMB]'}",
    ]
    ms, dt = due_ms(job.get("prazo"))
    body = {
        "name": name,
        "markdown_content": "\n".join(lines),
        "assignees": list(ASSIGNEES.values()),
        "status": STATUS,
        "priority": PRIORITY,
        "due_date": ms,
        "due_date_time": True,
    }
    return body, dt


def main():
    job = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    body, dt = build(job)
    print("NOME:", body["name"])
    print("RESPONSÁVEIS:", ", ".join(ASSIGNEES))
    print("STATUS:", STATUS, "| PRIORIDADE: normal | PRAZO:", dt.strftime("%d/%m/%Y %H:%M"), "(BRT)")
    print("---\n" + body["markdown_content"] + "\n---")
    if "--send" not in sys.argv:
        print("(prévia — rode com --send para criar)")
        return
    req = urllib.request.Request(
        f"{API}/list/{LIST_ID}/task", data=json.dumps(body).encode(),
        headers={"Authorization": token(), "Content-Type": "application/json"}, method="POST")
    res = json.load(urllib.request.urlopen(req))
    print("CRIADA:", res["id"], res["url"])


if __name__ == "__main__":
    main()
