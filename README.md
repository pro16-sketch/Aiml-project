# Vehicle Detection System - Web Interface

A beautiful, modern web frontend for the vehicle detection system with Flask backend integration.

## Features

✨ **Modern Web UI**
- Clean, responsive design with dark theme
- Real-time processing status updates
- Beautiful animations and transitions

🎬 **Video Management**
- Select from existing videos in the system
- Upload custom video files (MP4, AVI, MOV, MKV)
- Support for videos up to 2GB
- Drag-and-drop file upload

🚗 **Vehicle Detection**
- YOLOv8n model for accurate detection
- Real-time processing with status tracking
- Audio and visual alerts
- 6 vehicle/object detection classes

📊 **Results & Exports**
- Download processed videos with detections
- CSV logs with detection data
- Live progress monitoring

## Installation

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Make sure you have the existing dependencies from vehicle_detection.py:
```bash
pip install ultralytics opencv-python
```

### 2. Run the Server

```bash
python app.py
```

The server will start on `http://localhost:5000`

### 3. Access the Web Interface

Open your browser and navigate to:
```
http://localhost:5000
```

## Usage

### Selecting a Video

1. **From Local Videos Tab:**
   - The system will automatically show available MP4 files
   - Click on a video to select it
   - Click "Start Processing" to begin analysis

2. **Upload New Video:**
   - Switch to the "Upload Video" tab
   - Drag and drop a video file OR click "Browse Files"
   - Wait for upload to complete
   - The file will be ready for processing

### Processing a Video

1. Select or upload a video
2. Click "Start Processing"
3. Monitor the progress bar and status messages
4. Once complete, download the results

### Results

After processing completes, you can download:
- **Processed Video**: Video with overlaid detections and annotations
- **Detection Log**: CSV file with frame-by-frame detection data

## File Structure

```
.
├── app.py                  # Flask backend server
├── vehicle_detection.py    # Detection engine
├── requirements.txt        # Python dependencies
├── templates/
│   └── index.html         # Main web interface
├── static/
│   ├── style.css          # Beautiful styling
│   └── script.js          # Frontend interactions
├── uploads/               # Uploaded video files
└── outputs/               # Processed results
```

## API Endpoints

- `GET /` - Main web interface
- `GET /api/available-videos` - List available videos
- `POST /api/upload-video` - Upload new video
- `POST /api/process-video` - Start processing
- `GET /api/process-status/<job_id>` - Check processing status
- `GET /api/output-files/<job_id>` - Get generated results
- `GET /api/download/<filename>` - Download result file

## Configuration

Edit `app.py` to customize:
- **PORT**: Change line `app.run(..., port=5000)`
- **MAX_FILE_SIZE**: Change `app.config['MAX_CONTENT_LENGTH']`
- **VIDEO SOURCE**: The system will use the selected video path

## Troubleshooting

**Port already in use?**
```bash
python app.py --port 8000
```

**Processing doesn't start?**
- Check that `vehicle_detection.py` and `yolov8n.pt` are in the same directory
- Verify video file exists and is readable
- Check browser console for JavaScript errors

**Upload fails?**
- Verify file is a valid video format
- Check file size is under 2GB limit
- Ensure `uploads/` folder has write permissions

## Performance Tips

- For best results, use 1080p or lower resolution videos
- Processing time depends on video length and system specs
- GPU acceleration works automatically if CUDA is available

## Requirements

- Python 3.8+
- Flask 2.3+
- OpenCV (cv2)
- PyTorch
- YOLOv8 (ultralytics)
- 2GB+ RAM available
- Disk space for videos and outputs

## License

This project uses YOLOv8 by Ultralytics under AGPL-3.0 license.
