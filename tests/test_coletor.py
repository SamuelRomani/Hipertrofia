import json

import pytest

from coletor import coletar, db, exportar, temas
from coletor.parser import ler_lista_de_topicos, ler_topico

BASE = "https://www.hipertrofia.org"


def lista(ids_respostas, proxima=None):
    linhas = "".join(
        f"""<li class="ipsDataItem"><div><h4><a href="{BASE}/forum/topic/{i}-topico-{i}/">Tópico {i}</a>
        <a href="{BASE}/forum/topic/{i}-topico-{i}/page/2/">2</a></h4></div>
        <ul class="ipsDataItem_stats"><li>{r} respostas</li><li>1.234 visualizações</li></ul></li>"""
        for i, r in ids_respostas
    )
    nxt = f'<link rel="next" href="{proxima}">' if proxima else ""
    return f"<html><head>{nxt}</head><body><ol>{linhas}</ol></body></html>"


def topico_v4(posts, proxima=None):
    arts = "".join(
        f"""<article id="elComment_{pid}" class="cPost">
        <aside><h3 class="cAuthorPane_author"><strong><a href="{BASE}/forum/profile/1-x/">{autor}</a></strong></h3></aside>
        <div><time datetime="2026-08-18T16:17:00Z">18/08</time>
        <div data-role="commentContent" class="ipsType_richText">
          <blockquote class="ipsQuote"><p>citação de outro post</p></blockquote><p>{texto}</p></div></div></article>"""
        for pid, autor, texto in posts
    )
    nxt = f'<link rel="next" href="{proxima}">' if proxima else ""
    return f"<html><head>{nxt}</head><body><h1>Jiu-Jitsu e treino.</h1>{arts}</body></html>"


def topico_v5(posts):
    arts = "".join(
        f"""<article id="elComment_{pid}" class="ipsEntry">
        <aside class="ipsEntry__author-column"><h3 class="ipsEntry__username"><span class="ipsUsername">{autor}</span></h3>
        <ul class="ipsEntry__authorStats"><li><a href="{BASE}/forum/profile/2-y/badges/">9 Medalhas</a></li></ul></aside>
        <header>
        <time datetime="2026-08-19T12:46:00Z">19/08</time></header>
        <div class="ipsRichText" data-role="commentContent"><p>{texto}</p></div></article>"""
        for pid, autor, texto in posts
    )
    return f"<html><body><h1>Título v5</h1>{arts}</body></html>"


def test_lista_de_topicos_le_respostas_e_ignora_links_de_pagina():
    topicos, prox = ler_lista_de_topicos(lista([(10, 6), (11, 1234)], f"{BASE}/forum/forum/4-x/page/2/"), BASE + "/forum/")
    assert [(t["id"], t["respostas"], t["titulo"]) for t in topicos] == [(10, 6, "Tópico 10"), (11, 1234, "Tópico 11")]
    assert prox.endswith("/page/2/")


def test_topico_v4_remove_citacoes():
    info, posts, prox = ler_topico(topico_v4([(1, "e_ddie", "Parei a musculação"), (2, "outro", "Faz fullbody")]), BASE)
    assert info["titulo"] == "Jiu-Jitsu e treino."
    assert [(p["id"], p["autor"], p["texto"]) for p in posts] == [
        (1, "e_ddie", "Parei a musculação"), (2, "outro", "Faz fullbody")]
    assert posts[0]["data"] == "2026-08-18T16:17:00Z"
    assert prox is None


def test_topico_v5():
    _, posts, _ = ler_topico(topico_v5([(7, "capitain hook", "3 treinos de bjj")]), BASE)
    assert posts == [{"id": 7, "autor": "capitain hook", "data": "2026-08-19T12:46:00Z", "texto": "3 treinos de bjj"}]


def test_topico_json_ld_como_reserva():
    ld = {"@type": "DiscussionForumPosting", "text": "Pergunta", "author": {"name": "a"},
          "dateCreated": "2026-01-01", "comment": [{"text": "Resposta", "author": {"name": "b"}}]}
    html = f'<html><body><script type="application/ld+json">{json.dumps(ld)}</script></body></html>'
    _, posts, _ = ler_topico(html, BASE)
    assert [p["texto"] for p in posts] == ["Pergunta", "Resposta"]


def test_temas_sem_acento_e_palavra_inteira():
    c = temas.compilar({"Proteína": ["proteina"], "CrossFit": ["box"]})
    assert temas.detectar("Quanta PROTEÍNA por dia?", c) == ["Proteína"]
    assert temas.detectar("treino de boxe", c) == []


class SiteFalso:
    """Simula o fórum: subfórum com 3 páginas de listagem."""

    def __init__(self):
        self.paginas = {}
        self.respostas = {i: 1 for i in range(1, 7)}
        self.acessos = []

    def montar(self):
        f = f"{BASE}/forum/forum/4-treinamento/"
        ids = sorted(self.respostas, key=lambda i: -self.ordem.get(i, -i))
        grupos = [ids[0:2], ids[2:4], ids[4:6]]
        urls = [f, f + "page/2/", f + "page/3/"]
        for n, (url, grupo) in enumerate(zip(urls, grupos)):
            prox = urls[n + 1] if n + 1 < len(urls) else None
            self.paginas[url] = lista([(i, self.respostas[i]) for i in grupo], prox)
        for i in self.respostas:
            self.paginas[f"{BASE}/forum/topic/{i}-topico-{i}/"] = topico_v4(
                [(i * 10 + k, f"user{k}", f"post {k} do tópico {i} sobre creatina") for k in range(self.respostas[i] + 1)])

    ordem = {}

    def get(self, url):
        self.acessos.append(url)
        return self.paginas[url]


