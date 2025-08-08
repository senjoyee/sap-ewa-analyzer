# EWA Analyzer Frontend

This project was bootstrapped with manual steps, mimicking `create-react-app`.

## Backend API Endpoints

Base URL (local development): `http://localhost:8001`

- __/api/upload__ — `frontend/src/components/FileUpload.js:214` — POST
- __/api/files__ — `frontend/src/components/FileList.js:792` — GET
- __/api/analyze__ — `frontend/src/components/FileList.js:425` — POST
- __/api/analyze-ai__ — `frontend/src/components/FileList.js:464` — POST
- __/api/reprocess-ai__ — `frontend/src/components/FileList.js:560` — POST
- __/api/process-sequential__ — `frontend/src/components/FileList.js:303` — POST
- __/api/process-and-analyze__ — `frontend/src/components/FileList.js:662` — POST
- __/api/analysis-status/:fileName__ — `frontend/src/components/FileList.js:729` — GET
- __/api/delete-analysis__ — `frontend/src/components/FileList.js:201,622` — DELETE
- __/api/download/:file__ — `frontend/src/components/FileList.js:517`, `frontend/src/components/FilePreview.js:624,632,638` — GET
- __/api/export-pdf__ — `frontend/src/components/FilePreview.js:589` — GET
- __/api/chat__ — `frontend/src/components/DocumentChat.js:293` — POST

Notes:
- All API requests use the `API_BASE` constant set to `http://localhost:8001` in each component for local testing.
- If you expose a different backend port or host, update the `API_BASE` values or provide `REACT_APP_API_BASE` at runtime.

## Available Scripts

In the project directory, you can run:

### `npm install`

Installs all the necessary dependencies for the project. You need to run this first.

### `npm start`

Runs the app in the development mode.\
Open [http://localhost:3000](http://localhost:3000) to view it in your browser.

The page will reload when you make changes.\
You may also see any lint errors in the console.

### `npm test`

Launches the test runner in the interactive watch mode.\
See the section about [running tests](https://facebook.github.io/create-react-app/docs/running-tests) for more information.

### `npm run build`

Builds the app for production to the `build` folder.\
It correctly bundles React in production mode and optimizes the build for the best performance.

The build is minified and the filenames include the hashes.\
Your app is ready to be deployed!

See the section about [deployment](https://facebook.github.io/create-react-app/docs/deployment) for more information.

### `npm run eject`

**Note: this is a one-way operation. Once you `eject`, you can't go back!**

If you aren't satisfied with the build tool and configuration choices, you can `eject` at any time. This command will remove the single build dependency from your project.

Instead, it will copy all the configuration files and the transitive dependencies (webpack, Babel, ESLint, etc) right into your project so you have full control over them. All of the commands except `eject` will still work, but they will point to the copied scripts so you can tweak them. At this point you're on your own.

You don't have to ever use `eject`. The curated feature set is suitable for small and middle deployments, and you shouldn't feel obligated to use this feature. However we understand that this tool wouldn't be useful if you couldn't customize it when you are ready for it.
