import React, { useEffect, useState } from 'react';
import './index.css';
import ReactDOM from 'react-dom/client';
import './App.css'; // We'll create this next
import App from './App'; // And this one too
import reportWebVitals from './reportWebVitals'; // And this
import { FluentProvider, webLightTheme, teamsLightTheme, teamsDarkTheme, teamsHighContrastTheme } from '@fluentui/react-components';
import * as microsoftTeams from '@microsoft/teams-js';
import { FONT_OPTIONS, DEFAULT_FONT_KEY } from './theme/fonts';

function Root() {
  // Load saved font preference or default to 'inter'
  const [currentFont, setCurrentFont] = useState(() => {
    return localStorage.getItem('ewa-font-preference') || DEFAULT_FONT_KEY;
  });

  const applyFont = (fontKey, baseTheme) => {
    const font = FONT_OPTIONS[fontKey] || FONT_OPTIONS[DEFAULT_FONT_KEY];
    return {
      ...baseTheme,
      fontFamilyBase: font.base,
      fontFamilyMonospace: font.mono,
    };
  };

  const [fluentTheme, setFluentTheme] = useState(() => applyFont(currentFont, webLightTheme));

  const setFontPreference = (fontKey) => {
    const nextKey = FONT_OPTIONS[fontKey] ? fontKey : DEFAULT_FONT_KEY;
    setCurrentFont(nextKey);
    localStorage.setItem('ewa-font-preference', nextKey);
  };

  // Expose font setter globally so FilePreview can access it
  useEffect(() => {
    window.__setAppFont = (fontKey) => {
      setFontPreference(fontKey);
    };
    window.__getFontOptions = () => FONT_OPTIONS;
    window.__getCurrentFont = () => currentFont;
    window.__resetAppFont = () => setFontPreference(DEFAULT_FONT_KEY);
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
      <App
        fontOptions={FONT_OPTIONS}
        currentFont={currentFont}
        onFontChange={setFontPreference}
      />
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
