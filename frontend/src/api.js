import axios from 'axios';

const API_BASE = process.env.REACT_APP_API_URL || '/api';

const api = axios.create({
  baseURL: API_BASE,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  }
});

// Add CSRF token to requests
api.interceptors.request.use(config => {
  const csrfToken = getCookie('csrftoken');
  if (csrfToken) {
    config.headers['X-CSRFToken'] = csrfToken;
  }
  return config;
});

function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

export const auth = {
  register: (username, password, email) => 
    api.post('/register/', { username, password, email }),
  login: (username, password) => 
    api.post('/login/', { username, password }),
  logout: () => 
    api.post('/logout/'),
};

export const game = {
  getState: () => 
    api.get('/game-state/'),
  craft: (objectAId, objectBId) => 
    api.post('/craft/', { object_a_id: objectAId, object_b_id: objectBId }),
  place: (objectId, x, y) => 
    api.post('/place/', { object_id: objectId, x, y }),
  remove: (placedId) => 
    api.post('/remove/', { placed_id: placedId }),
  unlockEra: (eraName) => 
    api.post('/unlock-era/', { era_name: eraName }),
  export: () => 
    api.get('/export/'),
  import: (data) => 
    api.post('/import/', data),
  redeemUpgradeKey: (key) =>
    api.post('/redeem-upgrade-key/', { key }),
};

export default api;
