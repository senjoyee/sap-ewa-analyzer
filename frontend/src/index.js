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
  // Initialize with Inter immediately so non-Teams environments get the font
  const [fluentTheme, setFluentTheme] = useState(withInter(webLightTheme));

  useEffect(() => {
    let mounted = true;
    const applyTeamsTheme = (themeName) => {
      const base = themeName === 'dark' ? teamsDarkTheme : themeName === 'contrast' ? teamsHighContrastTheme : teamsLightTheme;
      if (mounted) setFluentTheme(withInter(base));
    };

    const init = async () => {
      try {
        await microsoftTeams.app.initialize();
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
