import axios from 'axios';

// In production VITE_API_URL = your Render backend URL
// In development it's empty so relative /api/... calls hit the Vite proxy
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? '',
});

export default api;