@pytest.fixture
def site(monkeypatch, tmp_path):
    falso = SiteFalso()
    falso.montar()

    class ClienteFalso:
        requisicoes = 0

        def __init__(self, config):
            pass

        def get(self, url):
            return falso.get(url)

    monkeypatch.setattr(coletar, "Cliente", ClienteFalso)
    cfg = json.load(open("config.json", encoding="utf-8"))
    cfg["foruns"] = [f for f in cfg["foruns"] + cfg.get("foruns_pausados", []) if f["id"] == 4]
    (tmp_path / "config.json").write_text(json.dumps(cfg))
    falso.args = ["--config", str(tmp_path / "config.json"), "--db", str(tmp_path / "f.db")]
    falso.tmp = tmp_path
    return falso


def topicos_salvos(site):
    con = db.conectar(str(site.tmp / "f.db"))
    return {r["id"]: r["respostas"] for r in con.execute("SELECT id, respostas FROM topicos")}


def test_coleta_incremental_com_historico(site):
    coletar.main(site.args + ["--max-topicos", "3"])
    assert topicos_salvos(site) == {1: 1, 2: 1, 3: 1}

    # Segunda execução: página 2 já é conhecida em parte, continua o histórico.
    coletar.main(site.args + ["--max-topicos", "10"])
    assert topicos_salvos(site) == {i: 1 for i in range(1, 7)}

    # Tópico 2 recebe respostas e sobe para o topo; só ele é baixado de novo.
    site.respostas[2] = 3
    site.ordem = {2: 100}
    site.montar()
    site.acessos.clear()
    coletar.main(site.args + ["--max-topicos", "10"])
    assert topicos_salvos(site)[2] == 3
    baixados = [u for u in site.acessos if "/topic/" in u]
    assert baixados == [f"{BASE}/forum/topic/2-topico-2/"]


def test_anonimiza_e_exporta(site):
    coletar.main(site.args + ["--max-topicos", "10"])
    con = db.conectar(str(site.tmp / "f.db"))
    autores = {r[0] for r in con.execute("SELECT autor FROM posts")}
    assert all(a.startswith("u_") for a in autores) and "user0" not in str(autores)

    saida = site.tmp / "site"
    exportar.main(["--config", str(site.tmp / "config.json"), "--db", str(site.tmp / "f.db"), "--saida", str(saida)])
    dados = json.loads((saida / "topicos.json").read_text())
    assert len(dados) == 6 and "Creatina" in dados[0]["temas"]
    assert "user0" not in (saida / "topicos.json").read_text()


def test_historico_avanca_em_varias_execucoes_pequenas(site):
    for _ in range(6):
        coletar.main(site.args + ["--max-topicos", "1"])
    assert topicos_salvos(site) == {i: 1 for i in range(1, 7)}
    con = db.conectar(str(site.tmp / "f.db"))
    assert db.ler_estado(con, 4) == (4, True)


def test_lista_ignora_linha_de_subforum():
    html = f"""<ol><li class="ipsData__item"><a href="{BASE}/forum/forum/40-artigos/">Artigos</a> 21,2k posts
      <a href="{BASE}/forum/topic/5-ultimo-artigo/">Último artigo</a></li></ol>""" + lista([(9, 0)])
    topicos, _ = ler_lista_de_topicos(html, BASE)
    assert [(t["id"], t["respostas"]) for t in topicos] == [(9, 0)]


def test_topico_com_proxima_pagina_repetida_nao_trava():
    url = f"{BASE}/forum/topic/1-x/"
    pagina = topico_v4([(1, "a", "oi")], proxima=url)

    class C:
        def get(self, u):
            return pagina

    _, posts = coletar.coletar_topico(C(), url)
    assert len(posts) == 1


def test_paginas_reais_salvas():
    """Páginas reais do fórum (Invision 5), se o diagnóstico tiver sido salvo localmente."""
    import os
    caminho = os.path.join(os.path.dirname(__file__), "paginas_reais")
    if not os.path.isdir(caminho):
        pytest.skip("sem páginas reais")
    with open(os.path.join(caminho, "topico.html"), encoding="utf-8") as f:
        _, posts, _ = ler_topico(f.read(), BASE)
    assert posts[0]["autor"] == "e_ddie" and posts[1]["autor"] == "diogooliveira"
    assert "Medalhas" not in {p["autor"] for p in posts}
    with open(os.path.join(caminho, "lista.html"), encoding="utf-8") as f:
        topicos, prox = ler_lista_de_topicos(f.read(), BASE + "/forum/forum/4-treinamento/")
    assert len(topicos) >= 25 and all(t["respostas"] is not None for t in topicos)
    assert prox.endswith("/page/2/")


def test_post_em_destaque_repetido_entra_uma_vez():
    url = f"{BASE}/forum/topic/1-x/"
    paginas = {
        url: topico_v4([(1, "a", "pergunta"), (2, "b", "melhor resposta")], proxima=url + "page/2/"),
        url + "page/2/": topico_v4([(2, "b", "melhor resposta"), (3, "c", "outra")]),
    }

    class C:
        def get(self, u):
            return paginas[u]

    _, posts = coletar.coletar_topico(C(), url)
    assert [p["id"] for p in posts] == [1, 2, 3]
