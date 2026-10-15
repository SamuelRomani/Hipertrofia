"""Gera os arquivos JSON lidos pela página de busca (GitHub Pages).

Uso: python -m coletor.exportar [--db dados/forum.db] [--saida site/dados]
"""
import argparse
import json
import os
from datetime import datetime, timezone

from . import db, temas


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--db", default="dados/forum.db")
    ap.add_argument("--saida", default="site/dados")
    args = ap.parse_args(argv)

    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    limite = config["max_caracteres_por_topico_no_site"]
    compilados = temas.compilar(config["temas"])
    con = db.conectar(args.db)

    topicos = []
    for t in con.execute("SELECT * FROM topicos ORDER BY ultima_resposta_em DESC"):
        posts = con.execute(
            "SELECT texto FROM posts WHERE topico_id = ? ORDER BY posicao", (t["id"],)
        ).fetchall()
        completo = "\n\n".join(p["texto"] for p in posts)
        topicos.append({
            "id": t["id"],
            "titulo": t["titulo"],
            "url": t["url"],
            "forum": t["forum"],
            "respostas": t["respostas"] if t["respostas"] is not None else max(len(posts) - 1, 0),
            "data": (t["criado_em"] or "")[:10],
            "ultima": (t["ultima_resposta_em"] or "")[:10],
            "temas": temas.detectar(t["titulo"] + "\n" + completo, compilados),
            "texto": completo[:limite],
        })

    os.makedirs(args.saida, exist_ok=True)
    with open(os.path.join(args.saida, "topicos.json"), "w", encoding="utf-8") as f:
        json.dump(topicos, f, ensure_ascii=False, separators=(",", ":"))
    meta = {
        "gerado_em": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "topicos": len(topicos),
        "posts": con.execute("SELECT COUNT(*) FROM posts").fetchone()[0],
        "foruns": [f["nome"] for f in config["foruns"]],
        "temas": list(config["temas"]),
    }
    with open(os.path.join(args.saida, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=1)
    print(f"Exportados {len(topicos)} tópicos para {args.saida}")


if __name__ == "__main__":
    main()
