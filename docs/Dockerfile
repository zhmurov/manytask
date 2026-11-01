FROM node:24 AS docs_builder

RUN npm i @diplodoc/cli -g

COPY . ./docs
RUN node ./docs/scripts/build-docs.mjs ./html


FROM nginx AS docs
COPY --from=docs_builder /html /usr/share/nginx/html
