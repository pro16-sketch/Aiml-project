// Global state
let selectedVideo = null;
let currentJobId = null;
let statusCheckInterval = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    setupEventListeners();
    loadAvailableVideos();
    setupCleanupOnLeave();
});

// Cleanup on page leave
function setupCleanupOnLeave() {
    // Clean up temp files when user leaves
    window.addEventListener('beforeunload', () => {
        navigator.sendBeacon('/api/cleanup-session', new Blob());
    });
}

// Setup event listeners
function setupEventListeners() {
    // Tab switching
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.addEventListener('click', switchTab);
    });

    // Upload area
    const uploadArea = document.getElementById('uploadArea');
    const videoInput = document.getElementById('videoInput');

    uploadArea.addEventListener('dragover', handleDragOver);
    uploadArea.addEventListener('dragleave', handleDragLeave);
    uploadArea.addEventListener('drop', handleDrop);
    videoInput.addEventListener('change', handleFileSelect);

    // Process button
    document.getElementById('processBtn').addEventListener('click', startProcessing);

    // Video list item selection using event delegation
    const videoList = document.getElementById('videoList');
    if (videoList) {
        videoList.addEventListener('click', (e) => {
            const item = e.target.closest('.video-item');
            if (item) {
                const path = item.getAttribute('data-path');
                const name = item.getAttribute('data-name');
                selectVideo(path, name);
            }
        });
    }
}

// Tab switching
function switchTab(e) {
    const tabName = e.target.closest('.tab-btn').dataset.tab;
    
    // Update buttons
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    e.target.closest('.tab-btn').classList.add('active');
    
    // Update content
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    document.getElementById(tabName).classList.add('active');
}

// Load available videos
async function loadAvailableVideos() {
    try {
        const response = await fetch('/api/available-videos');
        const videos = await response.json();
        
        const videoList = document.getElementById('videoList');
        
        if (videos.length === 0) {
            videoList.innerHTML = '<div class="loading"><p><i class="fas fa-film"></i> No videos found</p></div>';
            return;
        }
        
        videoList.innerHTML = videos.map(video => `
            <div class="video-item" data-path="${video.path}" data-name="${video.name}">
                <i class="fas fa-film"></i>
                <div class="name">${video.name}</div>
                <div class="size">${formatFileSize(video.size)}</div>
                <div class="source">${video.source}</div>
            </div>
        `).join('');
    } catch (error) {
        console.error('Error loading videos:', error);
        document.getElementById('videoList').innerHTML = '<div class="loading"><p><i class="fas fa-exclamation-circle"></i> Error loading videos</p></div>';
    }
}

// Select video
function selectVideo(path, name) {
    selectedVideo = { path, name };
    
    // Update UI
    document.querySelectorAll('.video-item').forEach(item => item.classList.remove('selected'));
    
    // Find the item robustly without querySelector parsing errors
    const selectedItem = Array.from(document.querySelectorAll('.video-item')).find(
        item => item.getAttribute('data-path') === path
    );
    if (selectedItem) {
        selectedItem.classList.add('selected');
    }
    
    // Update selected video info
    document.getElementById('selectedVideoInfo').innerHTML = `
        <p><i class="fas fa-check-circle"></i> <strong>Selected:</strong> ${name}</p>
        <p style="font-size: 0.9em; margin-top: 5px;"><strong>Path:</strong> ${path}</p>
    `;
    
    // Enable process button
    document.getElementById('processBtn').disabled = false;
}

// Upload area handlers
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('uploadArea').classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('uploadArea').classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('uploadArea').classList.remove('dragover');
    
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        uploadFile(files[0]);
    }
}

function handleFileSelect(e) {
    if (e.target.files.length > 0) {
        uploadFile(e.target.files[0]);
    }
}

