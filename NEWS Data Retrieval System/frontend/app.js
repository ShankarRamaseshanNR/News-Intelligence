/* ========================================
   News Intelligence RAG — Application Logic
   ======================================== */

const API_BASE = window.location.origin;

// ── State ──
const state = {
  currentSection: 'dashboard',
  articles: [],
  searchResults: [],
  chatMessages: [],
  conversationId: null,
  analytics: null,
  isLoading: false,
  chatLoading: false,
};

// ── Initialization ──
document.addEventListener('DOMContentLoaded', () => {
  initNavigation();
  initChat();
  initFetch();
  initSearch();
  loadDashboard();

  // Mobile toggle
  const toggle = document.getElementById('mobile-toggle');
  if (toggle) {
    toggle.addEventListener('click', () => {
      document.querySelector('.sidebar').classList.toggle('open');
    });
  }
});

// ── Navigation ──
function initNavigation() {
  document.querySelectorAll('.nav-item').forEach(item => {
    item.addEventListener('click', () => {
      const section = item.dataset.section;
      switchSection(section);
    });
  });
}

function switchSection(section) {
  state.currentSection = section;

  document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));
  document.querySelector(`.nav-item[data-section="${section}"]`)?.classList.add('active');

  document.querySelectorAll('.section').forEach(s => s.classList.remove('active'));
  document.getElementById(`section-${section}`)?.classList.add('active');

  // Update header
  const titles = {
    dashboard: ['Dashboard', 'Overview of your news intelligence system'],
    news: ['News Feed', 'Browse and fetch the latest news articles'],
    search: ['Semantic Search', 'Find relevant articles using AI-powered search'],
    chat: ['AI Chat', 'Ask questions about current events'],
    analytics: ['Analytics', 'Insights and statistics about collected news'],
  };

  const [title, subtitle] = titles[section] || ['', ''];
  document.getElementById('page-title').textContent = title;
  document.getElementById('page-subtitle').textContent = subtitle;

  // Load section data
  if (section === 'dashboard') loadDashboard();
  if (section === 'news') loadArticles();
  if (section === 'analytics') loadAnalytics();

  // Close mobile sidebar
  document.querySelector('.sidebar')?.classList.remove('open');
}

