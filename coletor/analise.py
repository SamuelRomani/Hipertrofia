"""Resumo dos relatos sobre testosterona (TRT e ciclos) para a aba de análise.

Conta colaterais citados, extrai valores de exames e ganhos de peso relatados nos
posts, separando reposição (TRT) de ciclo e destacando autores com perfil parecido
com o definido em config.json ("perfil"). São relatos de fórum, não dados clínicos.

Uso: python -m coletor.analise [--db dados/forum.db] [--saida site/dados]
"""
import argparse
import json
import os
import re
from collections import Counter, defaultdict
from statistics import median, quantiles

from . import db
from .temas import normalizar

TRT = re.compile(r"\b(trt|reposicao hormonal|reposicao de testosterona|terapia de reposicao|em reposicao)\b")
CICLO = re.compile(r"\b(ciclo|ciclando|durateston|deca|nandrolona|enantato|cipionato|oxandrolona|anavar|"
                   r"trembolona|boldenona|stanozolol|winstrol|hemogenin|oximetolona|anabolizantes?|esteroides?)\b")
TESTO = re.compile(r"\b(testo|testosterona|durateston|enantato|cipionato|trt)\b")
DOSE = re.compile(r"\b(\d{2,4})\s*mg\b")

COLATERAIS = {
    "Acne / oleosidade": ["acne", "espinha", "espinhas", "oleosidade", "pele oleosa"],
    "Hematócrito / hemoglobina alta": ["hematocrito alto", "hematocrito elevado", "hematocrito subiu",
                                       "hemoglobina alta", "policitemia", "sangue grosso", "sangria", "doacao de sangue"],
    "Ginecomastia / sensibilidade no mamilo": ["ginecomastia", "gino", "mamilo", "caroco no peito"],
    "Estradiol alto / retenção": ["estradiol alto", "e2 alto", "retencao", "inchaco", "inchado"],
    "Queda de cabelo / calvície": ["queda de cabelo", "calvicie", "cabelo caindo", "entradas"],
    "Pressão alta": ["pressao alta", "hipertensao", "pressao subiu", "pressao arterial"],
    "Colesterol (HDL baixo / LDL alto)": ["hdl baixo", "ldl alto", "colesterol", "perfil lipidico"],
    "Supressão do eixo / atrofia testicular": ["supressao", "eixo", "atrofia", "testiculo", "testiculos", "tpc", "pos ciclo"],
    "Libido / disfunção erétil": ["libido", "disfuncao eretil", "brochar", "brochei", "impotencia", "ereção"],
    "Insônia": ["insonia", "nao consigo dormir", "sono ruim"],
    "Humor / irritabilidade / ansiedade": ["irritabilidade", "irritado", "agressividade", "agressivo", "ansiedade", "depressao", "humor"],
    "Fígado (TGO/TGP)": ["figado", "hepatico", "hepatotox", "tgo", "tgp", "transaminases"],
    "Fertilidade / espermograma": ["fertilidade", "infertil", "espermograma", "azoospermia"],
    "Coração / palpitação": ["palpitacao", "taquicardia", "arritmia", "cardiaco", "hipertrofia cardiaca", "infarto"],
}
COLATERAIS_RE = {nome: re.compile(r"\b(" + "|".join(re.escape(normalizar(p)) for p in palavras) + r")\b")
                 for nome, palavras in COLATERAIS.items()}

