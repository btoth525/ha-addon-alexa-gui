'use strict';

// All fetch URLs are intentionally relative — the app runs under an HA ingress
// path and the server sees clean root paths after the prefix is stripped.

const DISPLAY_CATEGORIES = [
  '', 'LIGHT', 'SWITCH', 'SMARTPLUG', 'FAN', 'THERMOSTAT', 'SMARTLOCK',
  'GARAGE_DOOR', 'DOOR', 'INTERIOR_BLIND', 'EXTERIOR_BLIND',
  'SCENE_TRIGGER', 'ACTIVITY_TRIGGER', 'CONTACT_SENSOR', 'MOTION_SENSOR',
  'SECURITY_PANEL', 'SPEAKER', 'STREAMING_DEVICE', 'TV', 'OTHER',
];

let state = {
  entities: [],          // EntityState from /api/state
  activeTab: 'all',
  searchQuery: '',
  overrides: {},         // {entity_id: {name_override, display_category}}
  dirty: false,
  restartRequired: false,
  migrationStatus: '',
  migrationMessage: '',
};

// ---- DOM refs ----
const $ = id => document.getElementById(id);
const qsa = (sel, root = document) => [...root.querySelectorAll(sel)];

// ---- Bootstrap ----
document.addEventListener('DOMContentLoaded', () => {
  loadState();
});

async function loadState() {
  try {
    const r = await fetch('api/state');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    applyServerState(data);
  } catch (e) {
    showBanner('error-banner', `Failed to load state: ${e.message}`);
  }
}

function applyServerState(data) {
  state.entities = data.entities || [];
  state.restartRequired = data.restart_required || false;
  state.migrationStatus = data.migration_status || '';
  state.migrationMessage = data.migration_message || '';
  state.dirty = false;

  // Seed overrides from loaded entity data
  state.overrides = {};
  for (const e of state.entities) {
    if (e.name_override || e.display_category) {
      state.overrides[e.entity_id] = {
        name_override: e.name_override || '',
        display_category: e.display_category || '',
      };
    }
  }

  renderBanners();
  renderTabs();
  renderList();
  renderFooter();
}

// ---- Banners ----
function showBanner(id, msg) {
  const el = $(id);
  if (!el) return;
  const msgEl = el.querySelector('.msg');
  if (msgEl) msgEl.textContent = msg;
  el.classList.remove('hidden');
}
function hideBanner(id) {
  const el = $(id);
  if (el) el.classList.add('hidden');
}

function renderBanners() {
  // Migration banners
  hideBanner('migrated-banner');
  hideBanner('migration-failed-banner');
  hideBanner('not-configured-banner');

  if (state.migrationStatus === 'migration_failed') {
    showBanner('migration-failed-banner', state.migrationMessage || 'Migration failed');
  } else if (state.migrationStatus === 'not_configured') {
    showBanner('not-configured-banner', 'No alexa: block found in configuration.yaml.');
  } else if (state.migrationStatus === 'migrated') {
    showBanner('migrated-banner', 'Phase 0 migration complete. Restart required to apply.');
  }

  // Restart banner
  if (state.restartRequired) {
    showBanner('restart-banner', 'Saved. A Home Assistant restart is required to apply changes.');
  } else {
    hideBanner('restart-banner');
  }
}

// ---- Tabs ----
function domains() {
  const seen = new Set();
  const list = [];
  for (const e of state.entities) {
    if (!seen.has(e.domain)) { seen.add(e.domain); list.push(e.domain); }
  }
  return list.sort();
}

function renderTabs() {
  const container = $('tabs');
  container.innerHTML = '';

  const tabs = ['all', ...domains()];
  for (const tab of tabs) {
    const count = tab === 'all'
      ? state.entities.filter(e => e.exposed).length + '/' + state.entities.length
      : (() => {
          const inDomain = state.entities.filter(e => e.domain === tab);
          return inDomain.filter(e => e.exposed).length + '/' + inDomain.length;
        })();

    const btn = document.createElement('button');
    btn.className = 'tab' + (state.activeTab === tab ? ' active' : '');
    btn.innerHTML = `${tab === 'all' ? 'All' : tab} <span class="count">(${count})</span>`;
    btn.addEventListener('click', () => {
      state.activeTab = tab;
      renderTabs();
      renderList();
    });
    container.appendChild(btn);
  }
}

// ---- Entity list ----
function filteredEntities() {
  const q = state.searchQuery.toLowerCase();
  return state.entities.filter(e => {
    if (state.activeTab !== 'all' && e.domain !== state.activeTab) return false;
    if (q && !e.entity_id.toLowerCase().includes(q) && !e.friendly_name.toLowerCase().includes(q)) return false;
    return true;
  });
}

