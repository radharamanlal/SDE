import pika
import json
import os
import sys
from PIL import Image
import time

#------configuration------
RABBITMQ_HOST = 'localhost'
IN_QUEUE = 'upload_queue' #Queue to listin
OUT_QUEUE = 'watermark_queue' #watermark_queue' #queue to publish for next filter
RESIZE_FOLDER='./resized_images/'
RESIZE_WIDTH= 640
# ensure folder exists
os.makedirs(RESIZE_FOLDER, exist_ok=True)
#-------------------------
def resize_image(in_path,out_path,new_width):
    """ Resize image to new width"""
    try:
        with Image.open(in_path) as img:
            #Calculate new height to maintain asprect ratio
            w_percent = (new_width / float(img.size[0]))
            new_height = int((float(img.size[1]) * float(w_percent)))
            #Resize and save image
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img.save(out_path)
            print(f"Resized {in_path} saved to {out_path}")
            return True
    except Exception as e:
        print(f"Error resizing image {in_path}: {e}")
        return False
    
def callback(ch,method, properties,body):
    """ This function is called everytim a message is received from IN_QUEUE """
    print(f"\nReceived message..")
    try:
        # 1. Parse the job message
        message = json.loads(body)
        image_id = message['image_id']
        image_path = message['original_path']
        print(f"Processing image_id: {image_id}, image_path: {image_path}")
        # 2. Define the new output path
        resized_path= os.path.join(RESIZE_FOLDER,image_id)
        # 3. Perform the work (the filter logic)
        if resize_image(image_path,resized_path,RESIZE_WIDTH):
            # 4 create bext job message      
            new_message={
                'image_id':image_id,
                'original_path':image_path,
                'resized_path':resized_path
            }
            # Publish to the next queue (for watermarking fillter)
            ch.queue_declare(queue=OUT_QUEUE, durable=True)
            ch.basic_publish(
                exchange='',
                routing_key=OUT_QUEUE,
                body=json.dumps(new_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ))
            print(f"Published resized image job to {OUT_QUEUE} for {image_id}")
        else:
            print(f"Failed to resize image {image_id}")

        #6. Acknowledge message
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"Message acknowledged from: {IN_QUEUE}")
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)# need to discard bad message

def main():
    """ Main function to setup RabbitMQ connection and start consuming messages """
    try:
        #1. Connect to RabbitMQ
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
        #2. Declare the input queue
        channel.queue_declare(queue=IN_QUEUE, durable=True)# ensure input queue exists
        print(f"Waiting for messages in {IN_QUEUE}. To exit press CTRL+C")
        channel.queue_declare(queue=OUT_QUEUE, durable=True)# ensure output queue exists
        #3. Set up consumer and qulaity of service
        channel.basic_qos(prefetch_count=1) # Fair dispatch
        # 
        channel.basic_consume(queue=IN_QUEUE, on_message_callback=callback)
        #4. Start consuming
        channel.start_consuming()
    except pika.exceptions.AMQPConnectionError :
        print("Error: Unable to connect to RabbitMQ server. Is it running? Retrying in 5 seconds...")
        time.sleep(5)
        main()  # Retry connection
    except KeyboardInterrupt:
        print("Interrupted by user, shutting down,stopping filter...")
        sys.exit(0)
        
if __name__ == "__main__":
    main()