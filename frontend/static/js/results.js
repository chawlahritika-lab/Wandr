const results = JSON.parse(localStorage.getItem('wandr-trip-result') || '{}');
const API_BASE_URL = 'http://127.0.0.1:8001';

const titleEl = document.getElementById('trip-title');
const narrativeEl = document.getElementById('trip-narrative');
const recommendationsEl = document.getElementById('recommendations');
const budgetBreakdownEl = document.getElementById('budget-breakdown');
const itineraryEl = document.getElementById('itinerary');
const localIntelligenceEl = document.getElementById('local-intelligence');
const tripPersonaEl = document.getElementById('trip-persona');
const tripStyleEl = document.getElementById('trip-style');
const tripBudgetEl = document.getElementById('trip-budget');

function renderRecommendations(items) {
  if (!items || !items.length) {
    recommendationsEl.innerHTML = '<p>No recommendations available.</p>';
    return;
  }

  recommendationsEl.innerHTML = items.map((item) => `
    <article class="recommendation-item">
      <div class="meta">
        <span class="badge">${item.category}</span>
        <strong>₹${Math.round(item.price)}</strong>
      </div>
      <h3>${item.title}</h3>
      <p>${item.description}</p>
      <p><strong>Why it fits:</strong> ${item.reason}</p>
    </article>
  `).join('');
}

function renderBudget(budget) {
  if (!budget) {
    budgetBreakdownEl.innerHTML = '<p>No budget data available.</p>';
    return;
  }

  const rows = [
    ['Stay', budget.stay],
    ['Food', budget.food],
    ['Activities', budget.activities],
    ['Transport', budget.transport],
    ['Total', budget.total],
  ];

  budgetBreakdownEl.innerHTML = rows.map(([label, value]) => `
    <div class="budget-row">
      <span>${label}</span>
      <strong>₹${Math.round(value)}</strong>
    </div>
  `).join('');
}

function renderItinerary(days) {
  if (!days || !days.length) {
    itineraryEl.innerHTML = '<p>No itinerary available.</p>';
    return;
  }

  itineraryEl.innerHTML = days.map((day) => `
    <article class="itinerary-item">
      <h3>${day.title}</h3>
      <p>${day.summary}</p>
      <ul>
        ${day.activities.map((activity) => `<li>${activity}</li>`).join('')}
      </ul>
    </article>
  `).join('');
}

function renderLocalIntelligence(tabName) {
  const city = results.destination || 'your destination';
  const map = {
    guide: `
      <div class="info-card">
        <h3>${city} at a glance</h3>
        <p>Plan around the historic core, a food district, and one scenic escape. Keep the first day easy, then let the second day deepen into the main interests of your trip.</p>
      </div>
    `,
    tips: `
      <div class="info-card">
        <h3>Smart travel tips</h3>
        <p>Start early for temple walks or markets, book one standout stay near the core, and leave enough slack for evenings if your style leans relaxed, foodie, or cultural.</p>
      </div>
    `,
    timing: `
      <div class="info-card">
        <h3>Best timing</h3>
        <p>Late morning is ideal for city walks and sightseeing, while sunset windows work especially well for scenic viewpoints, slow dinners, and photos.</p>
      </div>
    `,
  };

  localIntelligenceEl.innerHTML = map[tabName] || map.guide;
}

if (results.destination) {
  titleEl.textContent = `${results.destination} itinerary`;
  narrativeEl.textContent = results.narrative || 'Personalized recommendations for your selected travel style.';
  tripPersonaEl.textContent = localStorage.getItem('wandr-persona') || 'Couple';
  tripStyleEl.textContent = localStorage.getItem('wandr-style') || 'Cultural';
  tripBudgetEl.textContent = localStorage.getItem('wandr-budget') || 'Midrange';
  renderRecommendations(results.recommendations || []);
  renderBudget(results.budget_breakdown || null);
  renderItinerary(results.itinerary || []);
  renderLocalIntelligence('guide');

  document.querySelectorAll('.tab-button').forEach((button) => {
    button.addEventListener('click', () => {
      document.querySelectorAll('.tab-button').forEach((item) => item.classList.toggle('active', item === button));
      renderLocalIntelligence(button.dataset.tab);
    });
  });
} else {
  titleEl.textContent = 'No trip generated yet';
  narrativeEl.textContent = 'Start from the planner and generate your trip.';
  renderLocalIntelligence('guide');
}

document.getElementById('regenerate-button').addEventListener('click', () => {
  window.location.href = './planner.html';
});

document.getElementById('save-trip-button').addEventListener('click', async () => {
  if (!results.destination) {
    return;
  }

  const payload = {
    destination: results.destination,
    narrative: results.narrative,
    recommendations: results.recommendations,
    itinerary: results.itinerary,
    budget_breakdown: results.budget_breakdown,
  };

  const response = await fetch(`${API_BASE_URL}/api/trips/save`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  const data = await response.json();
  if (data.saved) {
    window.location.href = './saved-trips.html';
  }
});
