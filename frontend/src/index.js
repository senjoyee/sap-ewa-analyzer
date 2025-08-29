import React, { useEffect, useState } from 'react';
import './index.css';
import ReactDOM from 'react-dom/client';
import './App.css'; // We'll create this next
import App from './App'; // And this one too
import reportWebVitals from './reportWebVitals'; // And this
import { FluentProvider, webLightTheme, teamsLightTheme, teamsDarkTheme, teamsHighContrastTheme } from '@fluentui/react-components';
import * as microsoftTeams from '@microsoft/teams-js';

function Root() {
  const fontFamilies = {
    'inter': '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'roboto': '"Roboto", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'open-sans': '"Open Sans", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'source-sans-3': '"Source Sans 3", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    'system-ui': 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
  };
  const allowedFontPrefs = ['inter', 'roboto', 'open-sans', 'source-sans-3', 'system-ui', 'teams'];
  const withFontPref = (t, pref) => {
    const base = fontFamilies[pref];
    if (!base) return t; // teams or unknown
    return {
      ...t,
      fontFamilyBase: base,
      fontFamilyMonospace: '"JetBrains Mono", Consolas, "Courier New", monospace',
    };
  };
  const withScaledFonts = (t, factor) => {
    const scale = (px) => {
      if (typeof px !== 'string' || !px.endsWith('px')) return px;
      const n = parseFloat(px);
      const scaled = Math.round(n * factor * 100) / 100;
      return `${scaled}px`;
    };
    const keys = [
      'fontSizeBase100','fontSizeBase200','fontSizeBase300','fontSizeBase400','fontSizeBase500','fontSizeBase600','fontSizeBase700',
      'fontSizeHero700','fontSizeHero800','fontSizeHero900','fontSizeHero1000'
    ];
    const overrides = {};
    keys.forEach(k => { if (t[k]) overrides[k] = scale(t[k]); });
    return { ...t, ...overrides };
  };
  // Persisted font preference
  const getInitialFontPref = () => {
    const v = typeof window !== 'undefined' ? window.localStorage.getItem('fontPref') : null;
    return allowedFontPrefs.includes(v) ? v : 'open-sans';
  };
  const [fontPref, setFontPref] = useState(getInitialFontPref);
  const [fluentTheme, setFluentTheme] = useState(() => {
    const init = getInitialFontPref();
    return init === 'teams' ? webLightTheme : withFontPref(webLightTheme, init);
  });
  const [inTeams, setInTeams] = useState(false);
  const [currentTeamsTheme, setCurrentTeamsTheme] = useState('default');

  const applyFontPref = (theme) => (fontPref === 'teams' ? theme : withFontPref(theme, fontPref));

  // Expose a global setter for app-level font preference changes
  useEffect(() => {
    window.__setAppFontPref = (pref) => {
      const next = allowedFontPrefs.includes(pref) ? pref : 'open-sans';
      try { window.localStorage.setItem('fontPref', next); } catch {}
      setFontPref(next);
    };
    return () => { delete window.__setAppFontPref; };
  }, []);

  // Recompute theme when font preference or Teams theme changes
  useEffect(() => {
    if (inTeams) {
      const base = currentTeamsTheme === 'dark' ? teamsDarkTheme : currentTeamsTheme === 'contrast' ? teamsHighContrastTheme : teamsLightTheme;
      const adjusted = withScaledFonts(base, 0.9);
      setFluentTheme(applyFontPref(adjusted));
    } else {
      setFluentTheme(applyFontPref(webLightTheme));
    }
  }, [fontPref, inTeams, currentTeamsTheme]);

  useEffect(() => {
    let mounted = true;
    const applyTeamsTheme = (themeName) => {
      if (!mounted) return;
      setInTeams(true);
      setCurrentTeamsTheme(themeName);
      const base = themeName === 'dark' ? teamsDarkTheme : themeName === 'contrast' ? teamsHighContrastTheme : teamsLightTheme;
      const adjusted = withScaledFonts(base, 0.9);
      setFluentTheme(applyFontPref(adjusted));
    };

    const init = async () => {
      try {
        await microsoftTeams.app.initialize();
        if (microsoftTeams?.appInitialization?.notifySuccess) {
          microsoftTeams.appInitialization.notifySuccess();
        }
        const ctx = await microsoftTeams.app.getContext();
        applyTeamsTheme((ctx.app && ctx.app.theme) || ctx.theme || 'default');
        microsoftTeams.app.registerOnThemeChangeHandler((theme) => applyTeamsTheme(theme));
      } catch (e) {
        // Not running inside Teams
        if (mounted) {
          setInTeams(false);
          setFluentTheme(applyFontPref(webLightTheme));
        }
      }
    };
    init();
    return () => { mounted = false; };
  }, []);

  return (
    <FluentProvider theme={fluentTheme}>
      <App />
    </FluentProvider>
  );
}

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <Root />
  </React.StrictMode>
);

// If you want to start measuring performance in your app, pass a function
// to log results (for example: reportWebVitals(console.log))
// or send to an analytics endpoint. Learn more: https://bit.ly/CRA-vitals
reportWebVitals();
