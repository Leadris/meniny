// Single-page logic: one data file (data/names.json) plus the voting API.
// No framework and no build step, so a deploy is a plain file upload.
(() => {
  'use strict';
  const MONTHS = ['január', 'február', 'marec', 'apríl', 'máj', 'jún', 'júl',
    'august', 'september', 'október', 'november', 'december'];
  const MONTHS_GEN = ['januára', 'februára', 'marca', 'apríla', 'mája', 'júna', 'júla',
    'augusta', 'septembra', 'októbra', 'novembra', 'decembra'];
  const LIST_STEP = 25;
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat('sk-SK');

  let data = null;
  let votes = { days: {}, mine: {} };
  // 2024 is a leap year, so stepping through it visits 29 February as well.
  let shown = new Date(2024, new Date().getMonth(), new Date().getDate());
  const listSize = { dead: LIST_STEP, missing: LIST_STEP };

  const fold = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const keyOf = (d) => String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const dateLabel = (key) => Number(key.slice(3)) + '. ' + MONTHS_GEN[Number(key.slice(0, 2)) - 1];

  // The sample is ~12 % of the country, so the national figure is an estimate and is
  // rounded to two significant digits to avoid suggesting precision we do not have.
  function estimate(count) {
    const raw = count * data.meta.scale;
    const digits = Math.max(0, Math.floor(Math.log10(Math.max(raw, 1))) - 1);
    return Math.round(raw / 10 ** digits) * 10 ** digits;
  }
  function people(count) {
    if (count === 0) return 'nikto vo vzorke';
    return nf.format(count) + ' vo vzorke, asi ' + nf.format(estimate(count)) + ' na Slovensku';
  }
  function el(tag, cls, text) {
    const node = document.createElement(tag);
    if (cls) node.className = cls;
    if (text !== undefined) node.textContent = text;
    return node;
  }

  function renderDay() {
    const key = keyOf(shown);
    const day = data.days[key];
    $('day-month').textContent = MONTHS[shown.getMonth()];
    $('day-num').textContent = shown.getDate();
    $('day-title').textContent = day.current.length ? day.current.join(', ') : 'Bez mena v kalendári';
    const ballot = $('ballot');
    ballot.replaceChildren();
    if (!day.candidates.length) {
      $('day-hint').textContent = 'Na tento deň kalendár žiadne meno neuvádza.';
      return;
    }
    $('day-hint').textContent = 'Ktoré meno má byť v tento deň hlavné? Ťukni a hlasuj.';
    const tally = votes.days[key] || {};
    const top = Math.max(...day.candidates.map((c) => c[1]), 1);
    for (const [name, count] of day.candidates) {
      const button = el('button');
      button.type = 'button';
      if (votes.mine[key] === name) button.classList.add('mine');
      const fill = el('span', 'fill');
      fill.style.width = (100 * count / top) + '%';
      const label = el('span', 'name', name);
      if (day.current.includes(name)) label.append(el('span', 'tag', 'dnes hlavné'));
      const n = tally[name] || 0;
      const voteText = (votes.mine[key] === name ? '✓ ' : '') + n + (n === 1 ? ' hlas' : n >= 2 && n <= 4 ? ' hlasy' : ' hlasov');
      button.append(fill, label, el('span', 'votes', voteText), el('span', 'count', people(count)));
      button.addEventListener('click', () => castVote(key, name));
      const item = el('li');
      item.append(button);
      ballot.append(item);
    }
  }

  async function castVote(day, name) {
    const status = $('vote-status');
    status.className = 'status';
    status.textContent = 'Ukladám hlas…';
    try {
      const response = await fetch('api/vote.php', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ day, name }),
      });
      if (!response.ok) throw new Error(String(response.status));
      votes = await response.json();
      status.textContent = 'Hlas za meno ' + name + ' je zapísaný.';
    } catch (error) {
      status.className = 'status err';
      status.textContent = 'Hlas sa nepodarilo uložiť. Skús to o chvíľu znova.';
    }
    renderDay();
  }

  function showDay(date) {
    shown = date;
    $('vote-status').textContent = '';
    renderDay();
  }

  function renderSearch() {
    const query = fold($('q').value.trim());
    const box = $('result');
    box.replaceChildren();
    if (query.length < 2) return;
    const hits = data.names.filter((n) => fold(n[0]).startsWith(query)).slice(0, 5);
    if (!hits.length) {
      box.append(el('p', '', 'Také meno má vo vzorke menej než 3 ľudia, alebo ho nemá nikto.'));
      return;
    }
    for (const [name, count, status, date] of hits) {
      box.append(el('p', 'big', name + ': ' + people(count)));
      const line = el('p', 'hint');
      if (status === 'none') {
        line.textContent = 'V kalendári toto meno nie je.';
      } else {
        line.textContent = (status === 'main' ? 'Hlavné meno dňa ' : 'Vedľajšie meno dňa ') + dateLabel(date) + '. ';
        const jump = el('button', 'link', 'Otvoriť deň');
        jump.type = 'button';
        jump.addEventListener('click', () => {
          showDay(new Date(2024, Number(date.slice(0, 2)) - 1, Number(date.slice(3))));
          document.querySelector('.leaf').scrollIntoView({ behavior: 'smooth' });
        });
        line.append(jump);
      }
      box.append(line);
    }
  }

  function renderLists() {
    const lists = {
      dead: data.names.filter((n) => n[2] === 'main').sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0], 'sk')),
      missing: data.names.filter((n) => n[2] !== 'main'),
    };
    for (const id of Object.keys(lists)) {
      const target = $(id);
      target.replaceChildren();
      for (const [name, count, status, date] of lists[id].slice(0, listSize[id])) {
        const item = el('li');
        const label = el('span', 'n', name);
        const note = date ? dateLabel(date) : 'nie je v kalendári';
        label.append(el('span', 'd', note));
        item.append(label, el('span', 'c', count === 0 ? '0' : nf.format(count) + ' · asi ' + nf.format(estimate(count))));
        target.append(item);
      }
      document.querySelector('.more[data-list="' + id + '"]').hidden = listSize[id] >= lists[id].length;
    }
  }

  async function start() {
    data = await (await fetch('data/names.json')).json();
    $('about-data').textContent = 'Vzorka: ' + nf.format(data.meta.people) + ' obyvateľov z ' + data.meta.cities
      + ' slovenských miest (asi ' + Math.round(100 / data.meta.scale) + ' % Slovenska). Pri každom mene je počet vo vzorke a odhad za celé Slovensko.';
    renderDay();
    renderLists();
    // Votes load after the first paint; the page stays useful if the API is down.
    try {
      const response = await fetch('api/vote.php');
      if (response.ok) { votes = await response.json(); renderDay(); }
    } catch (error) { /* read-only mode */ }
  }

  $('prev').addEventListener('click', () => showDay(new Date(2024, shown.getMonth(), shown.getDate() - 1)));
  $('next').addEventListener('click', () => showDay(new Date(2024, shown.getMonth(), shown.getDate() + 1)));
  $('today').addEventListener('click', () => showDay(new Date(2024, new Date().getMonth(), new Date().getDate())));
  $('pick').addEventListener('change', (event) => {
    const parts = event.target.value.split('-').map(Number);
    if (parts.length === 3) showDay(new Date(2024, parts[1] - 1, parts[2]));
  });
  $('q').addEventListener('input', renderSearch);
  for (const button of document.querySelectorAll('.more')) {
    button.addEventListener('click', () => { listSize[button.dataset.list] += LIST_STEP; renderLists(); });
  }
  start();
})();
