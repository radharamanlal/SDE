import subprocess
import requests
import time
import os
import pika
import sys
 
# Loading configuration
RABBITMQ_HOST = 'localhost'
UPLOAD_URL = 'http://localhost:5000/upload'
TEST_IMAGE_PATH = 'test_images/nature.avif'
UPLOAD_IMG_NO = 5

PYTHON_CMD = sys.executable 

def check_dependencies():
    """Checks that the required files and services are ready."""
    print("Checking dependencies...")
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f" ERROR: Test image not found: '{TEST_IMAGE_PATH}'")
        print("     Please create this file or update the script.")
        return False
    
    try:
        requests.get("http://127.0.0.1:5000/", timeout=1)
    except requests.exceptions.ConnectionError:
        print(f" ERROR: Cannot connect to Pump at '{UPLOAD_URL}'.")
        print(" Please run 'python app.py' in a separate terminal.")
        return False
        
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, connection_attempts=1, retry_delay=0))
        connection.close()
    except pika.exceptions.AMQPConnectionError:
        print(f" ERROR: Cannot connect to RabbitMQ at '{RABBITMQ_HOST}'.")
        print(" Please ensure your Docker container is running.")
        return False
        
    print(" Everthing Okay.")
    return True

def get_queue_length(queue_name):
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    queue_state = channel.queue_declare(queue=queue_name, durable=True, passive=True)
    connection.close()
    return queue_state.method.message_count

def upload_images():
    """Uploads the test image N times."""
    print(f"Uploading {UPLOAD_IMG_NO} images...")
    files = {'file': ('Test_Image_Path', open(TEST_IMAGE_PATH, 'rb'), 'image/png')}
    for i in range(TEST_IMAGE_PATH):
        try:
            requests.post(UPLOAD_URL, files=files.copy())
            print(f"Uploaded image {i+1}/{UPLOAD_IMG_NO}")
        except requests.exceptions.ConnectionError:
            print("Upload failed. Is app.py (the Pump) running?")
            return False
    print(" Uploads complete.")
    return True

def wait_for_queues_to_drain(timeout_sec=60):
    """Waits until both processing queues are empty."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            uploads = get_queue_length('upload_queue')
            watermarks = get_queue_length('watermark_queue')
            print(f"  ... processing ... (Uploads: {uploads}, Watermarks: {watermarks})")
            if uploads == 0 and watermarks == 0:
                print(" [🏁] Queues are empty. Processing complete.")
                return True
            time.sleep(1)
        except Exception as e:
            print(f"  ... waiting for queues to appear ...")
            time.sleep(1)
    
    print(" [✘] ERROR: Timeout waiting for queues to drain.")
    return False

def run_test(num_resize_filters):
    print(f"\n--- Starting test with {num_resize_filters} Resize Filter(s) ---")
    #Start filters
    filters = []
    for _ in range(num_resize_filters):
        filters.append(subprocess.Popen([PYTHON_CMD, "resize_filter.py"]))
    
    # one watermark filter for this test
    filters.append(subprocess.Popen([PYTHON_CMD, "watermark_filter.py"]))
    
    print(f"Started {len(filters)} filter processes. Waiting 3s for them to boot...")
    time.sleep(3)

    # Upload images and calculate time taken
    start_time = time.time()
    if not upload_images():
        return -1  # Upload failed
    
    wait_for_queues_to_drain()
    end_time = time.time()
    duration = end_time - start_time
    print(f"Test completed in {duration:.2f} seconds.")
#stop filter 
    for f in filters:
        f.terminate()

    return duration

def main():
    if not check_dependencies():
        sys.exit(1)
        
    print("\n" + "="*50)
    print("DEMO: PERFORMANCE (SCALABILITY)")
    print("="*50)
    print("This script demonstrates the 'Concurrency' and 'Increase Resources'")
    print("We will measure the total time to process 5 images using")
    print("1 resize filter vs. 3 resize filters.")

    if __name__ == "__main__":
        main