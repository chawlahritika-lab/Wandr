const API_BASE_URL = 'http://127.0.0.1:8001';

async function loadSavedTrips() {
  const list = document.getElementById('saved-trips-list');
  try {
    const response = await fetch(`${API_BASE_URL}/api/trips/saved`);
    const data = await response.json();

    if (!Array.isArray(data) || !data.length) {
      list.innerHTML = '<p>No saved trips yet.</p>';
      return;
    }

    list.innerHTML = data.map((trip) => `
      <article class="recommendation-item">
        <div class="meta">
          <span>${trip.destination}</span>
          <strong>#${trip.id}</strong>
        </div>
        <p>${trip.narrative}</p>
        <div class="saved-actions">
          <button class="secondary-button" type="button" data-delete-id="${trip.id}">Delete</button>
        </div>
      </article>
    `).join('');

    document.querySelectorAll('[data-delete-id]').forEach((button) => {
      button.addEventListener('click', async () => {
        const tripId = button.dataset.deleteId;
        const deleteResponse = await fetch(`${API_BASE_URL}/api/trips/saved/${tripId}`, {
          method: 'DELETE',
        });

        if (deleteResponse.ok) {
          loadSavedTrips();
        }
      });
    });
  } catch (error) {
    list.innerHTML = '<p>Unable to load saved trips right now.</p>';
  }
}

loadSavedTrips();