function renderList() {
  const list = $('entity-list');
  list.innerHTML = '';

  const entities = filteredEntities();

  if (entities.length === 0) {
    list.innerHTML = '<div class="empty">No entities match your filter.</div>';
    return;
  }

  // Header
  const hdr = document.createElement('div');
  hdr.className = 'entity-header';
  hdr.innerHTML = `
    <span></span>
    <span>Entity</span>
    <span>Friendly Name</span>
    <span class="col-override">Name Override</span>
    <span class="col-category">Category</span>
  `;
  list.appendChild(hdr);

  for (const entity of entities) {
    const ov = state.overrides[entity.entity_id] || {};
    const row = document.createElement('div');
    row.className = 'entity-row' + (entity.exposed ? '' : ' unexposed');
    row.dataset.eid = entity.entity_id;

    const catOptions = DISPLAY_CATEGORIES.map(c =>
      `<option value="${c}" ${(ov.display_category || '') === c ? 'selected' : ''}>${c || '— none —'}</option>`
    ).join('');

    row.innerHTML = `
      <input type="checkbox" ${entity.exposed ? 'checked' : ''} data-eid="${entity.entity_id}" class="expose-cb" title="Expose to Alexa">
      <span class="entity-id" title="${entity.entity_id}">${entity.entity_id}</span>
      <span class="entity-name" title="${entity.friendly_name}">${entity.friendly_name}</span>
      <span class="col-override">
        <input type="text" class="name-override" data-eid="${entity.entity_id}"
          placeholder="${entity.friendly_name}" value="${ov.name_override || ''}" maxlength="256">
      </span>
      <span class="col-category">
        <select class="category" data-eid="${entity.entity_id}">${catOptions}</select>
      </span>
    `;
    list.appendChild(row);
  }

  // Attach events
  list.querySelectorAll('.expose-cb').forEach(cb => {
    cb.addEventListener('change', e => {
      const eid = e.target.dataset.eid;
      const en = state.entities.find(x => x.entity_id === eid);
      if (en) { en.exposed = e.target.checked; }
      markDirty();
      // Restyle row
      const row = e.target.closest('.entity-row');
      if (row) row.classList.toggle('unexposed', !e.target.checked);
      // Update tab counts
      renderTabs();
    });
  });

  list.querySelectorAll('.name-override').forEach(input => {
    input.addEventListener('input', e => {
      const eid = e.target.dataset.eid;
      if (!state.overrides[eid]) state.overrides[eid] = {};
      state.overrides[eid].name_override = e.target.value.trim();
      markDirty();
    });
  });

  list.querySelectorAll('.category').forEach(sel => {
    sel.addEventListener('change', e => {
      const eid = e.target.dataset.eid;
      if (!state.overrides[eid]) state.overrides[eid] = {};
      state.overrides[eid].display_category = e.target.value;
      markDirty();
    });
  });
}

// ---- Bulk helpers ----
function selectAllVisible(exposed) {
  const entities = filteredEntities();
  for (const e of entities) { e.exposed = exposed; }
  markDirty();
  renderTabs();
  renderList();
}

// ---- Dirty / footer ----
function markDirty() {
  state.dirty = true;
  renderFooter();
}

function renderFooter() {
  const btn = $('save-btn');
  if (btn) btn.disabled = !state.dirty;
}

// ---- Save ----
async function save() {
  const btn = $('save-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving…';

  const payload = {
    entities: state.entities.map(e => {
      const ov = state.overrides[e.entity_id] || {};
      return {
        entity_id: e.entity_id,
        exposed: e.exposed,
        name_override: ov.name_override || null,
        display_category: ov.display_category || null,
      };
    }),
  };

  try {
    const r = await fetch('api/save', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const data = await r.json();

    if (data.ok) {
      state.dirty = false;
      state.restartRequired = data.restart_required || false;
      if (data.restarting) {
        showBanner('restarting-banner', 'Home Assistant is restarting (~30–60s)…');
        showDiscoveryReminder();
        hideBanner('restart-banner');
      } else {
        renderBanners();
      }
      renderTabs();
    } else {
      showBanner('error-banner', `Save failed: ${data.error || 'Unknown error'}${data.restored ? ' (backup restored)' : ''}`);
    }
  } catch (e) {
    showBanner('error-banner', `Save request failed: ${e.message}`);
  } finally {
    btn.textContent = 'Save';
    btn.disabled = !state.dirty;
  }
}

// ---- Restart ----
function promptRestart() {
  $('restart-modal').classList.remove('hidden');
}
function cancelRestart() {
  $('restart-modal').classList.add('hidden');
}

async function confirmRestart() {
  $('restart-modal').classList.add('hidden');
  const btn = $('restart-confirm-btn');
  if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span>'; }

  try {
    const r = await fetch('api/restart', { method: 'POST' });
    const data = await r.json();
    if (data.ok) {
      hideBanner('restart-banner');
      showBanner('restarting-banner', 'Home Assistant is restarting (~30–60s)…');
      showDiscoveryReminder();
      state.restartRequired = false;
    } else {
      showBanner('error-banner', `Restart failed: ${data.error}`);
    }
  } catch (e) {
    showBanner('error-banner', `Restart request failed: ${e.message}`);
  }
}

function showDiscoveryReminder() {
  showBanner('discovery-banner', '');
}

// ---- Search ----
function onSearch(e) {
  state.searchQuery = e.target.value;
  renderList();
}

// ---- Wire up static buttons and inputs ----
document.addEventListener('DOMContentLoaded', () => {
  const searchEl = $('search');
  if (searchEl) searchEl.addEventListener('input', onSearch);

  const saveBtn = $('save-btn');
  if (saveBtn) saveBtn.addEventListener('click', save);

  const selectAll = $('select-all');
  if (selectAll) selectAll.addEventListener('click', () => selectAllVisible(true));

  const deselectAll = $('deselect-all');
  if (deselectAll) deselectAll.addEventListener('click', () => selectAllVisible(false));

  const restartBtn = $('restart-banner-btn');
  if (restartBtn) restartBtn.addEventListener('click', promptRestart);

  const migRestartBtn = $('migrated-restart-btn');
  if (migRestartBtn) migRestartBtn.addEventListener('click', promptRestart);

  const cancelBtn = $('restart-cancel-btn');
  if (cancelBtn) cancelBtn.addEventListener('click', cancelRestart);

  const confirmBtn = $('restart-confirm-btn');
  if (confirmBtn) confirmBtn.addEventListener('click', confirmRestart);
});
