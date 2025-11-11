import pika
import json
import os
import sys
import time
from PIL import Image, ImageDraw, ImageFont

#------configuration------
RABBITMQ_HOST = 'localhost'
IN_QUEUE = 'watermark_queue' #Queue to listen
OUT_QUEUE = 'final_queue' #queue to publish for next filter
WATERMARK_FOLDER='./watermarked_images/'
WATERMARK_TEXT= 'SDE Project'
# ensure folder exists
os.makedirs(WATERMARK_FOLDER, exist_ok=True)
#-------------------------
def add_watermark(in_path,out_path,watermark_text):
    """ Add water mark to image"""
    try:
        with Image.open(in_path).convert("RGBA") as base:
            #Create transparent layer for text
            txt = Image.new('RGBA', base.size, (255,255,255,0))
            #Get a font need to provide a valid font path
            #or use a default font
            try:
                font = ImageFont.truetype("arial.ttf", 36)
            except IOError:
                print("Arial font not found. Using default font.")
                font = ImageFont.load_default()

            #Get a drawing context
            d = ImageDraw.Draw(txt)
            #Calculate text position (bottom right corner)
            bbox = d.textbbox((0, 0), watermark_text, font=font)
            text_width = bbox[2] - bbox[0]
            text_height = bbox[3] - bbox[1]
            pos_x = base.width - text_width - 10
            pos_y = base.height - text_height - 10
            #Draw text with 50% opacity
            d.text((pos_x, pos_y), watermark_text, font=font,fill=(255,255,255,128))
            #Combine base image with text
            watermarked = Image.alpha_composite(base, txt)
            watermarked.convert("RGB").save(out_path)
            print(f"Watermarked {in_path} saved to {out_path}")
            return True
    except Exception as e:
        print(f"Error adding watermark to image {in_path}: {e}")
        return False
    
def callback(ch,method, properties,body):
    """ This function is called every time a message is received from IN_QUEUE """
    print(f"\nReceived message..")
    try:
        # 1. Parse the job message
        message = json.loads(body)
        image_id = message['image_id']
        resized_path = message['resized_path']
        print(f"Processing image_id: {image_id}, resized_path: {resized_path}")
        # 2. Define the new output path
        watermarked_path= os.path.join(WATERMARK_FOLDER,image_id)
        # 3. Perform the work (the filter logic)
        if add_watermark(resized_path,watermarked_path,WATERMARK_TEXT):
            print(f"Watermark added successfully to {image_id}")
        else:
            print(f"Failed to add watermark to {image_id}")
            
        ch.basic_ack(delivery_tag=method.delivery_tag,)
        print(f"Acknowledged message from {IN_QUEUE}")
    except Exception as e:
        print(f"Error processing message: {e}")
        ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)# need to discard bad message
            

def main():
    # Connect to RabbitMQ
    print("Water Filter starting, Waiting for messages...")
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        channel = connection.channel()
    # Ensure the input queue exists
        channel.queue_declare(queue=IN_QUEUE, durable=True)
        print(f"Waiting for messages in {IN_QUEUE}. To exit press CTRL+C")
    # Set up subscription on the queue
        channel.basic_qos(prefetch_count=1)  # Fair dispatch
        channel.basic_consume(queue=IN_QUEUE, on_message_callback=callback)
        channel.start_consuming()
    
    except pika.exceptions.AMQPConnectionError:
        print("Interrupted could not connect to RabbitMQ server. Retrying in 5 seconds...")
        time.sleep(5)
        main()
    except KeyboardInterrupt:
        print("Interrupted by user, stopping filter...")
        sys.exit(0)
        
if __name__ == "__main__":
    main()
