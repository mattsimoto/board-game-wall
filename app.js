const state = { games: [], view: 'rank' };
const wall = document.querySelector('#gameWall');
const count = document.querySelector('#gameCount');
const empty = document.querySelector('#emptyState');
const category = document.querySelector('#categoryFilter');
const players = document.querySelector('#playersFilter');
const age = document.querySelector('#ageFilter');
const time = document.querySelector('#timeFilter');
const dialog = document.querySelector('#gameDialog');
const dialogContent = document.querySelector('#dialogContent');

const escapeHtml = value => String(value ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));

function movementClass(delta) {
  if (delta > 0) return 'up';
  if (delta < 0) return 'down';
  return 'flat';
}
function movementLabel(delta) {
  if (delta > 0) return `▲ ${delta}`;
  if (delta < 0) return `▼ ${Math.abs(delta)}`;
  return '• 0';
}
function cardSize(game, index) {
  if (state.view !== 'rank') {
    const magnitude = Math.abs(game.rankChange30 || 0);
    if (index < 2 || magnitude >= 25) return 'size-hero';
    if (index < 6 || magnitude >= 15) return 'size-xl';
    if (index < 14 || magnitude >= 8) return 'size-lg';
    return index < 30 ? 'size-md' : 'size-sm';
  }
  if (game.rank <= 3) return 'size-hero';
  if (game.rank <= 10) return 'size-xl';
  if (game.rank <= 25) return 'size-lg';
  if (game.rank <= 60) return 'size-md';
  return 'size-sm';
}
function matches(game) {
  if (category.value !== 'all' && !game.categories.includes(category.value)) return false;
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
function sortGames(games) {
  const copy = [...games];
  if (state.view === 'climbers') return copy.sort((a,b) => (b.rankChange30||0) - (a.rankChange30||0));
  if (state.view === 'fallers') return copy.sort((a,b) => (a.rankChange30||0) - (b.rankChange30||0));
  if (state.view === 'hot') return copy.sort((a,b) => (b.hotScore||0) - (a.hotScore||0));
  return copy.sort((a,b) => a.rank - b.rank);
}
function render() {
  const games = sortGames(state.games.filter(matches));
  count.textContent = games.length;
  empty.hidden = games.length > 0;
  wall.innerHTML = games.map((game, index) => `
    <article class="game-card ${cardSize(game,index)}" data-id="${game.id}" tabindex="0" role="button" aria-label="${escapeHtml(game.name)}, rank ${game.rank}">
      <img src="${escapeHtml(game.image)}" alt="${escapeHtml(game.name)} box cover" loading="lazy" referrerpolicy="no-referrer" />
      <div class="card-top">
        <span class="rank-badge">#${game.rank}</span>
        <span class="movement ${movementClass(game.rankChange30)}" title="30-day rank movement">${movementLabel(game.rankChange30)}</span>
      </div>
      <div class="card-bottom">
        <div class="game-info">
          <div class="game-name">${escapeHtml(game.name)}</div>
          <div class="game-meta"><span>♟ ${game.minPlayers}–${game.maxPlayers}</span><span>◷ ${game.minPlayTime}–${game.maxPlayTime}m</span><span>${game.minAge}+</span></div>
        </div>
      </div>
    </article>`).join('');
}
function showGame(id) {
  const g = state.games.find(x => String(x.id) === String(id));
  if (!g) return;
  dialogContent.innerHTML = `<div class="dialog-layout">
    <img class="dialog-cover" src="${escapeHtml(g.image)}" alt="${escapeHtml(g.name)} box cover" />
    <div class="dialog-copy">
      <div class="dialog-rank">BGG RANK #${g.rank} · <span class="${movementClass(g.rankChange30)}">${movementLabel(g.rankChange30)} / 30 days</span></div>
      <h2>${escapeHtml(g.name)}</h2>
      <p>${escapeHtml(g.year || '')}${g.rating ? ` · ${Number(g.rating).toFixed(1)} BGG rating` : ''}</p>
      <div class="detail-grid">
        <div class="detail"><span>Players</span><strong>${g.minPlayers}–${g.maxPlayers}</strong></div>
        <div class="detail"><span>Age</span><strong>${g.minAge}+</strong></div>
        <div class="detail"><span>Play time</span><strong>${g.minPlayTime}–${g.maxPlayTime} min</strong></div>
        <div class="detail"><span>30-day move</span><strong class="${movementClass(g.rankChange30)}">${movementLabel(g.rankChange30)}</strong></div>
      </div>
      <p>${g.categories.map(escapeHtml).join(' · ')}</p>
      <a class="bgg-link" href="https://boardgamegeek.com/boardgame/${g.id}" target="_blank" rel="noopener">View on BoardGameGeek ↗</a>
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
document.querySelector('#resetFilters').addEventListener('click', () => {
  category.value = players.value = age.value = time.value = 'all';
  state.view = 'rank';
  document.querySelectorAll('#viewControls button').forEach(b => b.classList.toggle('active', b.dataset.view === 'rank'));
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
    document.querySelector('#updatedLabel').textContent = payload.updated ? `Updated ${new Date(payload.updated).toLocaleDateString()}` : 'Cached data';
    render();
  } catch (error) {
    document.querySelector('#updatedLabel').textContent = 'Data unavailable';
    empty.hidden = false;
    empty.textContent = 'Could not load game data.';
    console.error(error);
  }
}
init();
