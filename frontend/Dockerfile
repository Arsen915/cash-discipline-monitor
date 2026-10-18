FROM node:20.18-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY . .
# Необязательный ключ, подставляемый в UI по умолчанию (виден в JS-бандле — только для демо)
ARG VITE_DEFAULT_API_KEY=""
ENV VITE_DEFAULT_API_KEY=$VITE_DEFAULT_API_KEY
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
