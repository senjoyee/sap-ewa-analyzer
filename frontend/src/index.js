import React, { useEffect, useState } from 'react';
import './index.css';
import ReactDOM from 'react-dom/client';
import './App.css'; // We'll create this next
import App from './App'; // And this one too
import reportWebVitals from './reportWebVitals'; // And this
import { FluentProvider, webLightTheme, teamsLightTheme, teamsDarkTheme, teamsHighContrastTheme } from '@fluentui/react-components';
import * as microsoftTeams from '@microsoft/teams-js';

// Font configurations
const FONT_OPTIONS = {
  inter: {
    name: 'Inter',
    base: '"Inter", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: '"JetBrains Mono", Consolas, "Courier New", monospace',
  },
  segoe: {
    name: 'Segoe UI',
    base: '"Segoe UI", system-ui, -apple-system, Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: 'Consolas, "Courier New", monospace',
  },
  roboto: {
    name: 'Roboto',
    base: '"Roboto", system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif',
    mono: '"Roboto Mono", Consolas, "Courier New", monospace',
  },
  opensans: {
    name: 'Open Sans',
    base: '"Open Sans", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: '"Source Code Pro", Consolas, "Courier New", monospace',
  },
  lato: {
    name: 'Lato',
    base: '"Lato", system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: '"Fira Code", Consolas, "Courier New", monospace',
  },
  system: {
    name: 'System Default',
    base: 'system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif',
    mono: 'ui-monospace, Consolas, "Courier New", monospace',
  },
};

function Root() {
  // Load saved font preference or default to 'inter'
  const [currentFont, setCurrentFont] = useState(() => {
    return localStorage.getItem('ewa-font-preference') || 'inter';
  });

  const applyFont = (fontKey, baseTheme) => {
    const font = FONT_OPTIONS[fontKey] || FONT_OPTIONS.inter;
    return {
      ...baseTheme,
      fontFamilyBase: font.base,
      fontFamilyMonospace: font.mono,
    };
  };

  const [fluentTheme, setFluentTheme] = useState(applyFont(currentFont, webLightTheme));

  // Expose font setter globally so FilePreview can access it
  useEffect(() => {
    window.__setAppFont = (fontKey) => {
      if (FONT_OPTIONS[fontKey]) {
        setCurrentFont(fontKey);
        localStorage.setItem('ewa-font-preference', fontKey);
      }
    };
    window.__getFontOptions = () => FONT_OPTIONS;
    window.__getCurrentFont = () => currentFont;
  }, [currentFont]);

  useEffect(() => {
    let mounted = true;
    const applyTeamsTheme = (themeName) => {
      const base = themeName === 'dark' ? teamsDarkTheme : themeName === 'contrast' ? teamsHighContrastTheme : teamsLightTheme;
      if (mounted) setFluentTheme(applyFont(currentFont, base));
    };

    const init = async () => {
      try {
        await microsoftTeams.app.initialize();
        const ctx = await microsoftTeams.app.getContext();
        applyTeamsTheme((ctx.app && ctx.app.theme) || ctx.theme || 'default');
        microsoftTeams.app.registerOnThemeChangeHandler((theme) => applyTeamsTheme(theme));
      } catch (e) {
        // Not running inside Teams, apply font to web theme
        if (mounted) setFluentTheme(applyFont(currentFont, webLightTheme));
      }
    };
    init();
    return () => {
      mounted = false;
    };
  }, [currentFont]);

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
