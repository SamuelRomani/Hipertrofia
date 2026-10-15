"""Marcação de temas por palavras-chave (definidas em config.json)."""
import re
import unicodedata


def normalizar(texto):
    sem_acento = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return sem_acento.lower()


def compilar(temas):
    return {
        nome: re.compile(r"\b(" + "|".join(re.escape(normalizar(p)) for p in palavras) + r")\b")
        for nome, palavras in temas.items()
    }


def detectar(texto, compilados):
    alvo = normalizar(texto)
    return [nome for nome, regex in compilados.items() if regex.search(alvo)]