_NUM = r"(\d{1,4}(?:[.,]\d{1,2})?)"
EXAMES = {
    # nome: (regex, unidade, mínimo plausível, máximo plausível)
    "Testosterona total": (r"testosterona total[^\d\n]{0,25}" + _NUM, "ng/dL", 30, 3000),
    "Testosterona livre": (r"testosterona livre[^\d\n]{0,25}" + _NUM, "ng/dL", 0.5, 100),
    "Estradiol": (r"\b(?:estradiol|e2)\b[^\d\n]{0,20}" + _NUM, "pg/mL", 5, 400),
    "Hematócrito": (r"hematocrito[^\d\n]{0,20}" + _NUM, "%", 30, 65),
    "Hemoglobina": (r"hemoglobina[^\d\n]{0,20}" + _NUM, "g/dL", 9, 22),
    "HDL": (r"\bhdl\b[^\d\n]{0,20}" + _NUM, "mg/dL", 5, 120),
    "LDL": (r"\bldl\b[^\d\n]{0,20}" + _NUM, "mg/dL", 20, 350),
    "TGP / ALT": (r"\b(?:tgp|alt)\b[^\d\n]{0,20}" + _NUM, "U/L", 5, 500),
    "PSA": (r"\bpsa\b[^\d\n]{0,20}" + _NUM, "ng/mL", 0, 20),
    "LH": (r"\blh\b[^\d\n]{0,20}" + _NUM, "mUI/mL", 0, 40),
}
EXAMES_RE = {nome: (re.compile(r), u, lo, hi) for nome, (r, u, lo, hi) in EXAMES.items()}

GANHO_RE = [
    re.compile(r"\b(?:ganhei|ganho de|subi|engordei)\s+(?:uns\s+|quase\s+|cerca de\s+)?(\d{1,2}(?:[.,]\d)?)\s*(?:kg|quilos|kilos)\b"),
    re.compile(r"\bde\s+(\d{2,3}(?:[.,]\d)?)\s*(?:kg)?\s+(?:para|pra|p/)\s+(\d{2,3}(?:[.,]\d)?)\s*kg\b"),
]
IDADE_RE = re.compile(r"\b(\d{2})\s*anos\b")
ALTURA_RE = re.compile(r"\b(1[,.]\d{2})\s*m?\b|\b(1[5-9]\d|20\d)\s*cm\b")
PESO_RE = re.compile(r"\b(\d{2,3}(?:[.,]\d)?)\s*(?:kg|quilos)\b")


def _num(txt):
    return float(txt.replace(",", "."))


def perfil_do_texto(t):
    """Idade, altura (cm) e peso (kg) que o autor diz ter, quando aparecem no post."""
    p = {}
    if m := IDADE_RE.search(t):
        if 16 <= int(m.group(1)) <= 70:
            p["idade"] = int(m.group(1))
    if m := ALTURA_RE.search(t):
        cm = _num(m.group(1)) * 100 if m.group(1) else float(m.group(2))
        if 150 <= cm <= 210:
            p["altura_cm"] = cm
    if m := PESO_RE.search(t):
        if 45 <= _num(m.group(1)) <= 160:
            p["peso_kg"] = _num(m.group(1))
    return p


def parecido(perfil, alvo):
    tol = alvo["tolerancia"]
    campos = [c for c in ("idade", "altura_cm", "peso_kg") if c in perfil]
    if "idade" not in campos or "peso_kg" not in campos:
        return False
    return all(abs(perfil[c] - alvo[c]) <= tol[c] for c in campos)


def exames_do_texto(t):
    achados = []
    for nome, (regex, unidade, lo, hi) in EXAMES_RE.items():
        for m in regex.finditer(t):
            v = _num(m.group(1))
            if lo <= v <= hi:
                achados.append((nome, v))
    return achados


def ganhos_do_texto(t):
    ganhos = []
    for m in GANHO_RE[0].finditer(t):
        v = _num(m.group(1))
        if 0.5 <= v <= 30:
            ganhos.append(v)
    for m in GANHO_RE[1].finditer(t):
        v = _num(m.group(2)) - _num(m.group(1))
        if 0.5 <= v <= 30:
            ganhos.append(round(v, 1))
    return ganhos


def resumo(valores):
    if not valores:
        return {"n": 0}
    r = {"n": len(valores), "mediana": round(median(valores), 1),
         "min": min(valores), "max": max(valores)}
    if len(valores) >= 4:
        q = quantiles(valores, n=4)
        r["p25"], r["p75"] = round(q[0], 1), round(q[2], 1)
    return r


