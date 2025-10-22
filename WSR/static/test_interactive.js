// Upscaler - AI-powered logo enhancement tool
// Upscales logos and provides background editing capabilities

class TestInteractiveEditor {
    constructor() {
        this.canvas = null;
        this.ctx = null;
        this.originalImageData = null;
        this.currentImageData = null;
        this.isDrawing = false;
        this.currentTool = 'flood';
        this.tolerance = 15;
        this.brushSize = 20;
        this.undoStack = [];
        this.maxUndoSteps = 10;

        // API Configuration
        this.API_BASE_URL = this.getApiBaseUrl();

        this.init();
    }

    getApiBaseUrl() {
        // Check if running locally or on AWS
        const hostname = window.location.hostname;

        if (hostname === 'localhost' || hostname === '127.0.0.1') {
            // Local development
            return '';
        } else {
            // Production - Replace with your actual API Gateway URL
            const API_GATEWAY_URL = 'https://YOUR-API-ID.execute-api.us-east-1.amazonaws.com/prod';
            return API_GATEWAY_URL;
        }
    }

    init() {
        // Get DOM elements
        this.canvas = document.getElementById('imageCanvas');
        this.ctx = this.canvas.getContext('2d');

        // Set up event listeners
        this.setupEventListeners();

        console.log('Upscaler tool initialized');
    }

    setupEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');

        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop
        uploadArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadArea.classList.add('drag-over');
        });

        uploadArea.addEventListener('dragleave', () => {
            uploadArea.classList.remove('drag-over');
        });

        uploadArea.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadArea.classList.remove('drag-over');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.loadImage(files[0]);
            }
        });

        // Tool controls
        document.getElementById('toolMode').addEventListener('change', (e) => {
            this.currentTool = e.target.value;
            this.updateToolUI();
        });

        document.getElementById('toleranceSlider').addEventListener('input', (e) => {
            this.tolerance = parseInt(e.target.value);
            document.getElementById('toleranceValue').textContent = this.tolerance;
        });

        document.getElementById('brushSize').addEventListener('input', (e) => {
            this.brushSize = parseInt(e.target.value);
            document.getElementById('brushSizeValue').textContent = this.brushSize;
        });


        // Action buttons
        document.getElementById('undoBtn').addEventListener('click', () => this.undo());
        document.getElementById('resetBtn').addEventListener('click', () => this.reset());
        document.getElementById('clearAllBtn').addEventListener('click', () => this.clearAll());
        document.getElementById('upscaleBtn').addEventListener('click', () => this.upscale());

        // Canvas interaction
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('click', (e) => this.handleClick(e));

        // Download buttons
        document.getElementById('downloadPngBtn').addEventListener('click', () => this.downloadPNG());
        document.getElementById('downloadUpscaledBtn').addEventListener('click', () => this.downloadUpscaled());
        document.getElementById('downloadBtn').addEventListener('click', () => this.downloadCurrentImage());
    }

    updateToolUI() {
        const brushGroup = document.getElementById('brushGroup');
        if (this.currentTool === 'brush') {
            brushGroup.style.display = 'block';
        } else {
            brushGroup.style.display = 'none';
        }
    }

    handleFileSelect(e) {
        const file = e.target.files[0];
        if (file) {
            this.loadImage(file);
        }
    }

    loadImage(file) {
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                this.setupCanvas(img);
                this.showEditor();
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }

    setupCanvas(img) {
        // Set canvas size to match image
        this.canvas.width = img.width;
        this.canvas.height = img.height;

        // Clear canvas and draw image
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(img, 0, 0);

        // Store original image data
        this.originalImageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        this.currentImageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);

        // Clear undo stack
        this.undoStack = [];
        this.updateUndoButton();

        // Enable upscale button
        document.getElementById('upscaleBtn').disabled = false;
    }

    showEditor() {
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('editorSection').style.display = 'block';
        document.getElementById('canvasOverlay').style.display = 'none';
        document.getElementById('downloadSection').style.display = 'block';
    }

    saveState() {
        // Save current state to undo stack
        if (this.undoStack.length >= this.maxUndoSteps) {
            this.undoStack.shift(); // Remove oldest state
        }

        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        this.undoStack.push({
            imageData: new ImageData(
                new Uint8ClampedArray(imageData.data),
                imageData.width,
                imageData.height
            )
        });

        this.updateUndoButton();
    }

    updateUndoButton() {
        document.getElementById('undoBtn').disabled = this.undoStack.length === 0;
    }

    startDrawing(e) {
        if (this.currentTool === 'brush') {
            this.saveState();
            this.isDrawing = true;
            this.draw(e);
        }
    }

    draw(e) {
        if (!this.isDrawing || this.currentTool !== 'brush') return;

        const rect = this.canvas.getBoundingClientRect();

        // Calculate scaled coordinates
        const scaleX = this.canvas.width / rect.width;
        const scaleY = this.canvas.height / rect.height;
        const x = (e.clientX - rect.left) * scaleX;
        const y = (e.clientY - rect.top) * scaleY;

        this.ctx.globalCompositeOperation = 'destination-out';
        this.ctx.beginPath();
        this.ctx.arc(x, y, this.brushSize / 2, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.globalCompositeOperation = 'source-over';
    }

    stopDrawing() {
        this.isDrawing = false;
    }

    handleClick(e) {
        if (this.currentTool === 'flood' || this.currentTool === 'magic') {
            this.saveState();

            const rect = this.canvas.getBoundingClientRect();

            // Calculate scaled coordinates to account for canvas display size vs actual size
            const scaleX = this.canvas.width / rect.width;
            const scaleY = this.canvas.height / rect.height;
            const x = Math.floor((e.clientX - rect.left) * scaleX);
            const y = Math.floor((e.clientY - rect.top) * scaleY);

            console.log(`Click at screen coords: ${e.clientX - rect.left}, ${e.clientY - rect.top}`);
            console.log(`Canvas size: ${this.canvas.width}x${this.canvas.height}, Display size: ${rect.width}x${rect.height}`);
            console.log(`Scale factors: ${scaleX}, ${scaleY}`);
            console.log(`Adjusted canvas coords: ${x}, ${y}`);

            // Get current click action mode
            const clickAction = document.getElementById('clickAction').value;

            if (this.currentTool === 'flood') {
                if (clickAction === 'remove') {
                    this.floodFill(x, y);
                } else if (clickAction === 'flatten') {
                    this.floodFlatten(x, y);
                }
            } else if (this.currentTool === 'magic') {
                if (clickAction === 'remove') {
                    this.magicWand(x, y);
                } else if (clickAction === 'flatten') {
                    this.magicFlatten(x, y);
                }
            }
        }
    }

    floodFill(startX, startY) {
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        const width = imageData.width;
        const height = imageData.height;

        const startIndex = (startY * width + startX) * 4;
        const startR = data[startIndex];
        const startG = data[startIndex + 1];
        const startB = data[startIndex + 2];
        const startA = data[startIndex + 3];

        if (startA === 0) return; // Already transparent

        const stack = [[startX, startY]];
        const visited = new Set();

        while (stack.length > 0) {
            const [x, y] = stack.pop();
            const key = `${x},${y}`;

            if (visited.has(key)) continue;
            if (x < 0 || x >= width || y < 0 || y >= height) continue;

            const index = (y * width + x) * 4;
            const r = data[index];
            const g = data[index + 1];
            const b = data[index + 2];
            const a = data[index + 3];

            if (a === 0) continue; // Already transparent

            // Check if color is within tolerance
            const colorDiff = Math.sqrt(
                Math.pow(r - startR, 2) +
                Math.pow(g - startG, 2) +
                Math.pow(b - startB, 2)
            );

            if (colorDiff <= this.tolerance * 2.55) { // Convert percentage to 255 scale
                visited.add(key);

                // Make pixel transparent
                data[index + 3] = 0;

                // Add neighboring pixels to stack
                stack.push([x + 1, y]);
                stack.push([x - 1, y]);
                stack.push([x, y + 1]);
                stack.push([x, y - 1]);
            }
        }

        this.ctx.putImageData(imageData, 0, 0);
    }

    magicWand(clickX, clickY) {
        // Similar to flood fill but selects all similar colors across the entire image
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        const width = imageData.width;
        const height = imageData.height;

        const startIndex = (clickY * width + clickX) * 4;
        const startR = data[startIndex];
        const startG = data[startIndex + 1];
        const startB = data[startIndex + 2];
        const startA = data[startIndex + 3];

        if (startA === 0) return; // Already transparent

        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const a = data[i + 3];

            if (a === 0) continue; // Already transparent

            const colorDiff = Math.sqrt(
                Math.pow(r - startR, 2) +
                Math.pow(g - startG, 2) +
                Math.pow(b - startB, 2)
            );

            if (colorDiff <= this.tolerance * 2.55) {
                data[i + 3] = 0; // Make transparent
            }
        }

        this.ctx.putImageData(imageData, 0, 0);
    }

    floodFlatten(startX, startY) {
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        const width = imageData.width;
        const height = imageData.height;

        const startIndex = (startY * width + startX) * 4;
        const startR = data[startIndex];
        const startG = data[startIndex + 1];
        const startB = data[startIndex + 2];
        const startA = data[startIndex + 3];

        if (startA === 0) return; // Skip transparent pixels

        console.log(`Starting flood flatten at ${startX},${startY} with tolerance ${this.tolerance}`);

        // Use array for better performance with large areas
        const visited = new Array(height).fill(null).map(() => new Array(width).fill(false));
        const stack = [[startX, startY]];
        const similarPixels = [];

        while (stack.length > 0) {
            const [x, y] = stack.pop();

            // Check bounds and if already visited
            if (x < 0 || x >= width || y < 0 || y >= height || visited[y][x]) continue;

            const index = (y * width + x) * 4;
            const r = data[index];
            const g = data[index + 1];
            const b = data[index + 2];
            const a = data[index + 3];

            if (a === 0) continue; // Skip transparent pixels

            // Check if color is within tolerance
            const colorDiff = Math.sqrt(
                Math.pow(r - startR, 2) +
                Math.pow(g - startG, 2) +
                Math.pow(b - startB, 2)
            );

            if (colorDiff <= this.tolerance * 2.55) {
                visited[y][x] = true;
                similarPixels.push({r, g, b, a, index});

                // Add neighboring pixels to stack (check bounds first)
                if (x + 1 < width && !visited[y][x + 1]) stack.push([x + 1, y]);
                if (x - 1 >= 0 && !visited[y][x - 1]) stack.push([x - 1, y]);
                if (y + 1 < height && !visited[y + 1][x]) stack.push([x, y + 1]);
                if (y - 1 >= 0 && !visited[y - 1][x]) stack.push([x, y - 1]);
            }
        }

        // Calculate average color
        if (similarPixels.length > 0) {
            let avgR = 0, avgG = 0, avgB = 0, avgA = 0;

            for (const pixel of similarPixels) {
                avgR += pixel.r;
                avgG += pixel.g;
                avgB += pixel.b;
                avgA += pixel.a;
            }

            avgR = Math.round(avgR / similarPixels.length);
            avgG = Math.round(avgG / similarPixels.length);
            avgB = Math.round(avgB / similarPixels.length);
            avgA = Math.round(avgA / similarPixels.length);

            // Apply average color to all similar pixels
            for (const pixel of similarPixels) {
                data[pixel.index] = avgR;
                data[pixel.index + 1] = avgG;
                data[pixel.index + 2] = avgB;
                data[pixel.index + 3] = avgA;
            }

            this.ctx.putImageData(imageData, 0, 0);
            console.log(`Flattened ${similarPixels.length} pixels to average color [${avgR},${avgG},${avgB},${avgA}]`);
        } else {
            console.log('No similar pixels found for flattening');
        }
    }

    magicFlatten(clickX, clickY) {
        // Similar to magic wand but flattens instead of removes
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        const width = imageData.width;
        const height = imageData.height;

        const startIndex = (clickY * width + clickX) * 4;
        const startR = data[startIndex];
        const startG = data[startIndex + 1];
        const startB = data[startIndex + 2];
        const startA = data[startIndex + 3];

        if (startA === 0) return; // Skip transparent pixels

        // Collect all similar pixels across the entire image
        const similarPixels = [];

        for (let i = 0; i < data.length; i += 4) {
            const r = data[i];
            const g = data[i + 1];
            const b = data[i + 2];
            const a = data[i + 3];

            if (a === 0) continue; // Skip transparent pixels

            const colorDiff = Math.sqrt(
                Math.pow(r - startR, 2) +
                Math.pow(g - startG, 2) +
                Math.pow(b - startB, 2)
            );

            if (colorDiff <= this.tolerance * 2.55) {
                similarPixels.push({r, g, b, a, index: i});
            }
        }

        // Calculate average color
        if (similarPixels.length > 0) {
            let avgR = 0, avgG = 0, avgB = 0, avgA = 0;

            for (const pixel of similarPixels) {
                avgR += pixel.r;
                avgG += pixel.g;
                avgB += pixel.b;
                avgA += pixel.a;
            }

            avgR = Math.round(avgR / similarPixels.length);
            avgG = Math.round(avgG / similarPixels.length);
            avgB = Math.round(avgB / similarPixels.length);
            avgA = Math.round(avgA / similarPixels.length);

            // Apply average color to all similar pixels
            for (const pixel of similarPixels) {
                data[pixel.index] = avgR;
                data[pixel.index + 1] = avgG;
                data[pixel.index + 2] = avgB;
                data[pixel.index + 3] = avgA;
            }
        }

        this.ctx.putImageData(imageData, 0, 0);
    }

    undo() {
        if (this.undoStack.length > 0) {
            const state = this.undoStack.pop();
            this.ctx.putImageData(state.imageData, 0, 0);
            this.updateUndoButton();
        }
    }

    reset() {
        if (this.originalImageData) {
            this.ctx.putImageData(this.originalImageData, 0, 0);
            this.undoStack = [];
            this.updateUndoButton();
        }
    }

    clearAll() {
        // Reset the entire program to initial state
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.undoStack = [];
        this.originalImageData = null;
        this.currentImageData = null;
        this.lastResult = null;

        // Hide all sections except upload
        document.getElementById('uploadSection').style.display = 'block';
        document.getElementById('editorSection').style.display = 'none';
        document.getElementById('editingToolbar').style.display = 'none';
        document.getElementById('downloadSection').style.display = 'none';
        document.getElementById('canvasOverlay').style.display = 'block';

        // Reset buttons
        document.getElementById('upscaleBtn').disabled = true;
        this.updateUndoButton();

        console.log('Program reset - ready for new image upload');
    }

    async upscale() {
        const scaleFactor = document.getElementById('scaleFactor').value;
        const upscaleMethod = document.getElementById('upscaleMethod').value;
        const preserveContrast = document.getElementById('preserveContrast').checked;
        const logoType = document.getElementById('logoType').value;

        // Show progress
        document.getElementById('progressSection').style.display = 'block';

        try {
            // Get current canvas as blob
            const canvas = document.getElementById('imageCanvas');
            const blob = await new Promise(resolve => canvas.toBlob(resolve));

            // Create form data
            const formData = new FormData();
            formData.append('image', blob);
            formData.append('scale_factor', scaleFactor);
            formData.append('method', upscaleMethod);
            formData.append('preserve_contrast', preserveContrast);
            formData.append('logo_type', logoType);

            // Send to test endpoint using API Gateway
            const apiUrl = `${this.API_BASE_URL}/process_upscale`;

            const response = await fetch(apiUrl, {
                method: 'POST',
                body: formData
            });

            const result = await response.json();

            if (result.success) {
                this.replaceCanvasImage(result.upscaled_image);
            } else {
                this.showError(result.error);
            }
        } catch (error) {
            this.showError('Error upscaling image: ' + error.message);
        } finally {
            document.getElementById('progressSection').style.display = 'none';
        }
    }

    showUpscaleResults(result) {
        // Show preview section
        document.getElementById('previewSection').style.display = 'block';

        // Show original image preview
        const previewCanvas = document.getElementById('previewCanvas');
        const previewCtx = previewCanvas.getContext('2d');
        const originalImg = new Image();
        originalImg.onload = () => {
            previewCanvas.width = originalImg.width;
            previewCanvas.height = originalImg.height;
            previewCtx.drawImage(originalImg, 0, 0);
        };
        originalImg.src = 'data:image/png;base64,' + result.original_image;

        // Show upscaled image
        const upscaledCanvas = document.getElementById('upscaledCanvas');
        const upscaledCtx = upscaledCanvas.getContext('2d');
        const upscaledImg = new Image();
        upscaledImg.onload = () => {
            upscaledCanvas.width = upscaledImg.width;
            upscaledCanvas.height = upscaledImg.height;
            upscaledCtx.drawImage(upscaledImg, 0, 0);
        };
        upscaledImg.src = 'data:image/png;base64,' + result.upscaled_image;

        // Store results for download
        this.lastResult = result;

        // Show download buttons
        document.getElementById('downloadPngBtn').style.display = 'inline-block';
        document.getElementById('downloadUpscaledBtn').style.display = 'inline-block';
    }

    replaceCanvasImage(base64Image) {
        // Save current state before replacing
        this.saveState();

        const img = new Image();
        img.onload = () => {
            // Resize canvas to match new image
            this.canvas.width = img.width;
            this.canvas.height = img.height;

            // Clear and draw new image
            this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
            this.ctx.drawImage(img, 0, 0);

            // CRITICAL: Update stored image data after the image is drawn
            this.originalImageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
            this.currentImageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);

            // Clear undo stack since we have a new image
            this.undoStack = [];
            this.updateUndoButton();

            // Show editing tools after upscaling
            document.getElementById('editingToolbar').style.display = 'block';

            console.log(`Canvas updated with upscaled image: ${img.width}x${img.height}`);
            console.log('Canvas image data synchronized for editing tools');
        };
        img.src = 'data:image/png;base64,' + base64Image;
    }

    showError(error) {
        alert('Error: ' + error);
    }

    downloadPNG() {
        if (this.lastResult) {
            const link = document.createElement('a');
            link.download = 'logo-original.png';
            link.href = 'data:image/png;base64,' + this.lastResult.original_image;
            link.click();
        }
    }

    downloadUpscaled() {
        if (this.lastResult) {
            const link = document.createElement('a');
            link.download = `logo-upscaled-${this.lastResult.scale_factor}x.png`;
            link.href = 'data:image/png;base64,' + this.lastResult.upscaled_image;
            link.click();
        }
    }

    downloadCurrentImage() {
        if (this.canvas && this.canvas.width > 0 && this.canvas.height > 0) {
            const link = document.createElement('a');
            link.download = 'logo-current.png';
            link.href = this.canvas.toDataURL('image/png');
            link.click();
        }
    }
}

// Initialize when page loads
document.addEventListener('DOMContentLoaded', () => {
    new TestInteractiveEditor();
});