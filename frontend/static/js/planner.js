const form = document.getElementById('planner-form');
const API_BASE_URL = 'http://127.0.0.1:8001';
const hiddenFields = {
  persona: document.getElementById('persona'),
  budget_level: document.getElementById('budget_level'),
  travel_style: document.getElementById('travel_style'),
  interests: document.getElementById('interests')
};

const cards = document.querySelectorAll('.choice-card');
const interestButtons = document.querySelectorAll('.interest-chip');

function selectSingleValue(group, value) {
  document.querySelectorAll(`[data-group="${group}"] .choice-card`).forEach((button) => {
    const isSelected = button.dataset.value === value;
    button.classList.toggle('selected', isSelected);
    button.setAttribute('aria-pressed', String(isSelected));
  });
  hiddenFields[group].value = value;
}

function toggleInterest(value) {
  const input = hiddenFields.interests;
  const selected = new Set((input.value || '').split(',').filter(Boolean));
  if (selected.has(value)) {
    selected.delete(value);
  } else {
    selected.add(value);
  }
  input.value = Array.from(selected).join(',');

  document.querySelectorAll(`.interest-chip[data-value="${value}"]`).forEach((button) => {
    const active = selected.has(value);
    button.classList.toggle('selected', active);
    button.setAttribute('aria-pressed', String(active));
  });
}

cards.forEach((button) => {
  const field = button.closest('[data-group]')?.dataset.group;
  button.addEventListener('click', () => {
    selectSingleValue(field, button.dataset.value);
  });
});

interestButtons.forEach((button) => {
  button.addEventListener('click', () => {
    toggleInterest(button.dataset.value);
  });
});

form.addEventListener('submit', async (event) => {
  event.preventDefault();
  const formData = new FormData(form);
  const payload = {
    destination: formData.get('destination').toString().trim() || 'Kyoto',
    start_date: formData.get('start_date').toString(),
    end_date: formData.get('end_date').toString(),
    travelers: Number(formData.get('travelers') || 2),
    persona: formData.get('persona').toString(),
    budget_level: formData.get('budget_level').toString(),
    travel_style: formData.get('travel_style').toString(),
    interests: (formData.get('interests') || '').split(',').filter(Boolean)
  };

  localStorage.setItem('wandr-persona', payload.persona);
  localStorage.setItem('wandr-style', payload.travel_style);
  localStorage.setItem('wandr-budget', payload.budget_level);

  const response = await fetch(`${API_BASE_URL}/api/trips/plan`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (!response.ok) {
    console.error('Trip generation failed');
    return;
  }

  const result = await response.json();
  localStorage.setItem('wandr-trip-result', JSON.stringify(result));
  window.location.href = './results.html';
});

selectSingleValue('persona', hiddenFields.persona.value);
selectSingleValue('budget_level', hiddenFields.budget_level.value);
selectSingleValue('travel_style', hiddenFields.travel_style.value);

const interestValues = (hiddenFields.interests.value || '').split(',').filter(Boolean);
interestValues.forEach((value) => {
  document.querySelectorAll(`.interest-chip[data-value="${value}"]`).forEach((button) => {
    button.classList.add('selected');
    button.setAttribute('aria-pressed', 'true');
  });
});
