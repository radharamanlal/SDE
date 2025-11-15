import os
import uuid
from flask import Flask, request, jsonify, send_from_directory
import pika
import json

#----- COnfiguration -----#
app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'
RABBITMQ_HOST = 'localhost'
UPLOAD_QUEUE = 'upload_queue'

# Ensure upload directory exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

#------The API Endpoints -----#
@app.route('/upload', methods=['POST'])
def upload_file():
    """ Accepts an image uploade and sends a job message to Rabbit MQ  """
    if 'file' not in request.files:
        return jsonify({'error': 'No file found'}),400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}),400
    
    file =request.files['file']
    if file:
        #generate unique id to save file
        ext=file.filename.split('.')[-1]
        unique_filename=f"{str(uuid.uuid4())}.{ext}"
        file_path=os.path.join(app.config['UPLOAD_FOLDER'],unique_filename)
        file.save(file_path)    

        #generate the job message
        job_message={
            'image_id':unique_filename,
            'original_path':file_path
        }
        try:
            #connect to rabbit mq and publish the  message
            connection=pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST)    
                                               )
            channel=connection.channel()
            channel.queue_declare(queue=UPLOAD_QUEUE,durable=True)
            channel.basic_publish(
                exchange='',
                routing_key=UPLOAD_QUEUE,
                body=json.dumps(job_message),
                properties=pika.BasicProperties(
                    delivery_mode=2,  # make message persistent
                ))
            connection.close()

            print(f" [x] Sent {job_message}")
            return jsonify({'message': 'File uploaded successfully', 'job': job_message}), 200
        except pika.exceptions.AMQPConnectionError:
            
            return jsonify({'error': 'Failed to connect to RabbitMQ'}), 503
        except Exception as e:
            return jsonify({'error': f"An unexpected error occured:{str(e)}"}), 503
        

#-----Run the Flask App -----#
if __name__ == '__main__':  
    app.run(debug=True, port=5001, host='0.0.0.0', use_reloader=False)