// ── API Helpers ──
async function apiFetch(path, options = {}) {
  try {
    const response = await fetch(`${API_BASE}${path}`, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    if (!response.ok) {
      let errorMsg = `API Error ${response.status}`;
      try {
        const errorData = await response.json();
        errorMsg = errorData.message || errorData.detail || JSON.stringify(errorData);
      } catch {
        errorMsg = await response.text();
      }
      throw new Error(errorMsg);
    }
    return await response.json();
  } catch (error) {
    console.error(`API Error [${path}]:`, error);
    throw error;
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ── Dashboard ──
async function loadDashboard() {
  const statsGrid = document.getElementById('dashboard-stats');
  const chartsArea = document.getElementById('dashboard-charts');

  try {
    const [analytics, health] = await Promise.all([
      apiFetch('/api/analytics').catch(() => null),
      apiFetch('/health').catch(() => null),
    ]);

    // Update status dot
    const statusText = document.getElementById('status-text');
    if (health && health.status === 'healthy') {
      statusText.textContent = 'System Online';
    }

    if (analytics) {
      state.analytics = analytics;
      renderDashboardStats(analytics);
      renderDashboardCharts(analytics);
    } else {
      statsGrid.innerHTML = `
        <div class="stat-card accent">
          <div class="stat-icon">📰</div>
          <div class="stat-value">0</div>
          <div class="stat-label">Total Articles</div>
        </div>
        <div class="stat-card success">
          <div class="stat-icon">🗂️</div>
          <div class="stat-value">0</div>
          <div class="stat-label">Categories</div>
        </div>
        <div class="stat-card warning">
          <div class="stat-icon">🔗</div>
          <div class="stat-value">0</div>
          <div class="stat-label">Sources</div>
        </div>
        <div class="stat-card info">
          <div class="stat-icon">🧠</div>
          <div class="stat-value">0</div>
          <div class="stat-label">Vector Embeddings</div>
        </div>
      `;
      chartsArea.innerHTML = `
        <div class="empty-state">
          <div class="icon">🚀</div>
          <h3>Welcome to News Intelligence</h3>
          <p>Start by fetching some news articles from the News Feed section to populate your dashboard.</p>
        </div>
      `;
    }
  } catch (e) {
    statsGrid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="icon">⚠️</div>
        <h3>Connection Error</h3>
        <p>Could not connect to the backend API. Make sure the server is running.</p>
      </div>
    `;
  }
}

function renderDashboardStats(data) {
  const vectorCount = data.categories?.reduce((a, b) => a + b.count, 0) || 0;
  document.getElementById('dashboard-stats').innerHTML = `
    <div class="stat-card accent">
      <div class="stat-icon">📰</div>
      <div class="stat-value">${data.total_articles?.toLocaleString() || 0}</div>
      <div class="stat-label">Total Articles</div>
    </div>
    <div class="stat-card success">
      <div class="stat-icon">🗂️</div>
      <div class="stat-value">${data.categories?.length || 0}</div>
      <div class="stat-label">Categories</div>
    </div>
    <div class="stat-card warning">
      <div class="stat-icon">🔗</div>
      <div class="stat-value">${data.top_sources?.length || 0}</div>
      <div class="stat-label">Sources</div>
    </div>
    <div class="stat-card info">
      <div class="stat-icon">📊</div>
      <div class="stat-value">${(data.sentiment?.positive || 0) + (data.sentiment?.negative || 0) + (data.sentiment?.neutral || 0)}</div>
      <div class="stat-label">Sentiment Analyzed</div>
    </div>
  `;
}

function renderDashboardCharts(data) {
  const chartsArea = document.getElementById('dashboard-charts');

  const categoryBars = (data.categories || []).slice(0, 8).map(c => {
    const max = Math.max(...data.categories.map(x => x.count), 1);
    const pct = Math.round((c.count / max) * 100);
    return `
      <div class="bar-item">
        <span class="bar-label">${c.category}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${pct}%"><span>${c.count}</span></div>
        </div>
      </div>
    `;
  }).join('');

  const trendBars = (data.recent_trend || []).slice(0, 14).reverse().map(t => {
    const max = Math.max(...data.recent_trend.map(x => x.count), 1);
    const heightPct = Math.max(8, Math.round((t.count / max) * 100));
    const dateLabel = t.date ? t.date.split('-').slice(1).join('/') : '';
    return `
      <div class="trend-bar" style="height: ${heightPct}%">
        <span class="trend-bar-count">${t.count}</span>
        <span class="trend-bar-label">${dateLabel}</span>
      </div>
    `;
  }).join('');

  const s = data.sentiment || { positive: 0, negative: 0, neutral: 0 };
  const sTotal = s.positive + s.negative + s.neutral || 1;
  const posPct = Math.round((s.positive / sTotal) * 100);
  const negPct = Math.round((s.negative / sTotal) * 100);
  const neuPct = 100 - posPct - negPct;

  chartsArea.innerHTML = `
    <div class="charts-row">
      <div class="chart-card">
        <h3>📊 Categories Distribution</h3>
        <div class="bar-chart">${categoryBars || '<div class="empty-state"><p>No data yet</p></div>'}</div>
      </div>
      <div class="chart-card">
        <h3>📈 Daily Trend</h3>
        <div class="trend-bars" style="margin-bottom: 28px;">${trendBars || '<div class="empty-state"><p>No data yet</p></div>'}</div>
      </div>
    </div>
    <div class="charts-row">
      <div class="chart-card">
        <h3>🎭 Sentiment Analysis</h3>
        <div class="donut-container">
          <div class="donut" style="background: conic-gradient(
            var(--success) 0% ${posPct}%,
            var(--danger) ${posPct}% ${posPct + negPct}%,
            var(--text-muted) ${posPct + negPct}% 100%
          )">
            <div class="donut-center">${sTotal > 1 ? sTotal : 0}</div>
          </div>
          <div class="donut-legend">
            <div class="legend-item"><span class="legend-dot positive"></span> Positive: ${s.positive} (${posPct}%)</div>
            <div class="legend-item"><span class="legend-dot negative"></span> Negative: ${s.negative} (${negPct}%)</div>
            <div class="legend-item"><span class="legend-dot neutral"></span> Neutral: ${s.neutral} (${neuPct}%)</div>
          </div>
        </div>
      </div>
      <div class="chart-card">
        <h3>🏢 Top Sources</h3>
        <div class="source-list">
          ${(data.top_sources || []).slice(0, 8).map(s => `
            <div class="source-row">
              <span class="source-name">${s.source || 'Unknown'}</span>
              <span class="source-count">${s.count} articles</span>
            </div>
          `).join('') || '<div class="empty-state"><p>No data yet</p></div>'}
        </div>
      </div>
    </div>
  `;
}

// ── News Feed ──
function initFetch() {
  document.getElementById('btn-fetch-news')?.addEventListener('click', fetchNewsArticles);
}

async function fetchNewsArticles() {
  const btn = document.getElementById('btn-fetch-news');
  const category = document.getElementById('fetch-category').value;

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Fetching...';

  try {
    const body = {};
    if (category) body.category = category;
    body.country = 'us';
    body.language = 'en';

    const result = await apiFetch('/api/news/fetch', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    if (result.fetched > 0) {
      showToast(`✅ Fetched ${result.fetched} articles, ${result.new_inserted} new inserted`, 'success');
    } else {
      showToast('No new articles found. Try a different category.', 'info');
    }
    await loadArticles();
  } catch (e) {
    showToast(e.message || 'Failed to fetch news.', 'error');
  } finally {
    btn.disabled = false;
    btn.innerHTML = '⚡ Fetch News';
  }
}

async function loadArticles() {
  const grid = document.getElementById('articles-grid');
  grid.innerHTML = '<div class="loading-overlay"><div class="loader"></div></div>';

  try {
    const category = document.getElementById('filter-category')?.value || '';
    const params = new URLSearchParams({ limit: '30', offset: '0' });
    if (category) params.set('category', category);

    const articles = await apiFetch(`/api/news?${params}`);
    state.articles = articles;

    if (articles.length === 0) {
      grid.innerHTML = `
        <div class="empty-state" style="grid-column: 1/-1;">
          <div class="icon">📭</div>
          <h3>No Articles Yet</h3>
          <p>Click "Fetch News" above to pull in the latest articles from NewsData.io</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = articles.map(a => renderArticleCard(a)).join('');
  } catch (e) {
    grid.innerHTML = `
      <div class="empty-state" style="grid-column: 1/-1;">
        <div class="icon">⚠️</div>
        <h3>Error Loading Articles</h3>
        <p>${e.message}</p>
      </div>
    `;
  }
}

function renderArticleCard(article) {
  const sentimentClass = article.sentiment === 'positive' ? 'badge-positive' :
    article.sentiment === 'negative' ? 'badge-negative' : 'badge-neutral';

  const imageHtml = article.image_url
    ? `<img class="article-image" src="${escapeHtml(article.image_url)}" alt="${escapeHtml(article.title)}" onerror="this.outerHTML='<div class=\\'article-image-placeholder\\'>📰</div>'">`
    : '<div class="article-image-placeholder">📰</div>';

  const date = article.published_at
    ? new Date(article.published_at).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
    : '';

  return `
    <div class="article-card">
      ${imageHtml}
      <div class="article-content">
        <div class="article-meta">
          ${article.category ? `<span class="badge badge-category">${escapeHtml(article.category)}</span>` : ''}
          ${article.sentiment ? `<span class="badge badge-sentiment ${sentimentClass}">${escapeHtml(article.sentiment)}</span>` : ''}
        </div>
        <h3 class="article-title">${escapeHtml(article.title)}</h3>
        <p class="article-desc">${escapeHtml(article.description || '')}</p>
      </div>
      <div class="article-footer">
        <span class="article-source">${escapeHtml(article.source_name || 'Unknown')} ${date ? '· ' + date : ''}</span>
        ${article.url ? `<a href="${escapeHtml(article.url)}" target="_blank" rel="noopener" class="article-link">Read ↗</a>` : ''}
      </div>
    </div>
  `;
}

// ── Semantic Search ──
function initSearch() {
  const searchInput = document.getElementById('search-input');
  const searchBtn = document.getElementById('btn-search');

  searchBtn?.addEventListener('click', performSearch);
  searchInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') performSearch();
  });
}

