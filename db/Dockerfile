# Use the official MongoDB image from the Docker Hub
FROM mongo:latest

# Create a directory inside the container to hold your db files
RUN mkdir -p /data/db

# Copy the db folder from your host to the container
COPY . /data/db

# Expose the MongoDB port
EXPOSE 27017

# Start the MongoDB server
CMD ["mongod", "--dbpath", "/data/db", "--bind_ip_all"]