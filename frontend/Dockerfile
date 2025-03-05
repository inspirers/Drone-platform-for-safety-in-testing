FROM nginx:latest
ENV BACKEND_URL="ws://localhost:8000"
COPY webapp.html /webapp.html
RUN envsubst < /webapp.html > /usr/share/nginx/html/index.html