async function performSearch() {
  const query = document.getElementById('search-input').value.trim();
  if (!query) return;

  const resultsArea = document.getElementById('search-results');
  const btn = document.getElementById('btn-search');
  const category = document.getElementById('search-category')?.value || '';

  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Searching';
  resultsArea.innerHTML = '<div class="loading-overlay"><div class="loader"></div></div>';

  try {
    const body = { query, top_k: 10 };
    if (category) body.category = category;

    const data = await apiFetch('/api/search', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    state.searchResults = data.results || [];

    if (state.searchResults.length === 0) {
      resultsArea.innerHTML = `
        <div class="empty-state">
          <div class="icon">🔍</div>
          <h3>No Results Found</h3>
          <p>Try a different query or fetch more news articles first.</p>
        </div>
      `;
      return;
    }

    resultsArea.innerHTML = state.searchResults.map((r, i) => `
      <div class="search-result-card">
        <div class="result-header">
          <h3 class="result-title">${escapeHtml(r.article?.title || 'Unknown')}</h3>
          <span class="relevance-badge">${Math.round(r.relevance_score * 100)}% match</span>
        </div>
        <div class="result-snippet">${escapeHtml(r.matched_snippet || '')}</div>
        <div class="result-meta">
          ${r.article?.category ? `<span>📁 ${escapeHtml(r.article.category)}</span>` : ''}
          ${r.article?.source_name ? `<span>🏢 ${escapeHtml(r.article.source_name)}</span>` : ''}
          ${r.article?.url ? `<a href="${escapeHtml(r.article.url)}" target="_blank" rel="noopener" class="article-link">Read full article ↗</a>` : ''}
        </div>
      </div>
    `).join('');

  } catch (e) {
    resultsArea.innerHTML = `
      <div class="empty-state">
        <div class="icon">⚠️</div>
        <h3>Search Error</h3>
        <p>${e.message}. Make sure you have articles indexed first.</p>
      </div>
    `;
  } finally {
    btn.disabled = false;
    btn.innerHTML = '🔍 Search';
  }
}

// ── AI Chat ──
function initChat() {
  const chatInput = document.getElementById('chat-input');
  const chatBtn = document.getElementById('btn-send-chat');

  chatBtn?.addEventListener('click', sendChatMessage);
  chatInput?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendChatMessage();
    }
  });

  // Suggestion chips
  document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
      chatInput.value = chip.textContent;
      sendChatMessage();
    });
  });
}

