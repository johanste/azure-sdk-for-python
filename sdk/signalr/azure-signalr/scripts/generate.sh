#!/usr/bin/env bash

npm install autorest
node_modules/.bin/autorest --use=@autorest/python@5.0.0-preview.3 --input-file=./ws.swagger.json --output-folder=../azure/signalr/
mv ../azure/signalr/azure_web_socket_service_restapi ../azure/signalr/_generated
