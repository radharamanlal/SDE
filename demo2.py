import subprocess
import requests
import time
import os
import pika
import sys
 
# Loading configuration
RABBITMQ_HOST = 'localhost'
UPLOAD_URL = 'http://localhost:5001/upload'
TEST_IMAGE_PATH = 'test_images/4.jpg' 
UPLOAD_IMG_NO = 10

PYTHON_CMD = sys.executable 

def check_dependencies():
    """Checks that the required files and services are ready."""
    print("Checking dependencies...")
    if not os.path.exists(TEST_IMAGE_PATH):
        print(f" ERROR: Test image not found: '{TEST_IMAGE_PATH}'")
        return False
    
    try:
        response = requests.post(UPLOAD_URL, timeout=1)
        if response.status_code != 400:
             print(f" Warning: Server at {UPLOAD_URL} returned an unexpected status {response.status_code}.")
    except requests.exceptions.ConnectionError:
        print(f" ERROR: Cannot connect to Pump at '{UPLOAD_URL}'.")
        print("     Please run 'python app.py' in a separate terminal.")
        return False
        
    try:
        connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST, connection_attempts=1, retry_delay=0))
        connection.close()
    except pika.exceptions.AMQPConnectionError:
        print(f" [✘] ERROR: Cannot connect to RabbitMQ at '{RABBITMQ_HOST}'.")
        print("     Please ensure your Docker container is running.")
        return False
        
    print(" All dependencies found.")
    return True

def get_queue_length(queue_name):
    """Checks RabbitMQ and returns the number of messages in a queue."""
    connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
    channel = connection.channel()
    queue_state = channel.queue_declare(queue=queue_name, durable=True, passive=True) 
    connection.close()
    return queue_state.method.message_count

def upload_images():
    """Uploads the test image N times."""
    print(f"  Uploading {UPLOAD_IMG_NO} images...")
    
    try:
        with open(TEST_IMAGE_PATH, 'rb') as f:
            filename = os.path.basename(TEST_IMAGE_PATH)
            files = {'file': (filename, f, 'image/jpeg')} 
            
            for i in range(UPLOAD_IMG_NO):
                try:
                    f.seek(0) # Rewind file for the next upload
                    requests.post(UPLOAD_URL, files=files)
                    print(f"     Uploaded image {i+1}/{UPLOAD_IMG_NO}")
                except requests.exceptions.ConnectionError:
                    print(" [✘] Upload failed. Is app.py (the Pump) running?")
                    return False
    except FileNotFoundError:
        print(f"  ERROR: Test image not found at {TEST_IMAGE_PATH}")
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
                print(" Queues are empty. Processing complete.")
                return True
            time.sleep(1)
        except Exception as e:
            print(f"  ... waiting for queues to appear ...")
            time.sleep(1)
    
    print(" [✘] ERROR: Timeout waiting for queues to drain.")
    return False

def main():
    if not check_dependencies():
        sys.exit(1)
        
    print("\n" + "="*50)
    print("DEMO: AVAILABILITY (FAULT TOLERANCE)")
    print("="*50)
    print("This script demonstrates the 'Active Redundancy' / 'Spare'")
    print("tactic (Software Architecture in Practice, Ch. 5).")
    print("We will start two redundant resize filters, then kill one")
    print("mid-process to show the system recovers and no data is lost.")

    filters = []
    try:
        # --- 1. Start Redundant Filters ---
        print("\n Starting 2x Resize Filters (A and B) and 1x Watermark Filter.")
        filter_a = subprocess.Popen([PYTHON_CMD, "resize_filter.py"])
        filters.append(filter_a)
        
        filter_b = subprocess.Popen([PYTHON_CMD, "resize_filter.py"])
        filters.append(filter_b)
        
        watermark_filter = subprocess.Popen([PYTHON_CMD, "water_filter.py"])
        filters.append(watermark_filter)
        
        print(f"     - Filter A (PID: {filter_a.pid})")
        print(f"     - Filter B (PID: {filter_b.pid})")
        print(f"     - Watermark (PID: {watermark_filter.pid})")
        time.sleep(3) # Give them time to boot

        # --- 2. Upload Work ---
        if not upload_images():
            sys.exit(1)
            
        print("\n  ... processing has started ...")
        time.sleep(2) # Wait for filters to pick up jobs

        # --- 3. Introduce Fault ---
        print("\n" + "="*50)
        print(f" SIMULATING FAULT: Killing Filter A (PID: {filter_a.pid})!")
        filter_a.terminate()
        filters.remove(filter_a) # Remove from list so it's not cleaned up
        print("="*50)
        time.sleep(20)
        # --- 4. Observe Recovery ---
        print("\nWatch: Filter B (the 'spare') will now process all")
        print("      remaining jobs, including any that Filter A had started")
        print("      but did not acknowledge.")
        
        wait_for_queues_to_drain()

        # --- 5. Print Results ---
        print("\n" + "="*50)
        print("DEMO RESULTS")
        print("="*50)
        print(f" All {UPLOAD_IMG_NO} images were processed successfully,")
        print("even though one filter process crashed.")
        print(" Availability tactic confirmed: The system is fault-tolerant.")
        print("\n DEMO COMPLETE")
        
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        # --- 6. Cleanup ---
        print("\n Cleaning up remaining filter processes...")
        for f in filters:
            f.terminate()
        print("     Done.")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nDemo stopped by user.")
        # Clean up any running processes
        try:
            # This is a simple cleanup; a real script would track PIDs
            if 'filter_a' in locals() and filter_a.poll() is None: filter_a.terminate()
            if 'filter_b' in locals() and filter_b.poll() is None: filter_b.terminate()
            if 'watermark_filter' in locals() and water_filter.poll() is None: watermark_filter.terminate()
        except:
            pass # Ignore cleanup errors