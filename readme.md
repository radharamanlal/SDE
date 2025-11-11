Setting environment
1. intall docker
2. # This will start a RabbitMQ server with a management UI
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management

# created file upload to rabbit mq