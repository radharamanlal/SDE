import subprocess
import requests
import time
import os
import pika
import sys
 
# Loading configuration
RABBITMQ_HOST = 'localhost'
UPLOAD_URL = 'http://localhost:5001/upload'
TEST_IMAGE_PATH = 'test_images/1.jpg' # <-- Make sure this file exists
UPLOAD_IMG_NO = 5


PYTHON_CMD = sys.executable 

def check_dependencies():
    """Checks that the required files and services are ready."""
    print(" Checking dependencies...")
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f" ERROR: Test image not found: '{TEST_IMAGE_PATH}'")
        print("     Please create this file or update the script.")
        return False
    
    try:
        # A POST to /upload with no file should return 400, proving the server is up.
        response = requests.post(UPLOAD_URL, timeout=1)
        if response.status_code != 400:
             print(f" Warning: Server at {UPLOAD_URL} returned an unexpected status {response.status_code}.")
    except requests.exceptions.ConnectionError:
        print(f"  ERROR: Cannot connect to Pump at '{UPLOAD_URL}'.")
        print("     Please run 'python app.py' in a separate terminal.")
        return False
        
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, connection_attempts=1, retry_delay=0))
        connection.close()
    except pika.exceptions.AMQPConnectionError:
        print(f" [ ERROR: Cannot connect to RabbitMQ at '{RABBITMQ_HOST}'.")
        print("     Please ensure your Docker container is running.")
        return False
        
    print(" All dependencies found.")
    
           
    return True

def get_queue_length(queue_name):
    """Checks RabbitMQ and returns the number of messages in a queue."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    # passive=True checks the queue without modifying it
    queue_state = channel.queue_declare(queue=queue_name, durable=True, passive=True) 
    connection.close()
    return queue_state.method.message_count

def upload_images():
    """Uploads the test image N times."""
    print(f"  Uploading {UPLOAD_IMG_NO} images...")
    
    try:
        with open(TEST_IMAGE_PATH, 'rb') as f:
            filename = os.path.basename(TEST_IMAGE_PATH)
            files = {'file': (filename, f, 'image/jpg')} 
            
            
            for i in range(UPLOAD_IMG_NO):
                try:
                    f.seek(0) # <-- Rewind file for the next upload
                    requests.post(UPLOAD_URL, files=files)
                    print(f"     Uploaded image {i+1}/{UPLOAD_IMG_NO}")
                except requests.exceptions.ConnectionError:
                    print(" Upload failed. Is app.py (the Pump) running?")
                    return False
    except FileNotFoundError:
        print(f" ERROR: Test image not found at {TEST_IMAGE_PATH}")
        return False
    
    print("  Uploads complete.")
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
                print(" Queues are empty. Processing complete.")
                return True
            time.sleep(1)
        except Exception as e:
            print(f"  ... waiting for queues to appear ...")
            time.sleep(1)
    
    print("  ERROR: Timeout waiting for queues to drain.")
    return False

def run_test(num_resize_filters):
    """Runs a complete test with a given number of filters."""
    print(f"\n--- Starting test with {num_resize_filters} Resize Filter(s) ---")
    #Start filters
    filters = []
    for _ in range(num_resize_filters):
        filters.append(subprocess.Popen([PYTHON_CMD, "resize_filter.py"]))
    
    # one watermark filter for this test
    filters.append(subprocess.Popen([PYTHON_CMD, "water_filter.py"]))
    
    print(f" Started {len(filters)} filter processes. Waiting 3s for them to boot...")
    time.sleep(3)

    # Upload images and calculate time taken
    start_time = time.time()
    if not upload_images():
        # Clean up filters if upload failed
        for f in filters:
            f.terminate()
        return -1  # Upload failed
    
    wait_for_queues_to_drain()
    end_time = time.time()
    duration = end_time - start_time
    print(f"  Test completed in {duration:.2f} seconds.")
    
    #stop filter 
    for f in filters:
        f.terminate()

    return duration

def main():
    """This function now contains the full test logic."""
    if not check_dependencies():
        sys.exit(1)
        
    print("\n" + "="*50)
    print(" DEMO: PERFORMANCE (SCALABILITY)")
    print("="*50)
    print("This script demonstrates the 'Concurrency' and 'Increase Resources'")
    print(f"We will measure the total time to process {UPLOAD_IMG_NO} images using")
    print("1 resize filter vs. 3 resize filters.")

    # --- Run Test 1 ---
    time_1_consumer = run_test(num_resize_filters=1)
    if time_1_consumer == -1: sys.exit(1)
    
    time.sleep(2) # Pause between tests
    
    # --- Run Test 2 ---
    time_3_consumers = run_test(num_resize_filters=3)
    if time_3_consumers == -1: sys.exit(1)

    # --- Print Results ---
    print("\n" + "="*50)
    print(" DEMO RESULTS")
    print("="*50)
    print(f"   Time with 1 filter:   {time_1_consumer:.2f} seconds")
    print(f"   Time with 3 filters:  {time_3_consumers:.2f} seconds")
    
    if time_1_consumer > 0 and time_3_consumers > 0:
        speedup = time_1_consumer / time_3_consumers
        print(f"\n  RESULT: Scaling to 3 'Competing Consumers' made the")
        print(f"      pipeline {speedup:.1f}x faster.")
    print("\n  DEMO COMPLETE")



if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDemo stopped by user.")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")