async function sendChatMessage() {
  const chatInput = document.getElementById('chat-input');
  const messagesContainer = document.getElementById('chat-messages');
  const btn = document.getElementById('btn-send-chat');
  const message = chatInput.value.trim();

  if (!message || state.chatLoading) return;

  // Add user message
  state.chatMessages.push({ role: 'user', content: message });
  chatInput.value = '';
  renderChatMessages();

  // Show typing indicator
  state.chatLoading = true;
  btn.disabled = true;
  const typingEl = document.createElement('div');
  typingEl.className = 'typing-indicator';
  typingEl.innerHTML = '<span></span><span></span><span></span>';
  messagesContainer.appendChild(typingEl);
  messagesContainer.scrollTop = messagesContainer.scrollHeight;

  try {
    const body = { message };
    if (state.conversationId) body.conversation_id = state.conversationId;

    const data = await apiFetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify(body),
    });

    state.conversationId = data.conversation_id;
    state.chatMessages.push({
      role: 'assistant',
      content: data.answer,
      sources: data.sources || [],
    });

  } catch (e) {
    state.chatMessages.push({
      role: 'assistant',
      content: `Sorry, I encountered an error: ${e.message}. Make sure you have news articles fetched and indexed first.`,
      sources: [],
    });
  } finally {
    state.chatLoading = false;
    btn.disabled = false;
    typingEl.remove();
    renderChatMessages();
  }
}

function renderChatMessages() {
  const container = document.getElementById('chat-messages');
  const welcomeEl = container.querySelector('.welcome-msg');

  if (state.chatMessages.length === 0) return;

  // Remove welcome message
  if (welcomeEl) welcomeEl.remove();

  container.innerHTML = state.chatMessages.map(msg => {
    if (msg.role === 'user') {
      return `
        <div class="message message-user">
          <div class="message-bubble">${escapeHtml(msg.content)}</div>
        </div>
      `;
    } else {
      const sourcesHtml = msg.sources && msg.sources.length > 0
        ? `<div class="message-sources">
            <h4>📚 Sources</h4>
            ${msg.sources.map((s, i) => `
              <div class="source-item">
                <span>[${i + 1}] ${escapeHtml(s.title)}</span>
                ${s.url ? `<a href="${escapeHtml(s.url)}" target="_blank" rel="noopener">↗</a>` : ''}
                <span style="color: var(--accent-light); font-size: 0.7rem;">${Math.round(s.relevance * 100)}%</span>
              </div>
            `).join('')}
           </div>`
        : '';

      return `
        <div class="message message-assistant">
          <div class="message-bubble">${formatMarkdown(msg.content)}</div>
          ${sourcesHtml}
        </div>
      `;
    }
  }).join('');

  container.scrollTop = container.scrollHeight;
}

