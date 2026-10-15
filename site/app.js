(() => {
  const POR_PAGINA = 20;
  const $ = (id) => document.getElementById(id);
  const semAcento = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const PARADAS = new Set(['de', 'da', 'do', 'das', 'dos', 'e', 'a', 'o', 'as', 'os', 'em', 'no', 'na', 'para', 'pra', 'com', 'que', 'um', 'uma', 'por', 'se', 'ou']);
  // "250 mg", "250mg" e "250MG" viram o mesmo termo.
  const tokenizar = (texto) => texto.replace(/(\d+)\s*mg\b/gi, '$1mg').split(/[^\p{L}\p{N}]+/u).filter(Boolean);
  const escapar = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  let topicos = [], indice, temasAtivos = new Set(), lista = [], mostrados = 0;

  const indexar = () => {
    indice = new MiniSearch({
      fields: ['titulo', 'texto'],
      storeFields: ['id'],
      tokenize: tokenizar,
      processTerm: (t) => (t.length < 2 || PARADAS.has(semAcento(t)) ? null : semAcento(t)),
      // Erros de digitação só em palavras longas e sem números ("250mg" não vira "200mg", "testo" não vira "teste").
      searchOptions: {
        boost: { titulo: 3 }, combineWith: 'AND',
        prefix: (termo) => !/\d/.test(termo),
        fuzzy: (termo) => (termo.length > 5 && !/\d/.test(termo) ? 0.2 : false),
      },
    });
    indice.addAll(topicos);
  };

  const trecho = (t, termos) => {
    const texto = t.texto.replace(/\s+/g, ' ').replace(/(\d+)\s*mg\b/gi, '$1mg');
    const norm = semAcento(texto);
    let pos = -1;
    for (const termo of termos) { pos = norm.indexOf(termo); if (pos >= 0) break; }
    const ini = Math.max(0, pos - 80);
    let s = (ini > 0 ? '… ' : '') + texto.slice(ini, ini + 280) + (texto.length > ini + 280 ? ' …' : '');
    s = escapar(s);
    if (!termos.length) return s;
    // Marca os termos ignorando acentos: percorre o texto normalizado em paralelo.
    const alvo = semAcento(s);
    const re = new RegExp(termos.map((x) => x.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')).join('|'), 'g');
    let out = '', ultimo = 0, m;
    while ((m = re.exec(alvo))) {
      if (!m[0]) { re.lastIndex++; continue; }
      out += s.slice(ultimo, m.index) + '<mark>' + s.slice(m.index, m.index + m[0].length) + '</mark>';
      ultimo = m.index + m[0].length;
    }
    return out + s.slice(ultimo);
  };

  const buscar = () => {
    const q = $('q').value.trim();
    const forum = $('forum').value;
    let res;
    if (q) {
      res = indice.search(q).map((r) => ({ t: topicos[r.id], score: r.score, termos: r.terms }));
      if (!res.length) res = indice.search(q, { combineWith: 'OR' }).map((r) => ({ t: topicos[r.id], score: r.score, termos: r.terms }));
    } else {
      res = topicos.map((t) => ({ t, score: 0, termos: [] }));
    }
    res = res.filter(({ t }) => (!forum || t.forum === forum) && [...temasAtivos].every((x) => t.temas.includes(x)));
    const ordem = $('ordem').value;
    if (ordem === 'recentes' || (!q && ordem === 'relevancia')) res.sort((a, b) => (b.t.ultima || '').localeCompare(a.t.ultima || ''));
    if (ordem === 'respostas') res.sort((a, b) => b.t.respostas - a.t.respostas);
    lista = res; mostrados = 0;
    $('resultados').innerHTML = '';
    $('contagem').textContent = `${res.length.toLocaleString('pt-BR')} tópico${res.length === 1 ? '' : 's'}`;
    mostrar();
    const params = new URLSearchParams();
    if (q) params.set('q', q);
    if (forum) params.set('forum', forum);
    if (temasAtivos.size) params.set('temas', [...temasAtivos].join('|'));
    history.replaceState(null, '', params.toString() ? '?' + params : location.pathname);
  };

  const mostrar = () => {
    const html = lista.slice(mostrados, mostrados + POR_PAGINA).map(({ t, termos }) => `
      <li>
        <h2><a href="${escapar(t.url)}" target="_blank" rel="noopener">${escapar(t.titulo)}</a></h2>
        <div class="info"><span>${escapar(t.forum)}</span><span>${t.respostas} resposta${t.respostas === 1 ? '' : 's'}</span>${t.ultima ? `<span>última em ${t.ultima.split('-').reverse().join('/')}</span>` : ''}</div>
        <p class="trecho">${trecho(t, termos)}</p>
        ${t.temas.length ? `<div class="etiquetas">${t.temas.map((x) => `<span>${escapar(x)}</span>`).join('')}</div>` : ''}
      </li>`).join('');
    $('resultados').insertAdjacentHTML('beforeend', html);
    mostrados += POR_PAGINA;
    $('mais').hidden = mostrados >= lista.length;
  };

  const iniciar = async () => {
    const [dados, meta] = await Promise.all([
      fetch('dados/topicos.json').then((r) => r.json()),
      fetch('dados/meta.json').then((r) => r.json()),
    ]);
    topicos = dados.map((t, i) => ({ ...t, id: i, idForum: t.id }));
    indexar();
    const quando = new Date(meta.gerado_em).toLocaleDateString('pt-BR');
    $('meta').textContent = `${meta.topicos.toLocaleString('pt-BR')} tópicos e ${meta.posts.toLocaleString('pt-BR')} posts, atualizado em ${quando}.`;
    for (const f of meta.foruns) $('forum').insertAdjacentHTML('beforeend', `<option>${escapar(f)}</option>`);
    for (const tema of meta.temas) {
      const b = document.createElement('button');
      b.type = 'button'; b.textContent = tema; b.setAttribute('aria-pressed', 'false');
      b.onclick = () => {
        temasAtivos.has(tema) ? temasAtivos.delete(tema) : temasAtivos.add(tema);
        b.setAttribute('aria-pressed', String(temasAtivos.has(tema)));
        buscar();
      };
      $('temas').append(b);
    }
    const params = new URLSearchParams(location.search);
    $('q').value = params.get('q') || '';
    $('forum').value = params.get('forum') || '';
    for (const tema of (params.get('temas') || '').split('|').filter(Boolean)) {
      temasAtivos.add(tema);
      [...$('temas').children].find((b) => b.textContent === tema)?.setAttribute('aria-pressed', 'true');
    }
    let espera;
    $('q').addEventListener('input', () => { clearTimeout(espera); espera = setTimeout(buscar, 200); });
    $('forum').onchange = buscar;
    $('ordem').onchange = buscar;
    $('mais').onclick = mostrar;
    buscar();
  };

  // Faixas típicas de laboratório para homens adultos; variam entre laboratórios.
  const REFERENCIA = {
    'Testosterona total': '264–916', 'Testosterona livre': '5–21', 'Estradiol': '10–40', 'Hematócrito': '41–50',
    'Hemoglobina': '13,5–17,5', 'HDL': 'acima de 40', 'LDL': 'abaixo de 130', 'TGP / ALT': 'abaixo de 41',
    'PSA': 'abaixo de 2,5', 'LH': '1,7–8,6',
  };
  let analise;
  const fmt = (n) => (n === undefined ? '–' : Number(n).toLocaleString('pt-BR', { maximumFractionDigits: 1 }));

  const mostrarAnalise = () => {
    if (!analise) return;
    const g = $('grupo').value;
    const total = analise.posts_por_grupo[g] || 0;
    const p = analise.perfil, tol = analise.tolerancia;
    $('grupo-info').textContent = g === 'Perfil parecido'
      ? `${analise.autores_com_perfil_parecido} autores dizem ter ${p.idade} ± ${tol.idade} anos e ${p.peso_kg} ± ${tol.peso_kg} kg (e altura de ${p.altura_cm} ± ${tol.altura_cm} cm, quando informada); ${total} posts deles falam de testosterona ou ciclo.`
      : `${total.toLocaleString('pt-BR')} posts analisados neste grupo.`;
    const col = analise.colaterais[g] || [];
    const maior = Math.max(1, ...col.map((c) => c.posts));
    $('colaterais').innerHTML = col.length ? col.map((c) => `
      <li><div class="barra-topo"><span>${escapar(c.nome)}</span><span>${c.posts} post${c.posts === 1 ? '' : 's'}${total ? ` · ${Math.round((100 * c.posts) / total)}%` : ''}</span></div>
      <div class="barra"><span style="width:${(100 * c.posts) / maior}%"></span></div>
      <div class="exemplos">${(analise.exemplos_colaterais[c.nome] || []).slice(0, 3).map((e) => `<a href="${escapar(e.url)}" target="_blank" rel="noopener">${escapar(e.titulo)}</a>`).join(' · ')}</div></li>`).join('')
      : '<li class="sub">Ainda não há relatos suficientes neste grupo.</li>';
    const ex = Object.entries(analise.exames[g] || {}).sort((a, b) => b[1].n - a[1].n);
    $('exames').innerHTML = ex.length
      ? '<tr><th>Exame</th><th>Relatos</th><th>Mediana</th><th>Metade dos relatos entre</th><th>Referência típica</th></tr>' +
        ex.map(([nome, r]) => `<tr><td>${escapar(nome)}</td><td class="num">${r.n}</td><td class="num">${fmt(r.mediana)} ${r.unidade}</td>
          <td class="num">${r.p25 !== undefined ? `${fmt(r.p25)}–${fmt(r.p75)}` : 'poucos dados'}</td><td>${REFERENCIA[nome] || ''} ${r.unidade}</td></tr>`).join('')
      : '<tr><td class="sub">Nenhum valor de exame encontrado neste grupo.</td></tr>';
    const gk = analise.ganhos_kg[g];
    $('ganhos').textContent = gk && gk.n
      ? `${gk.n} relatos; mediana de ${fmt(gk.mediana)} kg${gk.p25 !== undefined ? ` (metade entre ${fmt(gk.p25)} e ${fmt(gk.p75)} kg)` : ''}. Ganho de peso inclui água e gordura, não só músculo, e boa parte costuma ir embora depois que a dose cai.`
      : 'Nenhum relato de ganho em kg encontrado neste grupo.';
    $('doses').textContent = analise.doses_testosterona_mg.length
      ? analise.doses_testosterona_mg.map((d) => `${d.mg} mg (${d.mencoes})`).join(' · ') + ' — número de menções, sem distinguir dose semanal de aplicação única.'
      : 'Nenhuma dose encontrada.';
  };

  const abrirAba = (qual) => {
    $('aba-busca').setAttribute('aria-selected', String(qual === 'busca'));
    $('aba-analise').setAttribute('aria-selected', String(qual === 'analise'));
    $('painel-busca').hidden = qual !== 'busca';
    $('painel-analise').hidden = qual !== 'analise';
    if (qual === 'analise') mostrarAnalise();
  };
  $('aba-busca').onclick = () => abrirAba('busca');
  $('aba-analise').onclick = () => abrirAba('analise');
  $('grupo').onchange = mostrarAnalise;
  for (const b of document.querySelectorAll('.atalhos button')) {
    b.onclick = () => { $('q').value = b.dataset.q; if (indice) buscar(); };
  }
  fetch('dados/analise.json').then((r) => (r.ok ? r.json() : null)).then((a) => { analise = a; mostrarAnalise(); }).catch(() => {});
  if (location.hash === '#analise') abrirAba('analise');

  iniciar().catch((e) => {
    $('meta').textContent = 'Não foi possível carregar a base. Rode o workflow "Coletar e publicar" no GitHub Actions.';
    console.error(e);
  });
})();
