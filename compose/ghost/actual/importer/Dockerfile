FROM node:22-alpine

RUN npm install -g @actual-app/cli@26.10.0

WORKDIR /app
COPY importer.js .
COPY accounts.json /etc/actual-import/accounts.json

# /cache is a named volume at runtime — pre-chown so it inherits node perms
RUN mkdir -p /cache && chown node:node /cache
USER node

CMD ["node", "/app/importer.js"]
