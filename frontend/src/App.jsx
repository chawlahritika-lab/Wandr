import { useEffect, useState } from 'react';

// In dev, fall back to the local backend. In a production build, fall back to '' so
// requests are same-origin relative paths (e.g. "/api/trips/plan") - this matches the
// vercel.json rewrite that routes /api/* to the backend service on the same domain,
// so no VITE_API_URL needs to be configured for the standard single-domain deployment.
const API_BASE_URL = import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://127.0.0.1:8001' : '');
const destinations = ['Kyoto', 'Lisbon', 'Jaipur', 'Kuala Lumpur', 'Malaysia'];
const personas = ['Solo', 'Student', 'Couple', 'Honeymoon', 'Family', 'Backpacker'];
const budgets = ['Budget', 'Midrange', 'Premium', 'Luxe'];
const styles = ['Relaxed', 'Adventurous', 'Cultural', 'Luxury', 'Foodie', 'Wellness'];
const interests = ['Food', 'History', 'Nature', 'Nightlife', 'Shopping', 'Adventure', 'Wellness', 'Art'];
const FALLBACK_TOTAL_BUDGET_MAX = 300000;

function formatCurrency(currency, value) {
  try {
    return new Intl.NumberFormat(undefined, { style: 'currency', currency, maximumFractionDigits: 0 }).format(value);
  } catch {
    return `${currency || ''} ${Math.round(value)}`.trim();
  }
}

function convertAmount(amount, fromCurrency, toCurrency, rates) {
  if (!rates || !fromCurrency || !toCurrency || fromCurrency === toCurrency) return amount;
  const fromRate = rates[fromCurrency];
  const toRate = rates[toCurrency];
  if (!fromRate || !toRate) return amount;
  return (amount / fromRate) * toRate;
}

function formatApiError(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => item?.msg || item?.message)
      .filter(Boolean)
      .join(' ');
  }
  if (detail && typeof detail === 'object') {
    return detail.message || detail.detail || 'The request could not be completed.';
  }
  return 'Trip generation failed.';
}

const initialForm = {
  destination: 'Kyoto',
  brief: '',
  agent_decides: true,
  start_date: '2026-10-10',
  end_date: '2026-10-14',
  travelers: 2,
  persona: 'Couple',
  budget_level: 'Midrange',
  travel_style: 'Cultural',
  interests: ['Food', 'History'],
  price_min: null,
  price_max: null,
  custom_places: [],
  preference_notes: '',
};