def analisar(con, alvo):
    grupos = ("TRT", "Ciclo", "Perfil parecido")
    colaterais = {g: Counter() for g in grupos}
    exemplos_col = defaultdict(list)
    exames = {g: defaultdict(list) for g in grupos}
    ganhos = {g: [] for g in grupos}
    doses = Counter()
    perfis = {}
    posts_por_grupo = Counter()

    linhas = con.execute(
        "SELECT p.texto, p.autor, t.id, t.titulo, t.url FROM posts p JOIN topicos t ON t.id = p.topico_id "
        "ORDER BY p.topico_id, p.posicao"
    ).fetchall()
    # Primeiro passo: perfil autodeclarado de cada autor (primeira menção de cada campo).
    for r in linhas:
        if r["autor"]:
            p = perfis.setdefault(r["autor"], {})
            for k, v in perfil_do_texto(normalizar(r["texto"])).items():
                p.setdefault(k, v)
    parecidos = {a for a, p in perfis.items() if parecido(p, alvo)}

    contexto_topico = {}
    for r in linhas:
        t = normalizar(r["texto"])
        tid = r["id"]
        if tid not in contexto_topico:
            titulo = normalizar(r["titulo"])
            contexto_topico[tid] = (bool(TRT.search(titulo + " " + t)), bool(CICLO.search(titulo + " " + t)))
        trt_top, ciclo_top = contexto_topico[tid]
        fala_trt, fala_ciclo = bool(TRT.search(t)), bool(CICLO.search(t))
        # O post decide pelo que ele mesmo diz; sem menção, herda o assunto do tópico.
        trt = fala_trt or (trt_top and not fala_ciclo)
        ciclo = (fala_ciclo and not fala_trt) or (ciclo_top and not trt_top and bool(TESTO.search(t)))
        if not (trt or ciclo or TESTO.search(t)):
            continue
        meus = [g for g, ok in (("TRT", trt), ("Ciclo", ciclo), ("Perfil parecido", r["autor"] in parecidos)) if ok]
        if not meus:
            continue
        for m in DOSE.finditer(t):
            janela = t[max(0, m.start() - 40): m.end() + 40]
            if TESTO.search(janela):
                doses[int(m.group(1))] += 1
        achados_col = [nome for nome, rx in COLATERAIS_RE.items() if rx.search(t)]
        achados_ex = exames_do_texto(t)
        achados_ganho = ganhos_do_texto(t)
        for g in meus:
            posts_por_grupo[g] += 1
            colaterais[g].update(achados_col)
            for nome, v in achados_ex:
                exames[g][nome].append(v)
            ganhos[g].extend(achados_ganho)
        for nome in achados_col:
            if len(exemplos_col[nome]) < 5 and all(e["url"] != r["url"] for e in exemplos_col[nome]):
                exemplos_col[nome].append({"titulo": r["titulo"], "url": r["url"]})

    return {
        "perfil": {k: alvo[k] for k in ("idade", "altura_cm", "peso_kg")},
        "tolerancia": alvo["tolerancia"],
        "autores_com_perfil_parecido": len(parecidos),
        "posts_por_grupo": dict(posts_por_grupo),
        "doses_testosterona_mg": [{"mg": mg, "mencoes": n} for mg, n in doses.most_common(12)],
        "colaterais": {g: [{"nome": n, "posts": c} for n, c in colaterais[g].most_common()] for g in grupos},
        "exemplos_colaterais": exemplos_col,
        "exames": {g: {nome: dict(resumo(v), unidade=EXAMES[nome][1]) for nome, v in exames[g].items()} for g in grupos},
        "ganhos_kg": {g: resumo(ganhos[g]) for g in grupos},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--config", default="config.json")
    ap.add_argument("--db", default="dados/forum.db")
    ap.add_argument("--saida", default="site/dados")
    args = ap.parse_args(argv)
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    resultado = analisar(db.conectar(args.db), config["perfil"])
    os.makedirs(args.saida, exist_ok=True)
    with open(os.path.join(args.saida, "analise.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=1)
    print(f"Análise gerada: {resultado['posts_por_grupo']}")


if __name__ == "__main__":
    main()
