// Centralized API configuration
// - Reads from runtime window.__ENV__ (if injected) or CRA env (REACT_APP_API_BASE)
// - Defaults to same-origin (empty string) so CRA proxy can be used in dev

export const API_BASE = (() => {
  try {
    const runtime = typeof window !== 'undefined' && window.__ENV__ && window.__ENV__.REACT_APP_API_BASE;
    const env = typeof process !== 'undefined' && process.env && process.env.REACT_APP_API_BASE;
    const baseRaw = (runtime || env || '').toString().trim();
    // Remove trailing slash
    return baseRaw.replace(/\/$/, '');
  } catch (e) {
    return '';
  }
})();

export const apiUrl = (path = '') => {
  const cleanPath = path ? (path.startsWith('/') ? path : `/${path}`) : '';
  return `${API_BASE}${cleanPath}`;
};
