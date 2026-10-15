from coletor import analise, db
from coletor.temas import normalizar

ALVO = {"idade": 29, "altura_cm": 173, "peso_kg": 80,
        "tolerancia": {"idade": 5, "altura_cm": 6, "peso_kg": 10}}


def test_extrai_exames_ganhos_e_perfil():
    t = normalizar("Tenho 30 anos, 1,75 e 82kg. Testosterona total: 1.150 ng/dL, hematócrito 52%, HDL 28. Ganhei 6 kg.")
    assert analise.perfil_do_texto(t) == {"idade": 30, "altura_cm": 175.0, "peso_kg": 82.0}
    ex = dict(analise.exames_do_texto(t))
    assert ex["Hematócrito"] == 52 and ex["HDL"] == 28
    assert analise.ganhos_do_texto(t) == [6.0]
    assert analise.ganhos_do_texto(normalizar("fui de 78 para 85kg")) == [7.0]


def test_analisar_separa_trt_de_ciclo(tmp_path):
    con = db.conectar(str(tmp_path / "a.db"))
    posts = [
        {"id": 1, "autor": "u_a", "data": None, "texto": "Tenho 29 anos e 80kg, faço TRT com 100mg de cipionato. Hematócrito 50, acne leve."},
        {"id": 2, "autor": "u_b", "data": None, "texto": "No ciclo de 500mg de testo deu ginecomastia e pressão alta. Ganhei 8kg."},
        {"id": 3, "autor": "u_c", "data": None, "texto": "Boa sorte!"},
    ]
    db.salvar_topico(con, {"id": 1, "forum_id": 16, "forum": "E", "titulo": "Dúvidas testosterona", "url": "u1",
                           "respostas": 2}, posts, "agora")
    r = analise.analisar(con, ALVO)
    col = {g: {c["nome"] for c in v} for g, v in r["colaterais"].items()}
    assert col["TRT"] == {"Acne / oleosidade"}
    assert col["Ciclo"] == {"Ginecomastia / sensibilidade no mamilo", "Pressão alta"}
    assert col["Perfil parecido"] == {"Acne / oleosidade"}
    assert r["exames"]["TRT"]["Hematócrito"]["mediana"] == 50
    assert r["ganhos_kg"]["Ciclo"]["mediana"] == 8
    assert {d["mg"] for d in r["doses_testosterona_mg"]} == {100, 500}
    assert r["autores_com_perfil_parecido"] == 1
