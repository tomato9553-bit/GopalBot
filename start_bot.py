import subprocess
import time
import signal
import sys

# Function to start Ollama server
def start_ollama():
    print('Starting Ollama server...')
    process = subprocess.Popen(['ollama', 'start'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return process

# Function to check if Ollama is ready
def wait_for_ollama(process):
    print('Waiting for Ollama to be ready...')
    while True:
        output = process.stdout.readline()  
        if output == b'':
            break
        if b'Ready' in output:
            print('Ollama is ready!')
            break
    return

# Function to start the local API server
def start_local_api():
    print('Starting local API server...')
    api_process = subprocess.Popen(['python', 'api_server.py'], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return api_process

# Function to handle graceful shutdown
def signal_handler(sig, frame):
    print('\nShutting down servers...')
    ollama_process.terminate()
    api_process.terminate()
    sys.exit(0)

if __name__ == '__main__':
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    
    # Start the Ollama server
    ollama_process = start_ollama()
    wait_for_ollama(ollama_process)
    
    # Start the local API server
    api_process = start_local_api()
    print('Both servers are running. Press Ctrl+C to exit.')
    
    # Keep both servers running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        signal_handler(None, None)
