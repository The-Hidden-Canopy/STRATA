const state = { projects: [], selectedProjectId: null, workFilter: 'all', project: null, work: [], agents: [], attention: [], events: [] };
const $ = (selector) => document.querySelector(selector);
const $$ = (selector) => [...document.querySelectorAll(selector)];

async function api(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${response.status} ${response.statusText}`);
  return response.json();
}
function escapeHtml(value) { return String(value ?? '').replace(/[&<>"']/g, (character) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character])); }
function initials(name) { return String(name || '?').split(/\s+/).map((part) => part[0]).join('').slice(0, 2).toUpperCase(); }
function formatTime(value) { if (!value) return '—'; const date = new Date(value); return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat(undefined, { hour: 'numeric', minute: '2-digit' }).format(date); }
function statusClass(status) { return `status-${String(status || 'unknown').replace(/[^a-z0-9_-]/gi, '').toLowerCase()}`; }
function humanStatus(status) { return String(status || 'unknown').replaceAll('_', ' '); }
function showError(error) { const banner = $('#error-banner'); banner.textContent = `Could not refresh project data: ${error.message}`; banner.classList.remove('is-hidden'); }
function clearError() { $('#error-banner').classList.add('is-hidden'); }
function setLoading(isLoading) { document.body.classList.toggle('is-loading', isLoading); }

function renderProjects() {
  const list = $('#project-list');
  if (!state.projects.length) { list.innerHTML = '<div class="empty-state empty-sidebar">No projects yet.<small>Create one through the CLI or API.</small></div>'; return; }
  list.innerHTML = state.projects.map((project) => `<button class="project-button ${project.project_id === state.selectedProjectId ? 'is-selected' : ''}" type="button" data-project-id="${escapeHtml(project.project_id)}"><span class="project-avatar">${escapeHtml(initials(project.name))}</span><span class="project-button-copy"><strong>${escapeHtml(project.name)}</strong><small>${escapeHtml(humanStatus(project.status))}</small></span><span class="project-chevron" aria-hidden="true">›</span></button>`).join('');
  $$('.project-button').forEach((button) => button.addEventListener('click', () => selectProject(button.dataset.projectId)));
}
function renderProjectHeader() {
  const project = state.project;
  if (!project) return;
  $('#topbar-project-name').textContent = project.name;
  $('#project-title').textContent = project.name;
  $('#project-objective').textContent = project.objective || project.description || 'No project objective has been defined yet.';
  $('#project-status').textContent = humanStatus(project.status);
  $('#project-status').className = `status-pill ${statusClass(project.status)}`;
  $('#project-id').textContent = `${project.project_id} · revision ${project.revision}`;
}
function renderStats() {
  const activeStatuses = new Set(['claimed', 'running', 'review']);
  $('#stat-ready').textContent = state.work.filter((item) => item.status === 'ready').length;
  $('#stat-active').textContent = state.work.filter((item) => activeStatuses.has(item.status)).length;
  $('#stat-agents').textContent = state.agents.length;
  $('#stat-attention').textContent = state.attention.length;
  $('#work-count').textContent = `${state.work.length} item${state.work.length === 1 ? '' : 's'}`;
  $('#agent-count').textContent = `${state.agents.length}`;
  $('#attention-count').textContent = `${state.attention.length}`;
}
function filterWork(item) {
  if (state.workFilter === 'all') return true;
  if (state.workFilter === 'active') return ['claimed', 'running', 'review'].includes(item.status);
  if (state.workFilter === 'blocked') return ['blocked', 'reconciliation', 'failed_retryable', 'failed_final'].includes(item.status);
  return item.status === state.workFilter;
}
function renderWork() {
  const list = $('#work-list');
  const visible = state.work.filter(filterWork);
  $$('.filter-button').forEach((button) => button.classList.toggle('is-active', button.dataset.filter === state.workFilter));
  if (!visible.length) { list.innerHTML = `<div class="empty-state"><span class="empty-icon">✓</span><strong>${state.work.length ? 'Nothing in this view' : 'The work pool is clear'}</strong><small>${state.work.length ? 'Try another filter.' : 'New eligible work will appear here as the project evolves.'}</small></div>`; return; }
  list.innerHTML = visible.map((item) => `<article class="work-card"><div class="work-priority priority-${item.priority >= 8 ? 'high' : item.priority >= 4 ? 'medium' : 'low'}"><span aria-hidden="true">●</span> ${escapeHtml(item.priority >= 8 ? 'High' : item.priority >= 4 ? 'Normal' : 'Low')}</div><div class="work-copy"><h3>${escapeHtml(item.title)}</h3><p>${escapeHtml(item.objective || item.detail || 'No additional detail')}</p></div><span class="lane-badge">${escapeHtml(item.lane)}</span><span class="status-pill ${statusClass(item.status)}">${escapeHtml(humanStatus(item.status))}</span></article>`).join('');
}
function renderAgents() {
  const list = $('#agent-list');
  if (!state.agents.length) { list.innerHTML = '<div class="empty-state compact-empty"><span class="empty-icon">✦</span><strong>No agents registered</strong><small>Register an agent to start pulling work.</small></div>'; return; }
  list.innerHTML = state.agents.map((agent, index) => `<article class="agent-row"><span class="agent-avatar agent-color-${index % 4}">${escapeHtml(initials(agent.name))}</span><span class="agent-copy"><strong>${escapeHtml(agent.name)}</strong><small>${escapeHtml(agent.primary_lane)} lane · ${agent.capabilities?.length || 0} capabilities</small></span><span class="agent-state"><i></i> ready</span></article>`).join('');
}
function renderAttention() {
  const list = $('#attention-list');
  if (!state.attention.length) { list.innerHTML = '<div class="attention-clear"><span class="clear-check">✓</span><span><strong>Nothing needs you right now</strong><small>Agents can keep moving while the project is clear.</small></span></div>'; return; }
  list.innerHTML = state.attention.map((item) => `<article class="attention-item"><span class="attention-icon">!</span><span><strong>${escapeHtml(item.category)}</strong><small>${escapeHtml(item.summary)}</small></span></article>`).join('');
}
function renderActivity() {
  const list = $('#activity-list');
  if (!state.events.length) { list.innerHTML = '<div class="empty-state compact-empty"><strong>No activity yet</strong><small>Project events will appear here.</small></div>'; return; }
  list.innerHTML = state.events.slice(0, 5).map((event) => `<article class="activity-row"><span class="activity-dot"></span><span class="activity-copy"><strong>${escapeHtml(humanStatus(event.kind))}</strong><small>${escapeHtml(event.entity_type)} · ${escapeHtml(formatTime(event.created_at))}</small></span></article>`).join('');
}
async function selectProject(projectId) { state.selectedProjectId = projectId; renderProjects(); await loadProject(); }
async function loadProjects() {
  const data = await api('/api/v1/projects');
  state.projects = data.projects || [];
  if (!state.projects.length) { state.selectedProjectId = null; renderProjects(); return; }
  if (!state.projects.some((project) => project.project_id === state.selectedProjectId)) state.selectedProjectId = state.projects[0].project_id;
  renderProjects();
  await loadProject();
}
async function loadProject() {
  if (!state.selectedProjectId) return;
  setLoading(true);
  try {
    const id = encodeURIComponent(state.selectedProjectId);
    const [project, work, agents, attention, events] = await Promise.all([api(`/api/v1/projects/${id}`), api(`/api/v1/projects/${id}/work`), api(`/api/v1/projects/${id}/agents`), api(`/api/v1/projects/${id}/attention`), api(`/api/v1/projects/${id}/events`)]);
    state.project = project; state.work = work.work || []; state.agents = agents.agents || []; state.attention = attention.attention || []; state.events = events.events || [];
    clearError(); renderProjectHeader(); renderStats(); renderWork(); renderAgents(); renderAttention(); renderActivity();
    $('#last-updated').textContent = `Synced ${formatTime(new Date().toISOString())}`;
  } catch (error) { showError(error); } finally { setLoading(false); }
}
async function refresh() { try { await loadProjects(); } catch (error) { showError(error); } }
$$('.filter-button').forEach((button) => button.addEventListener('click', () => { state.workFilter = button.dataset.filter; renderWork(); }));
$('#sidebar-refresh').addEventListener('click', refresh);
$('#topbar-refresh').addEventListener('click', refresh);
loadProjects().catch(showError);
