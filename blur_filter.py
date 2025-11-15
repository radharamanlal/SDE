import pika
import json
import os
import sys
import time
from PIL import Image, ImageFilter

# --- Configuration ---
RABBITMQ_HOST = 'localhost'
IN_QUEUE = 'blur_queue'        
OUT_QUEUE = 'watermark_queue'  
BLUR_FOLDER = './blurred'
BLUR_RADIUS = 5

# Ensure the output folder exists
os.makedirs(BLUR_FOLDER, exist_ok=True)

def blur_image(input_path, output_path, radius):
    """Applies a Gaussian blur to an image."""
    try:
        with Image.open(input_path) as img:
            # Apply the blur filter
            blurred_img = img.filter(ImageFilter.GaussianBlur(radius=radius))
            blurred_img.save(output_path)
            
            print(f" Blurred {input_path} to {output_path}")
            return True
    except Exception as e:
        print(f" Failed to blur {input_path}: {e}")
        return False

def callback(ch, method, properties, body):
    """This function is called every time a message is received."""
    print(f"\n Received message...")
    
    try:
        # 1. Parse the job message (from resize_filter)
        message = json.loads(body)
        image_id = message['image_id']
        
        # 2. Get the path of the *resized* image
        resized_path = message['resized_path'] 

        # 3. Define the new output path
        blurred_path = os.path.join(BLUR_FOLDER, image_id)

        # 4. Perform the work (the filter's logic)
        if blur_image(resized_path, blurred_path, BLUR_RADIUS):
            
            # 5. Create the next job message
            # We copy the original message to preserve keys like 'original_path'
            next_job_message = message.copy()
            
            # --- This is the key to the demo ---
            # We *overwrite* the 'resized_path' key with our new 'blurred_path'.
            # This way, the watermark_filter (which reads 'resized_path')
            # doesn't need to be changed at all.
            next_job_message['resized_path'] = blurred_path 
            
            # 6. Publish to the *next* queue
            ch.queue_declare(queue=OUT_QUEUE, durable=True)
            ch.basic_publish(
                exchange='',
                routing_key=OUT_QUEUE,
                body=json.dumps(next_job_message),
                properties=pika.BasicProperties(delivery_mode=2)
            )
            print(f" Sent job to {OUT_QUEUE} for {image_id}")
            
        else:
            print(f" [Blurring failed for {image_id}.")

        # 7. Acknowledge the message (tells RabbitMQ the job is done)
        ch.basic_ack(delivery_tag=method.delivery_tag)
        print(f"  Acknowledged message from {IN_QUEUE}")

    except Exception as e:
        print(f" Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

def main():
    """Connects to RabbitMQ and starts consuming messages."""
    print(" Blur Filter starting. Waiting for messages...")
    try:
        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )
        channel = connection.channel()

        # Ensure both queues exist
        channel.queue_declare(queue=IN_QUEUE, durable=True)
        channel.queue_declare(queue=OUT_QUEUE, durable=True)

        channel.basic_qos(prefetch_count=1)
        channel.basic_consume(
            queue=IN_QUEUE,
            on_message_callback=callback
        )

        channel.start_consuming()

    except pika.exceptions.AMQPConnectionError:
        print(" Could not connect to RabbitMQ. Retrying in 5 seconds...")
        time.sleep(5)
        main() # Retry connection
    except KeyboardInterrupt:
        print(" Stopping filter.")
        sys.exit(0)

if __name__ == '__main__':
    main()