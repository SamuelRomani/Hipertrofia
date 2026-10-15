"""Coleta incremental dos tópicos públicos do fórum Hipertrofia.org.

Respeita o robots.txt do site, espera entre as requisições e guarda os autores
apenas como códigos anônimos.

Uso: python -m coletor.coletar [--max-topicos N] [--max-paginas N] [--db dados/forum.db]
"""
import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from urllib import robotparser
from urllib.parse import urljoin

import requests

from . import db
from .parser import ler_lista_de_topicos, ler_topico


class Cliente:
    def __init__(self, config):
        self.base = config["base_url"]
        self.intervalo = config["intervalo_entre_requisicoes_s"]
        self.sessao = requests.Session()
        self.sessao.headers["User-Agent"] = config["user_agent"]
        self.robots = robotparser.RobotFileParser()
        resp = self.sessao.get(urljoin(self.base, "/robots.txt"), timeout=30)
        resp.raise_for_status()
        self.robots.parse(resp.text.splitlines())
        self._ultima = 0.0
        self.requisicoes = 0

    def get(self, url):
        if not self.robots.can_fetch(self.sessao.headers["User-Agent"], url):
            raise PermissionError(f"robots.txt não permite: {url}")
        espera = self.intervalo - (time.monotonic() - self._ultima)
        if espera > 0:
            time.sleep(espera)
        for tentativa in range(4):
            self._ultima = time.monotonic()
            self.requisicoes += 1
            try:
                resp = self.sessao.get(url, timeout=30)
            except requests.RequestException as erro:
                print(f"  erro de rede ({erro}), tentando de novo", flush=True)
            else:
                if resp.status_code == 200:
                    return resp.text
                if resp.status_code not in (429, 500, 502, 503, 504):
                    resp.raise_for_status()
                print(f"  HTTP {resp.status_code}, aguardando para tentar de novo", flush=True)
            time.sleep(30 * (tentativa + 1))
        raise RuntimeError(f"Falhou após várias tentativas: {url}")


def url_da_pagina(inicio, n):
    return inicio if n == 1 else inicio.rstrip("/") + f"/page/{n}/"


def coletar_topico(cliente, url):
    posts, titulo, pagina = [], None, url
    while pagina:
        info, novos, pagina = ler_topico(cliente.get(pagina), pagina)
        titulo = titulo or info["titulo"]
        posts.extend(novos)
    return titulo, posts


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--db", default="dados/forum.db")
    ap.add_argument("--max-topicos", type=int, default=300, help="limite de tópicos baixados nesta execução")
    ap.add_argument("--max-paginas", type=int, default=0, help="limite de páginas de listagem por subfórum (0 = sem limite)")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    sal = os.environ.get("SAL_ANONIMIZACAO") or "hipertrofia-pesquisa"
    con = db.conectar(args.db)
    cliente = Cliente(config)
    agora = datetime.now(timezone.utc).isoformat(timespec="seconds")
    baixados = falhas = 0

    for forum in config["foruns"]:
        if baixados >= args.max_topicos:
            break
        print(f"== {forum['nome']}", flush=True)
        inicio = urljoin(config["base_url"], forum["url"])
        antiga, completo = db.ler_estado(con, forum["id"])
        # Fase "novidades": da página 1 em diante, até achar uma página sem mudanças.
        # Fase "histórico": continua de onde a coleta anterior parou nas páginas antigas.
        fase, n = "novidades", 1
        while baixados < args.max_topicos:
            url = url_da_pagina(inicio, n)
            topicos, proxima = ler_lista_de_topicos(cliente.get(url), url)
            mudou_algo = interrompido = False
            for t in topicos:
                if baixados >= args.max_topicos:
                    interrompido = True
                    break
                # A listagem vem ordenada pela última atividade: tópico conhecido com o
                # mesmo número de respostas não mudou desde a última coleta.
                conhecido = db.respostas_conhecidas(con, t["id"])
                if conhecido is not None and t["respostas"] is not None and conhecido == t["respostas"]:
                    continue
                mudou_algo = True
                try:
                    titulo, posts = coletar_topico(cliente, t["url"])
                except Exception as erro:  # um tópico com problema não derruba a coleta
                    falhas += 1
                    print(f"  falhou {t['url']}: {erro}", flush=True)
                    continue
                if not posts:
                    falhas += 1
                    print(f"  nenhum post lido em {t['url']}", flush=True)
                    continue
                for p in posts:
                    p["autor"] = db.anonimizar(p["autor"], sal)
                t.update(forum_id=forum["id"], forum=forum["nome"], titulo=t["titulo"] or titulo)
                db.salvar_topico(con, t, posts, agora)
                baixados += 1
                print(f"  [{baixados}] p.{n} {t['titulo'][:70]} ({len(posts)} posts)", flush=True)
            if interrompido:
                break
            if not proxima:
                completo = True
            if n + 1 > antiga or completo:
                antiga = max(antiga, n + 1)
                db.salvar_estado(con, forum["id"], antiga, completo)
            if not proxima or (args.max_paginas and n >= args.max_paginas):
                break
            # A página 1 tem tópicos fixos, então só a partir da 2 "sem mudanças" encerra.
            if fase == "novidades" and n > 1 and not mudou_algo:
                if completo:
                    break
                fase, n = "histórico", antiga
                print(f"  sem novidades; continuando o histórico na página {n}", flush=True)
                continue
            n += 1

    total = con.execute("SELECT COUNT(*) FROM topicos").fetchone()[0]
    print(f"\nTópicos baixados agora: {baixados} | falhas: {falhas} | "
          f"requisições: {cliente.requisicoes} | total na base: {total}")
    # Se nada foi lido, provavelmente o layout do site mudou: falha visível no Actions.
    if baixados == 0 and falhas > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
