FROM node:20-alpine as build

WORKDIR /app

# Copy dependency files first for caching
COPY package*.json ./

RUN npm install

# Accept API base as a build argument and expose as env for the build step
ARG REACT_APP_API_BASE="https://sap-ewa-analyzer-backend.azurewebsites.net/"
ENV REACT_APP_API_BASE=${REACT_APP_API_BASE}

# Copy the rest of the frontend code
COPY . .

RUN npm run build

# Serve static build with Nginx (adds CSP for Teams via nginx.conf)
FROM nginx:alpine as prod

# Copy React build output to default nginx web root
COPY --from=build /app/build /usr/share/nginx/html

# Provide custom nginx configuration (CSP + SPA fallback)
COPY nginx.conf /etc/nginx/nginx.conf

EXPOSE 80