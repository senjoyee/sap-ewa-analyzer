FROM node:20-alpine as build

WORKDIR /app

# Copy dependency files first for caching
COPY package*.json ./

RUN npm install

# Copy the rest of the frontend code
COPY . .

RUN npm run build

# Serve static build with 'serve'
FROM node:20-alpine as prod
WORKDIR /app
RUN npm install -g serve
COPY --from=build /app/build ./build
EXPOSE 80
CMD ["serve", "-s", "build", "-l", "80"]