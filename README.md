# Hipertrofia: base de pesquisa do fórum

Ferramenta que roda inteira no GitHub para pesquisar o conteúdo público do
[fórum Hipertrofia.org](https://www.hipertrofia.org/forum/):

- **Coleta (GitHub Actions):** toda segunda-feira, ou quando você mandar, o workflow
  *Coletar e publicar* baixa os tópicos novos ou com respostas novas e guarda tudo
  numa base SQLite no branch `dados`.
- **Busca (GitHub Pages):** uma página com busca por palavras (ignora acentos e
  aceita palavras incompletas), filtro por subfórum e por tema (jiu-jitsu, CrossFit,
  treino concorrente, bulking, proteína, creatina, recuperação, hormônios…) e link
  para o tópico original. Entende "250mg" e "250 mg" como a mesma coisa.
- **Análise testosterona (aba da página):** a partir dos relatos sobre TRT e ciclos,
  mostra os colaterais mais citados, os valores de exames relatados (com a faixa
  típica de laboratório ao lado) e o ganho de peso relatado, separando reposição,
  ciclo e autores com perfil parecido com o definido em `perfil` no `config.json`.
  São relatos de fórum, sem confirmação de dose ou exame; servem para levar
  perguntas ao médico, não para definir protocolo.

## Como a coleta se comporta

- Lê o `robots.txt` do site e não acessa nada que ele bloqueia (perfis, busca etc.).
- Espera 2 segundos entre as requisições e se identifica pelo User-Agent.
- Os nomes de usuário viram um código anônimo (`u_3fa9…`) e as citações de outros
  posts são removidas do texto. Nenhum dado de perfil é coletado.
- É incremental: primeiro pega as novidades e depois continua o histórico de onde
  parou, até o limite de tópicos de cada execução (100 por padrão, alguns minutos).

Os subfóruns coletados e os temas ficam em [`config.json`](config.json). Hoje só o
subfórum de esteroides está ativo; os outros estão em `foruns_pausados` e voltam
para a coleta se forem movidos de volta para `foruns`.

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
python -m coletor.exportar && python -m coletor.analise && python -m http.server -d site
python -m pytest -q
```

Para pesquisar a base completa que está no GitHub:
`git fetch origin dados && git show FETCH_HEAD:forum.db.gz | gunzip > dados/forum.db`.

## Aviso

Relatos de fórum são experiências individuais, não evidência científica nem
orientação médica. Use a base para levantar perguntas e hipóteses e confira com
estudos e com profissionais.
