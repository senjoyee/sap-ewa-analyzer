import React, { useEffect, useState } from 'react';
import '@fontsource/noto-sans/400.css';
import '@fontsource/noto-sans/600.css';
import './index.css'; // Global dark theme styles
import ReactDOM from 'react-dom/client';
import './App.css'; // We'll create this next
import App from './App'; // And this one too
import reportWebVitals from './reportWebVitals'; // And this
import { FluentProvider, webLightTheme, teamsLightTheme, teamsDarkTheme, teamsHighContrastTheme } from '@fluentui/react-components';
import * as microsoftTeams from '@microsoft/teams-js';

function Root() {
  const [fluentTheme, setFluentTheme] = useState(webLightTheme);

  useEffect(() => {
    let mounted = true;
    const applyTeamsTheme = (themeName) => {
      const t = themeName === 'dark' ? teamsDarkTheme : themeName === 'contrast' ? teamsHighContrastTheme : teamsLightTheme;
      if (mounted) setFluentTheme(t);
    };

    const init = async () => {
      try {
        await microsoftTeams.app.initialize();
        const ctx = await microsoftTeams.app.getContext();
        applyTeamsTheme((ctx.app && ctx.app.theme) || ctx.theme || 'default');
        microsoftTeams.app.registerOnThemeChangeHandler((theme) => applyTeamsTheme(theme));
      } catch (e) {
        // Not running inside Teams, keep webLightTheme
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
