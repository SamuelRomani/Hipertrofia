"""Busca na base local pelo terminal, útil para pesquisa mais detalhada.

Uso: python -m coletor.buscar "creatina jiu" [--limite 20] [--db dados/forum.db]
A consulta aceita a sintaxe do SQLite FTS5: "frase exata", OR, NOT, prefixo*.
"""
import argparse

from . import db


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("consulta")
    ap.add_argument("--db", default="dados/forum.db")
    ap.add_argument("--limite", type=int, default=20)
    args = ap.parse_args(argv)

    con = db.conectar(args.db)
    linhas = con.execute(
        """SELECT t.titulo, t.url, t.forum, p.data, p.autor,
                  snippet(posts_fts, 0, '[', ']', ' … ', 24) AS trecho
           FROM posts_fts
           JOIN posts p ON p.topico_id = posts_fts.topico_id AND p.posicao = posts_fts.posicao
           JOIN topicos t ON t.id = p.topico_id
           WHERE posts_fts MATCH ? ORDER BY rank LIMIT ?""",
        (args.consulta, args.limite),
    ).fetchall()
    for r in linhas:
        print(f"{r['titulo']}  ({r['forum']}, {(r['data'] or '')[:10]}, {r['autor']})")
        print(f"  {r['trecho']}")
        print(f"  {r['url']}\n")
    if not linhas:
        print("Nada encontrado.")


if __name__ == "__main__":
    main()