// Upload file
async function uploadFile(file) {
    if (!file.name.match(/\.(mp4|avi|mov|mkv)$/i)) {
        alert('Please select a valid video file (MP4, AVI, MOV, MKV)');
        return;
    }
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
        document.getElementById('uploadProgress').style.display = 'block';
        
        const xhr = new XMLHttpRequest();
        
        xhr.upload.addEventListener('progress', (e) => {
            if (e.lengthComputable) {
                const percentComplete = (e.loaded / e.total) * 100;
                document.getElementById('uploadProgressBar').style.width = percentComplete + '%';
                document.getElementById('uploadStatus').textContent = `Uploading: ${Math.round(percentComplete)}%`;
            }
        });
        
        xhr.addEventListener('load', async () => {
            if (xhr.status === 200) {
                const result = JSON.parse(xhr.responseText);
                selectVideo(result.path, result.filename);
                
                document.getElementById('uploadProgress').style.display = 'none';
                document.getElementById('uploadProgressBar').style.width = '0%';
                document.getElementById('videoInput').value = '';
                
                // Refresh video list
                await loadAvailableVideos();
                
                alert('Video uploaded successfully!');
            } else {
                alert('Upload failed!');
            }
        });
        
        xhr.open('POST', '/api/upload-video');
        xhr.send(formData);
    } catch (error) {
        console.error('Upload error:', error);
        alert('Upload error: ' + error);
    }
}

// Start processing
async function startProcessing() {
    if (!selectedVideo) {
        alert('Please select a video first');
        return;
    }
    
    try {
        document.getElementById('processBtn').disabled = true;
        
        const response = await fetch('/api/process-video', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                video_path: selectedVideo.path
            })
        });
        
        const result = await response.json();
        
        if (result.error) {
            alert('Error: ' + result.error);
            document.getElementById('processBtn').disabled = false;
            return;
        }
        
        currentJobId = result.job_id;
        
        // Show processing status
        document.getElementById('processingStatus').style.display = 'block';
        document.getElementById('resultsSection').style.display = 'none';
        
        // Start polling for status
        statusCheckInterval = setInterval(checkProcessingStatus, 1000);
        
    } catch (error) {
        console.error('Error starting process:', error);
        alert('Error: ' + error);
        document.getElementById('processBtn').disabled = false;
    }
}

// Check processing status
async function checkProcessingStatus() {
    if (!currentJobId) return;
    
    try {
        const response = await fetch(`/api/process-status/${currentJobId}`);
        const status = await response.json();
        
        if (response.ok) {
            document.getElementById('statusValue').textContent = status.status.toUpperCase();
            // Format the message, replacing newlines with <br>
            const messageHtml = status.message.replace(/\n/g, '<br>');
            document.getElementById('statusMessage').innerHTML = messageHtml;
            document.getElementById('processingProgressBar').style.width = status.progress + '%';
            document.getElementById('progressText').textContent = status.progress + '%';
            
            if (status.status === 'completed') {
                clearInterval(statusCheckInterval);
                showResults();
                document.getElementById('processBtn').disabled = false;
            } else if (status.status === 'error') {
                clearInterval(statusCheckInterval);
                alert('Processing error: ' + status.message);
                document.getElementById('processBtn').disabled = false;
            }
        }
    } catch (error) {
        console.error('Error checking status:', error);
    }
}

// Show results
async function showResults() {
    try {
        const response = await fetch(`/api/output-files/${currentJobId}`);
        const outputs = await response.json();
        
        if (outputs.length === 0) {
            document.getElementById('resultsList').innerHTML = '<p>No output files generated</p>';
        } else {
            document.getElementById('resultsList').innerHTML = outputs.map(file => {
                const icon = file.type === 'video' ? 'fa-video' : 'fa-file-csv';
                return `
                    <div class="result-item">
                        <i class="fas ${icon}"></i>
                        <div class="result-name">${file.name}</div>
                        <div class="result-type">${file.type.toUpperCase()}</div>
                        <a href="${file.path}" class="btn btn-primary btn-secondary">
                            <i class="fas fa-download"></i> Download
                        </a>
                    </div>
                `;
            }).join('');
        }
        
        document.getElementById('processingStatus').style.display = 'none';
        document.getElementById('resultsSection').style.display = 'block';
        
        // Scroll to results
        document.getElementById('resultsSection').scrollIntoView({ behavior: 'smooth' });
        
    } catch (error) {
        console.error('Error loading results:', error);
    }
}

// Utility: Format file size
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}
