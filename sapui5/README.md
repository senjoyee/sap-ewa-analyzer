# EWA Analyzer (SAPUI5 Version)

This is the SAPUI5 (Fiori) frontend for the EWA Analyzer application. It replaces the legacy React frontend.

## Prerequisites

1.  **Node.js**: Ensure you have Node.js installed (LTS version recommended).
2.  **UI5 CLI**: The project uses the standard UI5 tooling.

## Installation

1.  Open a terminal in this directory (`sapui5`).
2.  Install dependencies:
    ```bash
    npm install
    ```

## Running the Application

1.  Start the development server:
    ```bash
    npm start
    ```
    or directly via UI5 CLI:
    ```bash
    ui5 serve -o index.html
    ```

2.  The application will open automatically in your default browser at `http://localhost:8080/index.html`.

## Project Structure

-   **webapp/**: Source folder.
    -   **controller/**: JavaScript Controllers.
    -   **view/**: XML Views.
    -   **model/**: Data models and configuration.
    -   **css/**: Custom styles.
    -   **i18n/**: Internationalization (text labels).
    -   **manifest.json**: Application descriptor.
    -   **Component.js**: Application component entry point.
-   **ui5.yaml**: UI5 Tooling configuration.
-   **package.json**: NPM dependencies and scripts.

## Configuration

The API backend URL is configured in `webapp/model/config.js`.
Default: `https://sap-ewa-analyzer-backend.azurewebsites.net`
