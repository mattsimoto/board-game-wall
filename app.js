const state = { games: [], view: 'rank', period: '1' };
const wall = document.querySelector('#gameWall');
const count = document.querySelector('#gameCount');
const empty = document.querySelector('#emptyState');
const category = document.querySelector('#categoryFilter');
const players = document.querySelector('#playersFilter');
const age = document.querySelector('#ageFilter');
const time = document.querySelector('#timeFilter');
const dialog = document.querySelector('#gameDialog');
const dialogContent = document.querySelector('#dialogContent');

const escapeHtml = value => String(value ?? '').replace(/[&<>'\"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','\"':'&quot;'}[c]));

function movementKey(period = state.period) {
  return `rankChange${period}`;
}
function movementValue(game, period = state.period) {
  const value = game[movementKey(period)];
  return Number.isFinite(value) ? value : null;
}
function movementClass(delta) {
  if (delta === null) return 'flat';
  if (delta > 0) return 'up';
  if (delta < 0) return 'down';
  return 'flat';
}
function movementLabel(delta) {
  if (delta === null) return '—';
  if (delta > 0) return `▲ ${delta}`;
  if (delta < 0) return `▼ ${Math.abs(delta)}`;
  return '• 0';
}
function movementPeriodLabel(period = state.period) {
  return `${period}D`;
}
function playerLabel(game) {
  return game.minPlayers === game.maxPlayers ? `${game.minPlayers}` : `${game.minPlayers}–${game.maxPlayers}`;
}
function timeLabel(game) {
  if (!game.minPlayTime && !game.maxPlayTime) return '—';
  if (game.minPlayTime === game.maxPlayTime) return `${game.maxPlayTime}m`;
  return `${game.minPlayTime}–${game.maxPlayTime}m`;
}
function cardSize(game, index) {
  if (state.view !== 'rank') {
    const delta = movementValue(game);
    const magnitude = Math.abs(delta || 0);
    if (index === 0 || magnitude >= 30) return 'size-hero';
    if (index < 3 || magnitude >= 18) return 'size-xl';
    if (index < 8 || magnitude >= 10) return 'size-lg';
    if (index < 24 || magnitude >= 4) return 'size-md';
    return 'size-sm';
  }
  if (game.rank === 1) return 'size-hero';
  if (game.rank <= 3) return 'size-xl';
  if (game.rank <= 8) return 'size-lg';
  if (game.rank <= 24) return 'size-md';
  return 'size-sm';
}
function matches(game) {
  if (category.value !== 'all' && !(game.categories || []).includes(category.value)) return false;
  if (players.value !== 'all') {
    const p = Number(players.value);
    if (p === 6 ? game.maxPlayers < 6 : p < game.minPlayers || p > game.maxPlayers) return false;
  }
  if (age.value !== 'all' && game.minAge > Number(age.value)) return false;
  if (time.value !== 'all') {
    const t = Number(time.value);
    if (t === 30 && game.maxPlayTime > 30) return false;
    if (t === 60 && (game.maxPlayTime <= 30 || game.minPlayTime > 60)) return false;
    if (t === 120 && (game.maxPlayTime <= 60 || game.minPlayTime > 120)) return false;
    if (t === 121 && game.maxPlayTime <= 120) return false;
  }
  return true;
}
function compareNullableMovement(a, b, direction) {
  const av = movementValue(a);
  const bv = movementValue(b);
  if (av === null && bv === null) return a.rank - b.rank;
  if (av === null) return 1;
  if (bv === null) return -1;
  return direction * (av - bv) || a.rank - b.rank;
}
function hotScore(game) {
  const delta = movementValue(game) || 0;
  return Math.max(0, 100 - Math.min(game.rank, 100)) + Math.max(0, delta * 2);
}
function sortGames(games) {
  const copy = [...games];
  if (state.view === 'climbers') return copy.sort((a,b) => compareNullableMovement(a,b,-1));
  if (state.view === 'fallers') return copy.sort((a,b) => compareNullableMovement(a,b,1));
  if (state.view === 'hot') return copy.sort((a,b) => hotScore(b) - hotScore(a) || a.rank - b.rank);
  return copy.sort((a,b) => a.rank - b.rank);
}
function render() {
  const filtered = state.games.filter(matches);
  const games = sortGames(filtered);
  const hasMovement = games.some(game => movementValue(game) !== null);

  count.textContent = games.length;
  empty.hidden = games.length > 0;
  if (!games.length) {
    empty.textContent = 'No games match those filters.';
  } else if ((state.view === 'climbers' || state.view === 'fallers') && !hasMovement) {
    empty.hidden = false;
    empty.textContent = `${movementPeriodLabel()} movement is still collecting history.`;
  }

  wall.innerHTML = games.map((game, index) => {
    const tileImage = escapeHtml(game.thumbnail || game.image);
    const delta = movementValue(game);
    const historyTitle = delta === null
      ? `${movementPeriodLabel()} movement is not available yet`
      : `${movementPeriodLabel()} rank movement`;
    return `
    <article class="game-card ${cardSize(game,index)}" data-id="${game.id}" tabindex="0" role="button" aria-label="${escapeHtml(game.name)}, BoardGameGeek rank ${game.rank}">
      <div class="cover-stage" aria-hidden="true">
        <img class="cover-backdrop" src="${tileImage}" alt="" loading="lazy" referrerpolicy="no-referrer" />
        <img class="cover-art" src="${tileImage}" alt="" loading="lazy" referrerpolicy="no-referrer" />
      </div>
      <span class="sr-only">${escapeHtml(game.name)} box cover</span>
      <div class="card-top">
        <span class="rank-badge">#${game.rank}</span>
        <span class="movement ${movementClass(delta)}" title="${historyTitle}">${movementLabel(delta)}</span>
      </div>
      <div class="card-bottom">
        <div class="game-info">
          <div class="game-name">${escapeHtml(game.name)}</div>
          <div class="game-meta">
            <span title="Players">♟ ${playerLabel(game)}</span>
            <span title="Play time">◷ ${timeLabel(game)}</span>
            <span title="Minimum age">${game.minAge}+</span>
            ${game.rating ? `<span title="BGG rating">★ ${Number(game.rating).toFixed(1)}</span>` : ''}
          </div>
        </div>
      </div>
    </article>`;
  }).join('');
}
function movementDetail(g, period) {
  const delta = movementValue(g, period);
  return `<div class="detail"><span>${period}-day move</span><strong class="${movementClass(delta)}">${movementLabel(delta)}</strong></div>`;
}
function showGame(id) {
  const g = state.games.find(x => String(x.id) === String(id));
  if (!g) return;
  const activeDelta = movementValue(g);
  dialogContent.innerHTML = `<div class="dialog-layout">
    <div class="dialog-cover-stage">
      <img class="dialog-cover-backdrop" src="${escapeHtml(g.thumbnail || g.image)}" alt="" aria-hidden="true" />
      <img class="dialog-cover" src="${escapeHtml(g.image)}" alt="${escapeHtml(g.name)} box cover" />
    </div>
    <div class="dialog-copy">
      <div class="dialog-rank">BGG RANK #${g.rank} · <span class="${movementClass(activeDelta)}">${movementLabel(activeDelta)} / ${movementPeriodLabel()}</span></div>
      <h2>${escapeHtml(g.name)}</h2>
      <p>${escapeHtml(g.year || '')}${g.rating ? ` · ${Number(g.rating).toFixed(1)} BGG rating` : ''}</p>
      <div class="detail-grid">
        <div class="detail"><span>Players</span><strong>${playerLabel(g)}</strong></div>
        <div class="detail"><span>Age</span><strong>${g.minAge}+</strong></div>
        <div class="detail"><span>Play time</span><strong>${timeLabel(g)}</strong></div>
        ${movementDetail(g, '1')}
        ${movementDetail(g, '7')}
        ${movementDetail(g, '30')}
      </div>
      <p>${(g.categories || []).map(escapeHtml).join(' · ')}</p>
      <a class="bgg-link" href="https://boardgamegeek.com/boardgame/${g.id}" target="_blank" rel="noopener noreferrer">View on BoardGameGeek ↗</a>
    </div>
  </div>`;
  dialog.showModal();
}

