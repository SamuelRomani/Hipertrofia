# Hipertrofia: base de pesquisa do fórum

Ferramenta que roda inteira no GitHub para pesquisar o conteúdo público do
[fórum Hipertrofia.org](https://www.hipertrofia.org/forum/):

- **Coleta (GitHub Actions):** toda segunda-feira, ou quando você mandar, o workflow
  *Coletar e publicar* baixa os tópicos novos ou com respostas novas e guarda tudo
  numa base SQLite no branch `dados`.
- **Busca (GitHub Pages):** uma página com busca por palavras (ignora acentos e
  aceita palavras incompletas), filtro por subfórum e por tema (jiu-jitsu, CrossFit,
  treino concorrente, bulking, proteína, creatina, recuperação, hormônios…) e link
  para o tópico original.

## Como a coleta se comporta

- Lê o `robots.txt` do site e não acessa nada que ele bloqueia (perfis, busca etc.).
- Espera 2 segundos entre as requisições e se identifica pelo User-Agent.
- Os nomes de usuário viram um código anônimo (`u_3fa9…`) e as citações de outros
  posts são removidas do texto. Nenhum dado de perfil é coletado.
- É incremental: primeiro pega as novidades e depois continua o histórico de onde
  parou, até o limite de tópicos de cada execução (500 por padrão, cerca de 30 min).

Os subfóruns coletados e os temas ficam em [`config.json`](config.json).

## Primeira configuração

1. **Settings → Pages → Build and deployment → Source:** escolha **GitHub Actions**.
2. (Opcional) **Settings → Secrets and variables → Actions:** crie o segredo
   `SAL_ANONIMIZACAO` com qualquer texto aleatório, para que os códigos anônimos não
   possam ser recalculados a partir dos nomes.
3. **Actions → Coletar e publicar → Run workflow.** Rode algumas vezes para formar
   o histórico; depois a execução semanal mantém tudo atualizado.

A página fica em `https://<seu-usuario>.github.io/Hipertrofia/`.

## Uso local

```bash
pip install -r requirements.txt
python -m coletor.coletar --max-topicos 50       # coleta para dados/forum.db
python -m coletor.buscar '"treino concorrente" hipertrofia'
python -m coletor.exportar && python -m http.server -d site
python -m pytest -q
```

Para pesquisar a base completa que está no GitHub:
`git fetch origin dados && git show FETCH_HEAD:forum.db.gz | gunzip > dados/forum.db`.

## Aviso

Relatos de fórum são experiências individuais, não evidência científica nem
orientação médica. Use a base para levantar perguntas e hipóteses e confira com
estudos e com profissionais.