function App() {
  const [form, setForm] = useState(initialForm);
  const [trip, setTrip] = useState(null);
  const [savedTrips, setSavedTrips] = useState([]);
  const [view, setView] = useState('planner');
  const [activeTab, setActiveTab] = useState('guide');
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [rates, setRates] = useState(null);
  const [budgetThresholds, setBudgetThresholds] = useState(null);

  useEffect(() => {
    loadSavedTrips();
    loadCurrencyMeta();
  }, []);

  async function loadSavedTrips() {
    try {
      const response = await fetch(`${API_BASE_URL}/api/trips/saved`);
      if (response.ok) setSavedTrips(await response.json());
    } catch {
      setStatus('The saved trips shelf is offline right now.');
    }
  }

  async function loadCurrencyMeta() {
    try {
      const [ratesResponse, thresholdsResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/api/currency/rates`),
        fetch(`${API_BASE_URL}/api/currency/budget-thresholds`),
      ]);
      if (ratesResponse.ok) setRates(await ratesResponse.json());
      if (thresholdsResponse.ok) setBudgetThresholds(await thresholdsResponse.json());
    } catch {
      // Currency conversion and price-range bounds are optional enhancements; fall back silently.
    }
  }

  function updateForm(field, value) {
    setForm((current) => ({ ...current, [field]: value }));
  }

  function toggleInterest(value) {
    setForm((current) => ({
      ...current,
      interests: current.interests.includes(value)
        ? current.interests.filter((interest) => interest !== value)
        : [...current.interests, value],
    }));
  }

  async function generateTrip(event, overrides = {}) {
    event.preventDefault();
    setLoading(true);
    setStatus('');
    try {
      const response = await fetch(`${API_BASE_URL}/api/trips/plan`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ...form, ...overrides, travelers: Number(form.travelers) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(formatApiError(data.detail));
      setTrip(data);
      setView('results');
    } catch (error) {
      setStatus(error.message);
    } finally {
      setLoading(false);
    }
  }

  async function saveTrip() {
    if (!trip || saving) return;
    setSaving(true);
    try {
      const response = await fetch(`${API_BASE_URL}/api/trips/save`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(trip),
      });
      if (response.ok) {
        setStatus('Trip saved to your shelf.');
        await loadSavedTrips();
      }
    } finally {
      setSaving(false);
    }
  }

  async function deleteTrip(id) {
    const response = await fetch(`${API_BASE_URL}/api/trips/saved/${id}`, { method: 'DELETE' });
    if (response.ok) setSavedTrips((current) => current.filter((item) => item.id !== id));
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <button className="brand" onClick={() => setView('planner')}><span>W</span> WANDR</button>
        <nav>
          <button className={view === 'planner' ? 'nav-link active' : 'nav-link'} onClick={() => setView('planner')}>Plan a trip</button>
          <button className={view === 'saved' ? 'nav-link active' : 'nav-link'} onClick={() => { loadSavedTrips(); setView('saved'); }}>Saved trips <span className="count">{savedTrips.length}</span></button>
        </nav>
      </header>

      <main>
        {view === 'planner' && <Planner form={form} updateForm={updateForm} toggleInterest={toggleInterest} onSubmit={generateTrip} loading={loading} status={status} budgetThresholds={budgetThresholds} />}
        {view === 'results' && <Results trip={trip} activeTab={activeTab} setActiveTab={setActiveTab} onSave={saveTrip} saving={saving} onBack={() => setView('planner')} status={status} rates={rates} />}
        {view === 'saved' && <SavedTrips trips={savedTrips} onDelete={deleteTrip} onBack={() => setView('planner')} />}
      </main>
    </div>
  );
}

function Planner({ form, updateForm, toggleInterest, onSubmit, loading, status, budgetThresholds }) {
  const [customPlaceDraft, setCustomPlaceDraft] = useState('');
  const priceCeiling = budgetThresholds ? Math.round(budgetThresholds.Luxe * 12) : FALLBACK_TOTAL_BUDGET_MAX;

  function addCustomPlace() {
    const trimmed = customPlaceDraft.trim();
    if (!trimmed || form.custom_places.includes(trimmed)) {
      setCustomPlaceDraft('');
      return;
    }
    updateForm('custom_places', [...form.custom_places, trimmed]);
    setCustomPlaceDraft('');
  }

  function removeCustomPlace(place) {
    updateForm('custom_places', form.custom_places.filter((item) => item !== place));
  }

  function handleSubmit(event) {
    const trimmed = customPlaceDraft.trim();
    if (!trimmed) {
      onSubmit(event, {});
      return;
    }
    // Auto-commit any place left sitting in the checklist input (not yet confirmed
    // with the Add button) so it isn't silently dropped when the form is submitted.
    const mergedCustomPlaces = form.custom_places.includes(trimmed) ? form.custom_places : [...form.custom_places, trimmed];
    updateForm('custom_places', mergedCustomPlaces);
    setCustomPlaceDraft('');
    onSubmit(event, { custom_places: mergedCustomPlaces });
  }

  return <section className="planner-layout">
    <div className="intro-panel">
      <p className="eyebrow">A trip that sounds like you</p>
      <h1>Go somewhere<br /><em>more personal.</em></h1>
      <p className="intro-copy">Wandr turns your travel personality into a considered itinerary, with the right rhythm, places, and local flavor.</p>
      <div className="route-mark"><span>KYOTO</span><i></i><span>YOUR WAY</span></div>
    </div>
    <form className="planner-form" onSubmit={handleSubmit}>
      <div className="form-heading"><span>01</span><div><p className="eyebrow">The essentials</p><h2>Set the scene</h2></div></div>
      <label>Where do you want to go?<input list="destination-suggestions" value={form.destination} placeholder="Try Thailand, Patagonia, or anywhere you dream of" onChange={(event) => updateForm('destination', event.target.value)} /><datalist id="destination-suggestions">{destinations.map((item) => <option key={item} value={item} />)}</datalist></label>
      <label className="agent-toggle"><input type="checkbox" checked={form.agent_decides} onChange={(event) => updateForm('agent_decides', event.target.checked)} /><span>Let Wandr decide the destination and travel profile</span></label>
      <div className="two-col"><label>Start date<input type="date" value={form.start_date} onChange={(event) => updateForm('start_date', event.target.value)} /></label><label>End date<input type="date" value={form.end_date} onChange={(event) => updateForm('end_date', event.target.value)} /></label></div>
      <label>Travelers<input type="number" min="1" max="12" value={form.travelers} onChange={(event) => updateForm('travelers', event.target.value)} /></label>
      <ChoiceGroup label="I am traveling as" values={personas} selected={form.persona} onSelect={(value) => updateForm('persona', value)} />
      <ChoiceGroup label="My comfort zone" values={budgets} selected={form.budget_level} onSelect={(value) => updateForm('budget_level', value)} />
      <ChoiceGroup label="My travel rhythm" values={styles} selected={form.travel_style} onSelect={(value) => updateForm('travel_style', value)} />
      <fieldset><legend>I'm drawn to</legend><div className="chip-grid">{interests.map((item) => <button type="button" className={form.interests.includes(item) ? 'chip selected' : 'chip'} key={item} onClick={() => toggleInterest(item)}>{item}</button>)}</div></fieldset>

      <div className="form-heading"><span>02</span><div><p className="eyebrow">Fine-tune it</p><h2>Narrow the fit</h2></div></div>
      <PriceRangeSlider
        label="Total trip budget (target, local currency)"
        min={0}
        max={priceCeiling}
        valueMin={form.price_min ?? 0}
        valueMax={form.price_max ?? priceCeiling}
        onChangeMin={(value) => updateForm('price_min', value)}
        onChangeMax={(value) => updateForm('price_max', value)}
      />
      <p className="field-hint">Wandr will substitute cheaper or pricier picks to try to land your estimated trip total in this range.</p>
      <fieldset>
        <legend>Must-see places (your checklist)</legend>
        <div className="checklist-input">
          <input
            type="text"
            placeholder="Add a place you don't want to miss"
            value={customPlaceDraft}
            onChange={(event) => setCustomPlaceDraft(event.target.value)}
            onKeyDown={(event) => { if (event.key === 'Enter') { event.preventDefault(); addCustomPlace(); } }}
          />
          <button type="button" className="secondary-button small" onClick={addCustomPlace}>Add</button>
        </div>
        {form.custom_places.length > 0 && <div className="chip-grid">{form.custom_places.map((place) => <button type="button" className="chip removable" key={place} onClick={() => removeCustomPlace(place)}>{place} <span>×</span></button>)}</div>}
      </fieldset>
      <label>Tell us about specific places or activities you're excited about
        <textarea
          rows="3"
          placeholder="e.g. I really want to see the sunrise torii gates and try local street food"
          value={form.preference_notes}
          onChange={(event) => updateForm('preference_notes', event.target.value)}
        />
      </label>

      {status && <p className="error-message">{status}</p>}
      <button className="primary-button" disabled={loading || !form.interests.length}>{loading ? 'Shaping your trip...' : 'Generate my trip'} <span>↗</span></button>
    </form>
  </section>;
}

function PriceRangeSlider({ label, min, max, valueMin, valueMax, onChangeMin, onChangeMax }) {
  const span = Math.max(max - min, 1);
  const percentMin = ((valueMin - min) / span) * 100;
  const percentMax = ((valueMax - min) / span) * 100;
  return (
    <div className="price-range">
      <div className="price-range-header"><span>{label}</span><strong>{Math.round(valueMin)} – {Math.round(valueMax)}</strong></div>
      <div className="price-range-track">
        <div className="price-range-fill" style={{ left: `${percentMin}%`, right: `${100 - percentMax}%` }} />
        <input type="range" min={min} max={max} value={valueMin} onChange={(event) => onChangeMin(Math.min(Number(event.target.value), valueMax))} />
        <input type="range" min={min} max={max} value={valueMax} onChange={(event) => onChangeMax(Math.max(Number(event.target.value), valueMin))} />
      </div>
    </div>
  );
}

function ChoiceGroup({ label, values, selected, onSelect }) {
  return <fieldset><legend>{label}</legend><div className="choice-grid">{values.map((item) => <button type="button" key={item} className={selected === item ? 'choice selected' : 'choice'} onClick={() => onSelect(item)}>{item}</button>)}</div></fieldset>;
}

function crowdBadgeClass(level) {
  return `crowd-badge crowd-${(level || 'medium').toLowerCase()}`;
}

function popularityBadgeClass(value) {
  return value === 'Hidden gem' ? 'popularity-badge hidden' : 'popularity-badge popular';
}

function RecommendationCard({ item, currency, displayCurrency, rates }) {
  const price = convertAmount(item.price, currency, displayCurrency, rates);
  return (
    <article className="recommendation-item" key={item.id}>
      <div className="item-meta"><span>{item.category}</span><strong>{formatCurrency(displayCurrency || currency, price)}</strong></div>
      <h3>{item.title}</h3>
      <p>{item.description}</p>
      <div className="item-badges">
        <span className={popularityBadgeClass(item.popularity)}>{item.popularity}</span>
        <span className={crowdBadgeClass(item.crowd_density)}>Crowd: {item.crowd_density}</span>
        <span className="rating-badge">★ {item.rating.toFixed(1)}</span>
      </div>
      {item.best_time_to_visit && <p className="item-detail-row"><strong>Best time to visit:</strong> {item.best_time_to_visit}</p>}
      {item.reviews?.length > 0 && (
        <div className="item-detail-row">
          <strong>Reviews</strong>
          <ul className="review-list">{item.reviews.map((review) => <li key={review}>{review}</li>)}</ul>
        </div>
      )}
      <small>{item.reason}</small>
    </article>
  );
}

function Results({ trip, activeTab, setActiveTab, onSave, saving, onBack, status, rates }) {
  const [displayCurrency, setDisplayCurrency] = useState(trip?.currency || '');
  if (!trip) return null;
  const tabs = {
    guide: ['A considered first look', `Use ${trip.destination}'s historic core as your anchor, then let one food neighborhood and one slower scenic escape shape the edges of the trip.`],
    tips: ['Make room for the in-between', 'Start early for the most atmospheric walks, keep one evening open, and let the best meals take their time.'],
    timing: ['Follow the light', 'Late morning is made for city wandering. Save sunset for viewpoints, long dinners, and the moments you did not plan for.'],
  };
  const currencyOptions = rates ? Object.keys(rates.rates) : [trip.currency].filter(Boolean);
  const popularPicks = trip.recommendations.filter((item) => item.popularity !== 'Hidden gem');
  const hiddenGems = trip.recommendations.filter((item) => item.popularity === 'Hidden gem');
  const budgetTotal = (label, value) => convertAmount(value, trip.currency, displayCurrency, rates?.rates);

  return <section className="results-view">
    <button className="back-link" onClick={onBack}>← Refine your brief</button>
    <div className="results-hero"><div><p className="eyebrow">Your personal route</p><h1>{trip.destination}<br /><em>in your language.</em></h1><p className="lead">{trip.narrative}</p></div><div className="result-actions"><button className="secondary-button" onClick={onSave} disabled={saving}>{saving ? 'Saving...' : 'Save trip'}</button><button className="primary-button small" onClick={onBack}>Start over</button></div></div>
    {status && <p className="success-message">{status}</p>}
    <div className="score-strip">
      <span>Profile <strong>{trip.persona} · {trip.travelers} traveler{trip.travelers === 1 ? '' : 's'}</strong></span>
      <span>Rhythm <strong>{trip.travel_style} · {trip.trip_days} days</strong></span>
      <span>Budget <strong>{trip.budget_level}</strong></span>
      <span>Resolved by <strong>{trip.resolution_source || 'catalog'}</strong></span>
      {currencyOptions.length > 0 && (
        <span className="currency-picker">Currency
          <select className="currency-select" value={displayCurrency || trip.currency} onChange={(event) => setDisplayCurrency(event.target.value)}>
            {!currencyOptions.includes(trip.currency) && <option value={trip.currency}>{trip.currency}</option>}
            {currencyOptions.map((code) => <option key={code} value={code}>{code}</option>)}
          </select>
        </span>
      )}
    </div>
    {trip.agent_rationale && <div className="resolution-note"><span className="eyebrow">Wandr's read</span><p>{trip.agent_rationale}</p></div>}
    <div className="result-columns">
      <div className="result-panel">
        <div className="panel-heading"><p className="eyebrow">Selected for you</p><h2>Places with a point of view</h2></div>
        {popularPicks.length > 0 && <div className="section-group"><h4>Popular picks</h4>{popularPicks.map((item) => <RecommendationCard key={item.id} item={item} currency={trip.currency} displayCurrency={displayCurrency} rates={rates?.rates} />)}</div>}
        {hiddenGems.length > 0 && <div className="section-group"><h4>Hidden gems</h4>{hiddenGems.map((item) => <RecommendationCard key={item.id} item={item} currency={trip.currency} displayCurrency={displayCurrency} rates={rates?.rates} />)}</div>}
      </div>
      <div className="result-side">
        <div className="result-panel budget-panel">
          <p className="eyebrow">The shape of it</p>
          <h2>Budget</h2>
          {Object.entries(trip.budget_breakdown).map(([label, value]) => <div className={label === 'total' ? 'budget-row total' : 'budget-row'} key={label}><span>{label}</span><strong>{formatCurrency(displayCurrency || trip.currency, budgetTotal(label, value))}</strong></div>)}
        </div>
        {trip.custom_places?.length > 0 && (
          <div className="result-panel checklist-panel">
            <p className="eyebrow">Guaranteed in your itinerary</p>
            <h2>Your checklist</h2>
            <ul className="checklist-summary">{trip.custom_places.map((place) => <li key={place}>{place}</li>)}</ul>
          </div>
        )}
        <div className="result-panel local-panel"><p className="eyebrow">Beyond the itinerary</p><div className="tabs">{Object.keys(tabs).map((tab) => <button key={tab} className={activeTab === tab ? 'tab active' : 'tab'} onClick={() => setActiveTab(tab)}>{tab}</button>)}</div><h3>{tabs[activeTab][0]}</h3><p>{tabs[activeTab][1]}</p></div>
      </div>
    </div>
    <div className="result-panel itinerary-panel"><div className="panel-heading"><p className="eyebrow">Your days, with room to breathe</p><h2>Itinerary</h2></div><div className="itinerary-grid">{trip.itinerary.map((day) => <article key={day.day}><span className="day-number">0{day.day}</span><h3>{day.title}</h3><p>{day.summary}</p><ul>{day.activities.map((activity) => <li className={activity.startsWith('Your pick:') ? 'custom-activity' : ''} key={activity}>{activity}</li>)}</ul></article>)}</div></div>
  </section>;
}

function SavedTrips({ trips, onDelete, onBack }) {
  return <section className="saved-view"><button className="back-link" onClick={onBack}>← Plan another trip</button><p className="eyebrow">Your collection</p><h1>Saved <em>routes.</em></h1><p className="lead">The trips worth keeping close.</p>{!trips.length ? <div className="empty-state">No saved trips yet. Your next one is one good brief away.</div> : <div className="saved-grid">{trips.map((trip) => <article className="saved-card" key={trip.id}><div><span className="eyebrow">{trip.destination}</span><h2>Trip #{trip.id}</h2><p>{trip.narrative}</p></div><button className="delete-button" onClick={() => onDelete(trip.id)}>Delete</button></article>)}</div>}</section>;
}

export default App;