wall.addEventListener('click', e => { const card = e.target.closest('.game-card'); if(card) showGame(card.dataset.id); });
wall.addEventListener('keydown', e => { const card = e.target.closest('.game-card'); if(card && (e.key==='Enter'||e.key===' ')){e.preventDefault();showGame(card.dataset.id);} });
document.querySelector('#closeDialog').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', e => { if(e.target === dialog) dialog.close(); });

for (const el of [category, players, age, time]) el.addEventListener('change', render);
document.querySelector('#viewControls').addEventListener('click', e => {
  const button = e.target.closest('button[data-view]'); if (!button) return;
  state.view = button.dataset.view;
  document.querySelectorAll('#viewControls button').forEach(b => b.classList.toggle('active', b === button));
  render();
});
document.querySelector('#periodControls').addEventListener('click', e => {
  const button = e.target.closest('button[data-period]'); if (!button) return;
  state.period = button.dataset.period;
  document.querySelectorAll('#periodControls button').forEach(b => b.classList.toggle('active', b === button));
  document.querySelector('#movementPeriodLabel').textContent = `${movementPeriodLabel()} movement`;
  render();
});
document.querySelector('#resetFilters').addEventListener('click', () => {
  category.value = players.value = age.value = time.value = 'all';
  state.view = 'rank';
  state.period = '1';
  document.querySelectorAll('#viewControls button').forEach(b => b.classList.toggle('active', b.dataset.view === 'rank'));
  document.querySelectorAll('#periodControls button').forEach(b => b.classList.toggle('active', b.dataset.period === '1'));
  document.querySelector('#movementPeriodLabel').textContent = '1D movement';
  render();
});

async function init() {
  try {
    const response = await fetch('data/games.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const payload = await response.json();
    state.games = payload.games || [];
    const cats = [...new Set(state.games.flatMap(g => g.categories || []))].sort();
    category.insertAdjacentHTML('beforeend', cats.map(c => `<option value="${escapeHtml(c)}">${escapeHtml(c)}</option>`).join(''));
    document.querySelector('#updatedLabel').textContent = payload.updated ? `Updated ${new Date(payload.updated).toLocaleDateString(undefined,{month:'short',day:'numeric',year:'numeric'})}` : 'Cached data';
    const pool = Number(payload.topN) || state.games.length;
    document.querySelector('#poolLabel').textContent = `Current BGG Top ${pool}`;
    render();
  } catch (error) {
    document.querySelector('#updatedLabel').textContent = 'Data unavailable';
    empty.hidden = false;
    empty.textContent = 'Could not load game data.';
    console.error(error);
  }
}
init();
