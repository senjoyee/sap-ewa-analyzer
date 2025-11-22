# SAPUI5 Frontend – Azure Web App Deployment Guide

This guide explains how to package the SAPUI5 frontend as a Docker image, push it to Azure Container Registry (ACR) via GitHub Actions (matching the existing backend/frontend automation), and prepare it for hosting on an Azure Web App for Containers.

> **Scope**: Documentation only—follow these steps to add automation/configuration later. Commands assume the repo root is `ewa_analyzer/`.

---

## 1. Prerequisites

1. **Azure Container Registry** – reuse `sapservicesuk-g8b0edb8fthrbpgj.azurecr.io` (see `.github/workflows/push-to-acr.yml`).
2. **GitHub Secrets** – already configured for the current workflow:
   - `REGISTRY_USERNAME`
   - `REGISTRY_PASSWORD`
3. **Node.js LTS** + **UI5 CLI** (for local builds/tests).
4. **Docker CLI** with access to the registry if you plan to run local smoke tests.

---

## 2. Build Output

1. From the repo root run:
   ```bash
   cd sapui5
   npm install
   npx ui5 build --dest dist
   ```
2. Confirm the optimized build exists under `sapui5/dist/`; this folder is what the container will serve.

---

## 3. Create a Dockerfile (`sapui5/Dockerfile`)

1. Use a multi-stage build so the final image only contains the compiled assets:
   ```dockerfile
   # Stage 1 – build UI5 app
   FROM node:18-alpine AS builder
   WORKDIR /app
   COPY package*.json ./
   RUN npm ci
   COPY . .
   RUN npx ui5 build --dest dist

   # Stage 2 – serve via nginx
   FROM nginx:alpine
   COPY --from=builder /app/dist/ /usr/share/nginx/html/
   COPY nginx.conf /etc/nginx/conf.d/default.conf
   EXPOSE 8080
   CMD ["nginx", "-g", "daemon off;"]
   ```
2. Reuse the existing frontend `nginx.conf` (or create a minimal one) to define caching headers and listen on port 8080.

---

## 4. Local Smoke Test (optional)

```bash
docker build -t ewa-sapui5:local ./sapui5
docker run --rm -p 8080:8080 ewa-sapui5:local
```

Visit `http://localhost:8080/index.html` and verify the UI5 app loads.

---

## 5. Extend GitHub Actions Workflow

1. Edit `.github/workflows/push-to-acr.yml` and append a third `docker/build-push-action` step after the existing backend/frontend builds:
   ```yaml
      - name: Build and push SAPUI5 frontend with cache
        uses: docker/build-push-action@v5
        with:
          context: ./sapui5
          push: true
          tags: ${{ env.REGISTRY }}/ewa-sapui5:latest
          cache-from: type=registry,ref=${{ env.REGISTRY }}/ewa-sapui5:buildcache
          cache-to: type=registry,ref=${{ env.REGISTRY }}/ewa-sapui5:buildcache,mode=max
   ```
2. The existing `REGISTRY`, `REGISTRY_USERNAME`, and `REGISTRY_PASSWORD` env values automatically cover this new step.
3. GitHub Actions will now push `ewa-sapui5:latest` to ACR on the same triggers (`main`, `heidegger`, `fiori-migration`).

---

## 6. Deploy Azure Web App for Containers

1. In Azure Portal create a new Web App (Linux) and choose **Docker Container** deployment.
2. Set the image source to **Azure Container Registry** → `sapservicesuk-g8b0edb8fthrbpgj.azurecr.io/ewa-sapui5:latest`.
3. Configure the container settings to expose port `8080` (matches the nginx config).
4. Save and restart the Web App; it will pull the latest container automatically after each push.

---

## 7. Verification Checklist

1. Confirm the GitHub workflow run shows three successful image pushes.
2. In ACR, verify the `ewa-sapui5` repository exists with the `latest` tag.
3. Browse the new Web App URL and ensure it uses the backend URL set in `webapp/model/config.js`.
4. Roll back by redeploying a previous tag if required (ACR retains tag history).

---

## 8. Future Enhancements (optional)

- Parameterize image tags (e.g., `ewa-sapui5:${{ github.sha }}`) for immutable releases.
- Add a post-publish smoke test (GitHub job hitting `/health`).
- Automate Web App provisioning via IaC (Bicep/Terraform) for consistent environments.
