# Asynchronous Image Processing Pipeline

This project is a demonstration of the **Pipe-and-Filter** architectural pattern for the CSL7090: Software & Data Engineering course.

It implements a scalable, asynchronous pipeline in Python to process image uploads. Instead of a single, monolithic application, the system is broken down into decoupled services that communicate using a RabbitMQ message broker.

##  Architectural Overview

The system follows a classic **Pipe-and-Filter** design. The "pipes" are not in-memory function calls but **asynchronous message queues** (RabbitMQ), which makes the system resilient, scalable, and modifiable.

The data flows as follows:

1.  **Pump (`app.py`):** A Flask web server accepts an image upload from a user via a `POST` request. It saves the original image and publishes a JSON job message to the `upload_queue`.
2.  **Pipe 1 (`upload_queue`):** A durable RabbitMQ queue that holds jobs for the first processing stage.
3.  **Filter 1 (`resize_filter.py`):** A standalone Python consumer script. It listens to the `upload_queue`, receives a job, resizes the image using Pillow, and publishes a *new* job message to the `watermark_queue`.
4.  **Pipe 2 (`watermark_queue`):** A durable queue that holds jobs for the watermarking stage.
5.  **Filter 2 / Sink (`watermark_filter.py`):** A second consumer script. It listens to the `watermark_queue`, adds a text watermark to the resized image, and saves the final result to the `watermarked/` directory.

### PIPE & FILTER ARCHITECTURE DIAGRAM (Flow Diagram)

<img width="964" height="362" alt="image" src="https://github.com/user-attachments/assets/384bc59c-bd1e-42d9-935a-3650293b2c3e" />

### Sequence Diagram

<img width="1043" height="738" alt="image" src="https://github.com/user-attachments/assets/4e3011e2-17b2-4a28-8118-4ca85e4b6301" />



##  Architectural Concepts

This project is a  application for implementing key software architecture principles for SDE assignment and our course slides:

* **Pipe-and-Filter Pattern:** The main architecture. Each processing step is a filter, and queues act as pipes.
* **Decoupling & Modifiability:** Filters are completely independent.We can add a new `convert_grayscale` or between the resize and watermark steps without modifying *any* existing code—we just plugin  the queue outputs. Or preprocessing of image for classification training or for predicting form trained model. We can send it to other pipelines.
* **Scalability:** The `resize_filter.py` is slow? We can run multiple instances of it. RabbitMQ will automatically load-balance jobs across all running consumers .This allows us to scale only the bottleneck, which one of the essential attribute of good architecture. 
* **Reliability & Fault Tolerance:**
    * **Persistence:** By declaring queues as `durable=True` and marking messages as persistent, jobs are not lost even if the RabbitMQ broker restarts.
    * **Acknowledgments:** A job is removed from the queue only after a filter successfully processes it and sends an `basic_ack`. If a filter crashes mid-process, the message is automatically re-queued and processed by another instance.
* **Asynchronous Processing:** The user's upload request returns in milliseconds with a `OK`, even if the processing takes few seconds. This provides a responsive user experience.

##  Technology Stack

* **Python 3**
* **Flask**: To create the API Pump (`app.py`).
* **Pika**: The standard Python client for RabbitMQ.
* **Pillow (PIL)**: For all image processing (resize, watermark).
* **RabbitMQ**: The message broker (the "Pipes").
* **Docker**: Used to easily run the RabbitMQ broker.

##  Setup & Installation

### 1. Clone the Repository

```bash
git clone [https://github.com/YourUsername/YourRepoName.git](https://github.com/YourUsername/YourRepoName.git)
cd YourRepoName
```

### 2. Create `requirements.txt`

(If you haven't already, create this file)
```txt
# requirements.txt
Flask
pika
Pillow
```

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Docker
Install [Docker Desktop](https://www.docker.com/products/docker-desktop/) for your OS.

### 5. Start the RabbitMQ Broker

Run this command in your terminal to start RabbitMQ in a Docker container.

```bash
docker run -d --name rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management
```
* `5672` is the port for the Python apps.
* `15672` is for the web management UI (open `http://localhost:15672` in your browser. Login: `guest`/`guest`).

##  How to Run the Pipeline

You must have **three separate terminals** open, one for each component.

### Terminal 1: Run the API Pump

```bash
python app.py
```
*Output: `* Running on http://127.0.0.1:5000`*

### Terminal 2: Run the Resize Filter

```bash
python resize_filter.py
```
*Output: `Waiting for messages in upload_queue...`*

### Terminal 3: Run the Watermark Filter

```bash
python watermark_filter.py
```
*Output: `[*] Watermark Filter starting. Waiting for messages...`*

All three services are now running and waiting.

##  How to Test

Open a **fourth terminal** to send an image. Make sure you have a test image (e.g., `test.png`) in your project directory.

```bash
curl -X POST -F "file=@test.png" [http://127.0.0.1:5000/upload](http://127.0.0.1:5000/upload)
```

### Expected Result

1.  The `curl` command will immediately return a JSON response:
    ```json
    {
      "message": "File uploaded successfully",
      "job": { ... }
    }
    ```
2.  Watch your other terminals! You will see the log messages as the job is passed from `app.py` -> `resize_filter.py` -> `watermark_filter.py`.
3.  Check your local folders:
    * `./uploads/` will have the original `test.png`.
    * `./resized_images/` will have the resized version.
    * `./watermarked/` will have the final, watermarked version.

## Demonstrating the Quality Attributes

This project includes scripts to automatically demonstrate the architectural benefits.

Before running any demo, make sure app.py (the Pump) is running in its own terminal!

### 1. Demo: Performance (Scalability)

This script proves the system gets faster as you add resources.

python demo1.py

<img width="1017" height="467" alt="image" src="https://github.com/user-attachments/assets/1e5bd566-f31a-4d65-8fa0-ae511faab66e" />

The script will run a test with 1 filter, then a test with 3 filters, and print a report showing the speed-up.

|TABLE: MAJOR COMPONENTS|
|Component	|Description|
|Pump (Flask API)|	Receives uploads and enqueues jobs|
|Filter 1 – Resize|	Resizes images to standardized dimensions|
|Filter 2 – Watermark|	Adds a watermark and finalizes output|
|Pipes (RabbitMQ queues)|	Durable message transport|
|Sink (File storage)|	Stores final processed output|


### 2. Demo: Availability (Fault Tolerance)

This script proves the system is resilient to failure. It will start two filters, give them work, and then kill one to show the "spare" takes over.

python demo2.py


### 3. Demo: Modifiability (Walkthrough)

This script is for blurring image which will be replace with any one filter (either image_resized.py, or water_mark.py) 
just replace any of the filter only name of filter to be changed no code chnage is required.

python blur_filter.py



##  Future Improvements

This project demonstrates the concept of pipe and filter, but a production-ready system would require significant effort in following aspects:
* **Dead-Letter Queues (DLQs):** If a file is corrupt and a filter fails miltiple times (lets say 3 times, the message should be moved to a `_error_queue` for inspection instead of blocking the pipeline.
* **Centralized Logging:** Logging from all three services should be club togehter into one logger.
* **Shared Storage:** The local folders (`uploads/`, etc.) won't work if you scale. These should be replaced with a shared volume or cloud storage (like Amazon S3).
* **Configuration Management:** Hard-coded values (`localhost`, queue names) should be moved to environment variables.
````
