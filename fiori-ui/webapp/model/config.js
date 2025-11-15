sap.ui.define([], function () {
  "use strict";

  var API_BASE = "";

  try {
    if (window && window.__ENV__ && window.__ENV__.REACT_APP_API_BASE) {
      var baseRaw = window.__ENV__.REACT_APP_API_BASE.toString().trim();
      API_BASE = baseRaw.replace(/\/$/, "");
    }
  } catch (e) {
    // Ignore and fall through to default handling below
  }

  // If no explicit runtime base URL is provided, use the fixed HTTPS backend URL
  if (!API_BASE) {
    API_BASE = "https://sap-ewa-analyzer-backend.azurewebsites.net";
  }

  function apiUrl(path) {
    var cleanPath = path || "";
    if (cleanPath && cleanPath.charAt(0) !== "/") {
      cleanPath = "/" + cleanPath;
    }
    return API_BASE + cleanPath;
  }

  return {
    API_BASE: API_BASE,
    apiUrl: apiUrl
  };
});
