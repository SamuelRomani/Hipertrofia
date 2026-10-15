"""Leitura das páginas do fórum (Invision Community, versões 4 e 5)."""
import json
import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup

TOPICO_RE = re.compile(r"/forum/topic/(\d+)-[^/?#]*")
RESPOSTAS_RE = re.compile(r"(\d[\d.]*)\s+respostas?", re.IGNORECASE)


def _soup(html):
    return BeautifulSoup(html, "html.parser")


def proxima_pagina(soup, url_atual):
    """URL da próxima página (link rel=next do Invision), ou None."""
    link = soup.find("link", rel="next") or soup.find("a", rel="next")
    if link and link.get("href"):
        return urljoin(url_atual, link["href"])
    return None


def ler_lista_de_topicos(html, url_atual):
    """Tópicos de uma página de listagem de subfórum.

    Retorna (topicos, url_proxima_pagina). Cada tópico é um dict com id, titulo,
    url e respostas (None quando não foi possível ler).
    """
    soup = _soup(html)
    topicos = {}
    for a in soup.find_all("a", href=TOPICO_RE):
        m = TOPICO_RE.search(a["href"])
        titulo = a.get_text(" ", strip=True)
        tid = int(m.group(1))
        # Links de "última página", "ir para o post" etc. não têm título útil.
        if not titulo or tid in topicos or "findComment" in a["href"] or "/page/" in a["href"]:
            continue
        linha = a.find_parent("li") or a.find_parent("tr") or a.find_parent("div")
        respostas = None
        if linha:
            rm = RESPOSTAS_RE.search(linha.get_text(" ", strip=True))
            if rm:
                respostas = int(rm.group(1).replace(".", ""))
        url = urljoin(url_atual, a["href"].split("?")[0].split("#")[0])
        topicos[tid] = {"id": tid, "titulo": titulo, "url": url, "respostas": respostas}
    return list(topicos.values()), proxima_pagina(soup, url_atual)


def _texto_limpo(el):
    for lixo in el.select("blockquote, script, style, .ipsQuote, .ipsSpoiler_header, .ipsEmbeddedVideo"):
        lixo.decompose()
    texto = el.get_text("\n", strip=True)
    return re.sub(r"\n{3,}", "\n\n", texto).strip()


def _autor(article):
    for sel in (
        ".cAuthorPane_author a",
        ".ipsEntry__username a",
        "[data-role='author'] a",
        "[itemprop='author'] [itemprop='name']",
        "a[href*='/forum/profile/']",
    ):
        el = article.select_one(sel)
        if el and el.get_text(strip=True):
            return el.get_text(strip=True)
    return None


def _posts_json_ld(soup):
    """Alguns temas do Invision publicam os posts em JSON-LD; usado como reserva."""
    posts = []
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            dados = json.loads(script.string or "")
        except (json.JSONDecodeError, TypeError):
            continue
        for item in dados if isinstance(dados, list) else [dados]:
            if not isinstance(item, dict) or item.get("@type") != "DiscussionForumPosting":
                continue
            principal = dict(item, comment=None)
            for i, p in enumerate([principal] + list(item.get("comment") or [])):
                texto = (p.get("text") or p.get("articleBody") or "").strip()
                if not texto:
                    continue
                autor = p.get("author") or {}
                posts.append({
                    "id": None,
                    "autor": autor.get("name") if isinstance(autor, dict) else str(autor),
                    "data": p.get("dateCreated") or p.get("datePublished"),
                    "texto": texto,
                })
    return posts


def ler_topico(html, url_atual):
    """Posts de uma página de tópico.

    Retorna (info, posts, url_proxima_pagina). info tem titulo; cada post tem
    id, autor, data (ISO) e texto, sem as citações de outros posts.
    """
    soup = _soup(html)
    h1 = soup.find("h1")
    og = soup.find("meta", property="og:title")
    titulo = (h1.get_text(" ", strip=True) if h1 else None) or (og.get("content") if og else None)

    artigos = soup.select("article[id^='elComment_']") or soup.select("[data-commentid]")
    posts = []
    for art in artigos:
        conteudo = art.select_one("[data-role='commentContent']") or art.select_one(".ipsType_richText, .ipsRichText")
        if not conteudo:
            continue
        pid = art.get("data-commentid") or re.sub(r"\D", "", art.get("id", "")) or None
        quando = art.find("time")
        posts.append({
            "id": int(pid) if pid else None,
            "autor": _autor(art),
            "data": quando.get("datetime") if quando else None,
            "texto": _texto_limpo(conteudo),
        })
    if not posts:
        posts = _posts_json_ld(soup)
    return {"titulo": titulo}, posts, proxima_pagina(soup, url_atual)
