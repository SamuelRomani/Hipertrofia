"""Base SQLite com busca de texto completo (FTS5)."""
import hashlib
import os
import sqlite3

ESQUEMA = """
CREATE TABLE IF NOT EXISTS topicos (
    id INTEGER PRIMARY KEY,
    forum_id INTEGER NOT NULL,
    forum TEXT NOT NULL,
    titulo TEXT NOT NULL,
    url TEXT NOT NULL,
    respostas INTEGER,
    criado_em TEXT,
    ultima_resposta_em TEXT,
    coletado_em TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS posts (
    topico_id INTEGER NOT NULL REFERENCES topicos(id),
    posicao INTEGER NOT NULL,
    post_id INTEGER,
    autor TEXT,
    data TEXT,
    texto TEXT NOT NULL,
    PRIMARY KEY (topico_id, posicao)
);
CREATE TABLE IF NOT EXISTS estado_foruns (
    forum_id INTEGER PRIMARY KEY,
    proxima_pagina_antiga INTEGER NOT NULL DEFAULT 1,
    completo INTEGER NOT NULL DEFAULT 0
);
CREATE VIRTUAL TABLE IF NOT EXISTS posts_fts USING fts5(
    texto, titulo UNINDEXED, topico_id UNINDEXED, posicao UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def conectar(caminho):
    os.makedirs(os.path.dirname(caminho) or ".", exist_ok=True)
    con = sqlite3.connect(caminho)
    con.row_factory = sqlite3.Row
    con.executescript(ESQUEMA)
    return con


def anonimizar(nome, sal):
    """Troca o nome de usuário por um código estável que não revela o nome."""
    if not nome:
        return None
    return "u_" + hashlib.sha256((sal + nome.strip().lower()).encode()).hexdigest()[:10]


def salvar_topico(con, topico, posts, coletado_em):
    datas = [p["data"] for p in posts if p.get("data")]
    con.execute("DELETE FROM posts WHERE topico_id = ?", (topico["id"],))
    con.execute("DELETE FROM posts_fts WHERE topico_id = ?", (topico["id"],))
    con.execute(
        """INSERT OR REPLACE INTO topicos
           (id, forum_id, forum, titulo, url, respostas, criado_em, ultima_resposta_em, coletado_em)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (topico["id"], topico["forum_id"], topico["forum"], topico["titulo"], topico["url"],
         topico.get("respostas"), min(datas) if datas else None, max(datas) if datas else None,
         coletado_em),
    )
    for i, p in enumerate(posts):
        con.execute(
            "INSERT INTO posts (topico_id, posicao, post_id, autor, data, texto) VALUES (?, ?, ?, ?, ?, ?)",
            (topico["id"], i, p.get("id"), p.get("autor"), p.get("data"), p["texto"]),
        )
        con.execute(
            "INSERT INTO posts_fts (texto, titulo, topico_id, posicao) VALUES (?, ?, ?, ?)",
            (p["texto"], topico["titulo"], topico["id"], i),
        )
    con.commit()


def respostas_conhecidas(con, topico_id):
    """Número de respostas salvo na última coleta, ou None se o tópico é novo."""
    linha = con.execute("SELECT respostas FROM topicos WHERE id = ?", (topico_id,)).fetchone()
    return None if linha is None else linha["respostas"]


def ler_estado(con, forum_id):
    linha = con.execute(
        "SELECT proxima_pagina_antiga, completo FROM estado_foruns WHERE forum_id = ?", (forum_id,)
    ).fetchone()
    return (linha[0], bool(linha[1])) if linha else (1, False)


def salvar_estado(con, forum_id, proxima_pagina_antiga, completo):
    con.execute(
        "INSERT OR REPLACE INTO estado_foruns (forum_id, proxima_pagina_antiga, completo) VALUES (?, ?, ?)",
        (forum_id, proxima_pagina_antiga, int(completo)),
    )
    con.commit()
