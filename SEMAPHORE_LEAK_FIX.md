# Semaphore Leak Warning - Causes and Solutions

## Warning Message

```
/opt/homebrew/Cellar/python@3.11/3.11.14/Frameworks/Python.framework/Versions/3.11/lib/python3.11/multiprocessing/resource_tracker.py:254: UserWarning: resource_tracker: There appear to be 2 leaked semaphore objects to clean up at shutdown
```

## Root Causes

### 1. **Gunicorn Multi-Worker Configuration**

- Your `Procfile` uses `--workers 2`, creating 2 worker processes
- Each worker process uses multiprocessing internally
- When workers shut down, semaphores created by multiprocessing may not be properly cleaned up

### 2. **Heavy ML/AI Dependencies**

Your application uses several resource-intensive libraries that internally use multiprocessing:

- **MinerU** (`mineru==2.5.4`) - Uses PyTorch and computer vision models
- **PyTorch** (`torch>=2.0.0`) - Creates multiprocessing resources for model loading
- **Transformers** (`transformers>=4.30.0`) - Uses multiprocessing for tokenization
- **Ultralytics** (`ultralytics>=8.0.0`) - YOLO models use multiprocessing
- **OpenCV** (`opencv-python>=4.11.0.86`) - May create semaphores for image processing

### 3. **Google Cloud Document AI Client**

- The `google-cloud-documentai` library creates internal connections
- May use multiprocessing resources that aren't properly cleaned up

### 4. **Temporary File Handling**

- Application creates temporary files and directories
- Cleanup process might not be releasing all multiprocessing resources

## Solutions Implemented

### ✅ **Solution 1: Proper Resource Cleanup**

Added cleanup handlers to `app.py`:

- Signal handlers for graceful shutdown
- `atexit` handlers for cleanup on exit
- Proper cleanup of MinerU/PyTorch resources

### ✅ **Solution 2: MinerU Resource Cleanup**

Added `cleanup()` method to `MinerUExtractor`:

- Clears PyTorch CUDA cache
- Synchronizes CUDA operations
- Properly releases GPU memory

### ✅ **Solution 3: Configurable Worker Count**

- Added `WORKERS` environment variable (defaults to 1)
- Updated `Procfile` to use `${WORKERS:-1}`
- Created `Procfile.dev` for development with single worker

### ✅ **Solution 4: Environment Configuration**

- Added `WORKERS=1` to `env.example`
- Updated `Config` class to include worker count setting

## How to Use

### For Development (Recommended)

```bash
# Use single worker to prevent semaphore leaks
export WORKERS=1
python app.py
```

### For Production

```bash
# Use multiple workers only if needed
export WORKERS=2
gunicorn --bind 0.0.0.0:$PORT --workers $WORKERS --timeout 300 app:app
```

### Alternative: Use Development Procfile

```bash
# Use the development Procfile
gunicorn --bind 0.0.0.0:$PORT --workers 1 --timeout 300 --preload app:app
```

## Additional Recommendations

### 1. **Monitor Resource Usage**

- Watch for memory leaks during development
- Use tools like `htop` or `ps` to monitor process behavior

### 2. **Update Dependencies**

- Keep PyTorch, MinerU, and other ML libraries updated
- Some semaphore leak issues are fixed in newer versions

### 3. **Consider Alternative Architectures**

- For production, consider using a task queue (Celery) instead of multiprocessing
- Use Redis or RabbitMQ for background processing

### 4. **Platform-Specific Considerations**

- This warning is more common on macOS
- Consider testing on Linux for production deployment

## Testing the Fix

1. **Start the server with single worker:**

   ```bash
   export WORKERS=1
   python app.py
   ```

2. **Process a PDF file through the API**

3. **Stop the server gracefully** (Ctrl+C)

4. **Check if the semaphore warning still appears**

The warning should be significantly reduced or eliminated with these changes.
