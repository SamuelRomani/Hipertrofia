(() => {
  const POR_PAGINA = 20;
  const $ = (id) => document.getElementById(id);
  const semAcento = (s) => s.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase();
  const escapar = (s) => s.replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

  let topicos = [], indice, temasAtivos = new Set(), lista = [], mostrados = 0;

  const indexar = () => {
    indice = new MiniSearch({
      fields: ['titulo', 'texto'],
      storeFields: ['id'],
      processTerm: (t) => (t.length < 2 ? null : semAcento(t)),
      searchOptions: { boost: { titulo: 3 }, prefix: true, fuzzy: 0.15, combineWith: 'AND' },
    });
    indice.addAll(topicos);
  };

  const trecho = (t, termos) => {
    const texto = t.texto.replace(/\s+/g, ' ');
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

  iniciar().catch((e) => {
    $('meta').textContent = 'Não foi possível carregar a base. Rode o workflow "Coletar e publicar" no GitHub Actions.';
    console.error(e);
  });
})();
