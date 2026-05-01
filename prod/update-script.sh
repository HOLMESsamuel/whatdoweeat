#!/bin/bash

# Print the current date and time
echo "Script executed on: $(date)"

# Se déplacer dans le dossier du docker-compose
cd ~/whatdoweeat

# Arrêter les services docker-compose
sudo docker compose down

# Pull des images Docker
sudo docker pull samuelholmes/whatdoweeat-frontend:latest
sudo docker pull samuelholmes/whatdoweeat-backend:latest

# Nettoyer le système Docker
sudo docker system prune -f

# Relancer les services docker-compose
sudo docker compose up -d