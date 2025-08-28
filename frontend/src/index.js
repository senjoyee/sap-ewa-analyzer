import React, { useEffect, useState } from 'react';
import './index.css';
import ReactDOM from 'react-dom/client';
import './App.css'; // We'll create this next
import App from './App'; // And this one too
import reportWebVitals from './reportWebVitals'; // And this
import { FluentProvider, webLightTheme, teamsLightTheme, teamsDarkTheme, teamsHighContrastTheme } from '@fluentui/react-components';
import * as microsoftTeams from '@microsoft/teams-js';

function Root() {
  const withInter = (t) => ({
    ...t,
    fontFamilyBase: '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    fontFamilyMonospace: '"JetBrains Mono", Consolas, "Courier New", monospace',
  });
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
  // Initialize with Inter immediately so non-Teams environments get the font
  const [fluentTheme, setFluentTheme] = useState(withInter(webLightTheme));

  useEffect(() => {
    let mounted = true;
    const applyTeamsTheme = (themeName) => {
      const base = themeName === 'dark' ? teamsDarkTheme : themeName === 'contrast' ? teamsHighContrastTheme : teamsLightTheme;
      const adjusted = withScaledFonts(base, 0.9);
      if (mounted) setFluentTheme(withInter(adjusted));
    };

    const init = async () => {
      try {
        await microsoftTeams.app.initialize();
        // Notify Teams host as soon as initialization completes to avoid
        // transient desktop banners if getContext is slow/intermittent.
        if (microsoftTeams?.appInitialization?.notifySuccess) {
          microsoftTeams.appInitialization.notifySuccess();
        }
        const ctx = await microsoftTeams.app.getContext();
        applyTeamsTheme((ctx.app && ctx.app.theme) || ctx.theme || 'default');
        microsoftTeams.app.registerOnThemeChangeHandler((theme) => applyTeamsTheme(theme));
      } catch (e) {
        // Not running inside Teams, ensure Inter override is applied
        if (mounted) setFluentTheme(withInter(webLightTheme));
      }
    };
    init();
    return () => {
      mounted = false;
    };
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
