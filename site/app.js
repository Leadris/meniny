// Single-page logic: one data file (data/names.json) plus the voting API.
// No framework and no build step, so a deploy is a plain file upload.
(() => {
  'use strict';
  const MONTHS = ['január', 'február', 'marec', 'apríl', 'máj', 'jún', 'júl',
    'august', 'september', 'október', 'november', 'december'];
  const MONTHS_GEN = ['januára', 'februára', 'marca', 'apríla', 'mája', 'júna', 'júla',
    'augusta', 'septembra', 'októbra', 'novembra', 'decembra'];
  const LIST_STEP = 25;
  const QUIZ_POOL = 300;   // well-known names only, so the guess is about intuition, not trivia
  const $ = (id) => document.getElementById(id);
  const nf = new Intl.NumberFormat('sk-SK');

  let data = null;
  let votes = { days: {}, mine: {} };
  // 2024 is a leap year, so stepping through it visits 29 February as well.
  let shown = new Date(2024, new Date().getMonth(), new Date().getDate());
  const listSize = { dead: LIST_STEP, missing: LIST_STEP };
  let quiz = { pair: null, streak: 0, best: 0 };

  const fold = (s) => s.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
  const keyOf = (d) => String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const dateOf = (key) => new Date(2024, Number(key.slice(0, 2)) - 1, Number(key.slice(3)));
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
  function button(cls, text, onClick) {
    const node = el('button', cls, text);
    node.type = 'button';
    node.addEventListener('click', onClick);
    return node;
  }
  function votesLabel(n) {
    return n + (n === 1 ? ' hlas' : n >= 2 && n <= 4 ? ' hlasy' : ' hlasov');
  }

  // ---- day card and voting -------------------------------------------------
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
    $('day-hint').textContent = 'Ktoré meno si tento deň zaslúži najviac? Ťukni a hlasuj.';
    const tally = votes.days[key] || {};
    const top = Math.max(...day.candidates.map((c) => c[1]), 1);
    for (const [name, count, official] of day.candidates) {
      const mine = votes.mine[key] === name;
      const item = button(mine ? 'mine' : '', undefined, () => castVote(key, name));
      const fill = el('span', 'fill');
      fill.style.width = (100 * count / top) + '%';
      const label = el('span', 'name', name);
      label.append(el('span', official ? 'tag' : 'tag new', official ? 'v kalendári' : 'návrh na doplnenie'));
      item.append(fill, label, el('span', 'votes', (mine ? '✓ ' : '') + votesLabel(tally[name] || 0)),
        el('span', 'count', people(count)));
      const row = el('li');
      row.append(item);
      ballot.append(row);
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
      status.textContent = 'Hlas za meno ' + name + ' je zapísaný. Šípkou prejdi na ďalší deň.';
    } catch (error) {
      status.className = 'status err';
      status.textContent = 'Hlas sa nepodarilo uložiť. Skús to o chvíľu znova.';
    }
    renderDay();
  }

  function showDay(date, scroll) {
    shown = date;
    $('vote-status').textContent = '';
    renderDay();
    if (scroll) document.querySelector('.leaf').scrollIntoView({ behavior: 'smooth' });
  }

  // ---- name card -----------------------------------------------------------
  function tier(count) {
    const n = count === 0 ? 0 : estimate(count);
    if (n === 0) return ['Meno z legiend', 'Vo vzorke ho nenosí nikto.'];
    if (n < 100) return ['Unikát', 'Na Slovensku by ste sa zmestili do jedného autobusu.'];
    if (n < 1000) return ['Vzácne meno', 'Na ulici zrejme nestretneš menovca celý rok.'];
    if (n < 10000) return ['Nevšedné meno', 'Menovcov máš, ale v triede si bol asi jediný.'];
    if (n < 50000) return ['Bežné meno', 'V každej väčšej firme sedí aspoň jeden menovec.'];
    return ['Slovenská klasika', 'Keď na ulici zavoláš svoje meno, otočí sa pol námestia.'];
  }

  function nameCard(entry) {
    const [name, count, status, date, close] = entry;
    const rank = data.names.indexOf(entry) + 1;
    const [title, quip] = tier(count);
    const card = el('div', 'card');
    card.append(el('p', 'card-tier', title), el('p', 'card-name', name), el('p', 'card-count', people(count)));
    if (count > 0) card.append(el('p', 'hint', rank + '. najčastejšie meno vo vzorke. ' + quip));
    else card.append(el('p', 'hint', quip));

    const line = el('p', 'card-day');
    let target = null;
    if (status === 'official') {
      line.textContent = 'Meniny podľa oficiálneho kalendára: ' + dateLabel(date) + '. ';
      target = date;
    } else if (close) {
      line.textContent = 'V oficiálnom kalendári v tejto podobe nie je. Najbližšie je ' + close[0] + ', ' + dateLabel(close[1]) + '. ';
      target = status === 'customary' ? date : close[1];
    } else if (status === 'customary') {
      line.textContent = 'V oficiálnom kalendári nie je. Zvykne sa sláviť ' + dateLabel(date) + '. ';
      target = date;
    } else {
      line.textContent = 'V kalendári nie je a nemá ani zaužívaný deň.';
    }
    if (target) line.append(button('link', 'Otvoriť deň', () => showDay(dateOf(target), true)));
    card.append(line);

    const shareText = name + ': ' + (count === 0 ? 'vo vzorke ho nenosí nikto' : 'asi ' + nf.format(estimate(count)) + ' ľudí na Slovensku')
      + '. Ako je na tom tvoje meno?';
    const url = location.origin + location.pathname + '?meno=' + encodeURIComponent(name);
    card.append(button('share', 'Poslať ďalej', async (event) => {
      try {
        if (navigator.share) await navigator.share({ title: 'Meniny', text: shareText, url });
        else {
          await navigator.clipboard.writeText(shareText + ' ' + url);
          event.target.textContent = 'Odkaz je skopírovaný';
        }
      } catch (error) { /* the visitor closed the share sheet */ }
    }));
    return card;
  }

  function renderSearch() {
    const query = fold($('q').value.trim());
    const box = $('result');
    box.replaceChildren();
    if (query.length < 2) return;
    const exact = data.names.find((n) => fold(n[0]) === query);
    const hits = exact ? [exact] : data.names.filter((n) => fold(n[0]).startsWith(query)).slice(0, 3);
    if (!hits.length) {
      box.append(el('p', '', 'Také meno má vo vzorke menej než 3 ľudia, alebo ho nemá nikto. Si skutočný unikát.'));
      return;
    }
    for (const entry of hits) box.append(nameCard(entry));
  }

  // ---- guessing game -------------------------------------------------------
  function nextPair() {
    const pool = data.names.slice(0, QUIZ_POOL);
    let a, b;
    do {
      a = pool[Math.floor(Math.random() * pool.length)];
      b = pool[Math.floor(Math.random() * pool.length)];
      // Near-ties would make the answer feel arbitrary.
    } while (a === b || Math.max(a[1], b[1]) / Math.min(a[1], b[1]) < 1.25);
    quiz.pair = [a, b];
    renderQuiz(null);
  }

  function renderQuiz(picked) {
    const box = $('quiz');
    box.replaceChildren();
    const [a, b] = quiz.pair;
    const winner = a[1] > b[1] ? a : b;
    for (const entry of quiz.pair) {
      const option = button('quiz-option', undefined, () => {
        if (picked) return;
        quiz.streak = entry === winner ? quiz.streak + 1 : 0;
        quiz.best = Math.max(quiz.best, quiz.streak);
        try { localStorage.setItem('meniny-best', String(quiz.best)); } catch (error) { /* private mode */ }
        renderQuiz(entry);
      });
      option.append(el('span', 'name', entry[0]));
      if (picked) {
        option.append(el('span', 'count', 'asi ' + nf.format(estimate(entry[1]))));
        option.classList.add(entry === winner ? 'right' : 'wrong');
        option.disabled = true;
      }
      box.append(option);
    }
    const note = $('quiz-note');
    if (!picked) note.textContent = 'Séria: ' + quiz.streak + ' · rekord: ' + quiz.best;
    else {
      note.textContent = (picked === winner ? 'Správne! ' : 'Vedľa. ') + 'Séria: ' + quiz.streak + ' · rekord: ' + quiz.best + ' ';
      note.append(button('link', 'Ďalšia dvojica', nextPair));
    }
  }

  // ---- lists ---------------------------------------------------------------
  function renderLists() {
    const lists = {
      dead: data.names.filter((n) => n[2] === 'official').sort((a, b) => a[1] - b[1] || a[0].localeCompare(b[0], 'sk')),
      missing: data.names.filter((n) => n[2] !== 'official'),
    };
    for (const id of Object.keys(lists)) {
      const target = $(id);
      target.replaceChildren();
      for (const [name, count, status, date, close] of lists[id].slice(0, listSize[id])) {
        const item = el('li');
        const label = el('span', 'n', name);
        const note = status === 'official' ? dateLabel(date) : close ? 'ako ' + close[0] : status === 'customary' ? 'zvykom ' + dateLabel(date) : 'bez dňa';
        label.append(el('span', 'd', note));
        item.append(label, el('span', 'c', count === 0 ? '0' : 'asi ' + nf.format(estimate(count))));
        target.append(item);
      }
      document.querySelector('.more[data-list="' + id + '"]').hidden = listSize[id] >= lists[id].length;
    }
  }

  async function start() {
    data = await (await fetch('data/names.json')).json();
    $('covered').textContent = String(Math.round(data.meta.covered));
    $('about-data').textContent = 'Vzorka: ' + nf.format(data.meta.people) + ' obyvateľov z ' + data.meta.cities
      + ' slovenských miest (asi ' + Math.round(100 / data.meta.scale) + ' % Slovenska). Pri každom mene je počet vo vzorke a odhad za celé Slovensko.';
    try { quiz.best = Number(localStorage.getItem('meniny-best')) || 0; } catch (error) { /* private mode */ }

    // Deep links let people send a name or a day to a friend.
    const params = new URLSearchParams(location.search);
    if (/^\d\d-\d\d$/.test(params.get('den') || '') && data.days[params.get('den')]) shown = dateOf(params.get('den'));
    renderDay();
    renderLists();
    nextPair();
    if (params.get('meno')) {
      $('q').value = params.get('meno');
      renderSearch();
      $('search-title').scrollIntoView();
    }
    // Votes load after the first paint; the page stays useful if the API is down.
    try {
      const response = await fetch('api/vote.php');
      if (response.ok) { votes = await response.json(); renderDay(); }
    } catch (error) { /* read-only mode */ }
  }

  const today = () => new Date(2024, new Date().getMonth(), new Date().getDate());
  $('prev').addEventListener('click', () => showDay(new Date(2024, shown.getMonth(), shown.getDate() - 1)));
  $('next').addEventListener('click', () => showDay(new Date(2024, shown.getMonth(), shown.getDate() + 1)));
  $('today').addEventListener('click', () => showDay(today()));
  $('pick').addEventListener('change', (event) => {
    const parts = event.target.value.split('-').map(Number);
    if (parts.length === 3) showDay(new Date(2024, parts[1] - 1, parts[2]));
  });
  $('q').addEventListener('input', renderSearch);
  for (const more of document.querySelectorAll('.more')) {
    more.addEventListener('click', () => { listSize[more.dataset.list] += LIST_STEP; renderLists(); });
  }
  start();
})();