// ── Analytics ──
async function loadAnalytics() {
  const container = document.getElementById('analytics-content');
  container.innerHTML = '<div class="loading-overlay"><div class="loader"></div></div>';

  try {
    const data = await apiFetch('/api/analytics');
    state.analytics = data;
    renderAnalytics(data);
  } catch (e) {
    container.innerHTML = `
      <div class="empty-state">
        <div class="icon">⚠️</div>
        <h3>Error Loading Analytics</h3>
        <p>${e.message}</p>
      </div>
    `;
  }
}

function renderAnalytics(data) {
  const container = document.getElementById('analytics-content');

  const categoryBars = (data.categories || []).map(c => {
    const max = Math.max(...data.categories.map(x => x.count), 1);
    const pct = Math.round((c.count / max) * 100);
    return `
      <div class="bar-item">
        <span class="bar-label">${escapeHtml(c.category)}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width: ${pct}%"><span>${c.count}</span></div>
        </div>
      </div>
    `;
  }).join('');

  const s = data.sentiment || { positive: 0, negative: 0, neutral: 0 };
  const sTotal = s.positive + s.negative + s.neutral || 1;
  const posPct = Math.round((s.positive / sTotal) * 100);
  const negPct = Math.round((s.negative / sTotal) * 100);
  const neuPct = 100 - posPct - negPct;

  container.innerHTML = `
    <div class="stats-grid">
      <div class="stat-card accent">
        <div class="stat-icon">📰</div>
        <div class="stat-value">${data.total_articles?.toLocaleString() || 0}</div>
        <div class="stat-label">Total Articles</div>
      </div>
      <div class="stat-card success">
        <div class="stat-icon">😊</div>
        <div class="stat-value">${s.positive}</div>
        <div class="stat-label">Positive Articles</div>
      </div>
      <div class="stat-card warning">
        <div class="stat-icon">😐</div>
        <div class="stat-value">${s.neutral}</div>
        <div class="stat-label">Neutral Articles</div>
      </div>
      <div class="stat-card info">
        <div class="stat-icon">😟</div>
        <div class="stat-value">${s.negative}</div>
        <div class="stat-label">Negative Articles</div>
      </div>
    </div>

    <div class="analytics-grid">
      <div class="chart-card">
        <h3>📊 All Categories</h3>
        <div class="bar-chart">${categoryBars || '<div class="empty-state"><p>No data</p></div>'}</div>
      </div>

      <div class="chart-card">
        <h3>🎭 Sentiment Breakdown</h3>
        <div class="donut-container">
          <div class="donut" style="background: conic-gradient(
            var(--success) 0% ${posPct}%,
            var(--danger) ${posPct}% ${posPct + negPct}%,
            var(--text-muted) ${posPct + negPct}% 100%
          )">
            <div class="donut-center">${sTotal > 1 ? sTotal : 0}</div>
          </div>
          <div class="donut-legend">
            <div class="legend-item"><span class="legend-dot positive"></span> Positive: ${s.positive} (${posPct}%)</div>
            <div class="legend-item"><span class="legend-dot negative"></span> Negative: ${s.negative} (${negPct}%)</div>
            <div class="legend-item"><span class="legend-dot neutral"></span> Neutral: ${s.neutral} (${neuPct}%)</div>
          </div>
        </div>
      </div>

      <div class="chart-card" style="grid-column: 1 / -1;">
        <h3>🏢 Top News Sources</h3>
        <div class="source-list">
          ${(data.top_sources || []).map(s => `
            <div class="source-row">
              <span class="source-name">${escapeHtml(s.source || 'Unknown')}</span>
              <span class="source-count">${s.count} articles</span>
            </div>
          `).join('') || '<div class="empty-state"><p>No sources found</p></div>'}
        </div>
      </div>
    </div>
  `;
}

// ── Utilities ──
function escapeHtml(str) {
  if (!str) return '';
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

function formatMarkdown(text) {
  if (!text) return '';
  // Basic markdown-like formatting
  let html = escapeHtml(text);
  // Bold
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
  // Italic
  html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
  // Source references
  html = html.replace(/\[Source (\d+)\]/g, '<span style="color: var(--accent-light); font-weight: 600;">[Source $1]</span>');
  // Line breaks
  html = html.replace(/\n/g, '<br>');
  // Bullet points
  html = html.replace(/^- (.+)/gm, '• $1');
  return html;
}
