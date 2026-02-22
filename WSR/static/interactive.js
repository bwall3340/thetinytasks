class InteractiveBackgroundRemover {
    constructor() {
        this.canvas = document.getElementById('imageCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.previewCanvas = document.getElementById('previewCanvas');
        this.previewCtx = this.previewCanvas.getContext('2d');

        this.originalImage = null;
        this.currentImageData = null;
        this.originalImageData = null;
        this.removedAreas = [];
        this.currentFile = null;

        // API Configuration
        // TODO: Replace this with your actual API Gateway URL
        this.API_BASE_URL = this.getApiBaseUrl();

        this.setupEventListeners();
    }

    getApiBaseUrl() {
        // Always use relative URLs — served by the same origin in all environments
        return '';
    }

    setupEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');

        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        uploadArea.addEventListener('drop', (e) => this.handleDrop(e));

        // Canvas clicking
        this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));

        // Tolerance slider
        const toleranceSlider = document.getElementById('toleranceSlider');
        toleranceSlider.addEventListener('input', (e) => {
            document.getElementById('toleranceValue').textContent = e.target.value;
        });

        // Toolbar buttons
        document.getElementById('undoBtn').addEventListener('click', () => this.undo());
        document.getElementById('resetBtn').addEventListener('click', () => this.reset());
        document.getElementById('clearAllBtn').addEventListener('click', () => this.clearAll());
        document.getElementById('vectorizeBtn').addEventListener('click', () => this.vectorize());

        // Download buttons
        document.getElementById('downloadPngBtn').addEventListener('click', () => this.downloadPng());
        document.getElementById('downloadSvgBtn').addEventListener('click', () => this.downloadSvg());
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) this.loadImage(file);
    }

    handleDragOver(event) {
        event.preventDefault();
        document.getElementById('uploadArea').classList.add('drag-over');
    }

    handleDragLeave(event) {
        event.preventDefault();
        document.getElementById('uploadArea').classList.remove('drag-over');
    }

    handleDrop(event) {
        event.preventDefault();
        document.getElementById('uploadArea').classList.remove('drag-over');
        const files = event.dataTransfer.files;
        if (files.length > 0) this.loadImage(files[0]);
    }

    loadImage(file) {
        // Validate file
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff'];
        if (!validTypes.includes(file.type)) {
            this.showError('Please select a valid image file');
            return;
        }

        this.currentFile = file;
        const reader = new FileReader();
        reader.onload = (e) => {
            const img = new Image();
            img.onload = () => {
                this.originalImage = img;
                this.setupCanvas();
                this.showEditor();
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }

    setupCanvas() {
        // Set canvas size to fit image while maintaining aspect ratio
        const maxWidth = 800;
        const maxHeight = 600;

        let { width, height } = this.originalImage;

        if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width *= ratio;
            height *= ratio;
        }

        this.canvas.width = width;
        this.canvas.height = height;
        this.previewCanvas.width = width;
        this.previewCanvas.height = height;

        // Draw original image
        this.ctx.drawImage(this.originalImage, 0, 0, width, height);

        // Store original image data
        this.originalImageData = this.ctx.getImageData(0, 0, width, height);
        this.currentImageData = this.ctx.createImageData(this.originalImageData);
        this.currentImageData.data.set(this.originalImageData.data);

        // Clear removed areas array
        this.removedAreas = [];

        // Enable vectorize button
        document.getElementById('vectorizeBtn').disabled = false;
    }

    showEditor() {
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('editorSection').style.display = 'block';
        document.getElementById('canvasOverlay').style.display = 'none';
    }

    handleCanvasClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = Math.floor((event.clientX - rect.left) * (this.canvas.width / rect.width));
        const y = Math.floor((event.clientY - rect.top) * (this.canvas.height / rect.height));

        const tolerance = parseInt(document.getElementById('toleranceSlider').value);

        // Store current state for undo
        const currentState = this.ctx.createImageData(this.currentImageData);
        currentState.data.set(this.currentImageData.data);
        this.removedAreas.push(currentState);

        // Enable undo button
        document.getElementById('undoBtn').disabled = false;

        // Perform flood fill
        this.floodFill(x, y, tolerance);

        // Update canvas
        this.ctx.putImageData(this.currentImageData, 0, 0);
    }

    floodFill(startX, startY, tolerance) {
        const width = this.currentImageData.width;
        const height = this.currentImageData.height;
        const data = this.currentImageData.data;

        // Get target color
        const startIndex = (startY * width + startX) * 4;
        const targetR = data[startIndex];
        const targetG = data[startIndex + 1];
        const targetB = data[startIndex + 2];
        const targetA = data[startIndex + 3];

        // If already transparent, do nothing
        if (targetA === 0) return;

        const visited = new Set();
        const stack = [[startX, startY]];

        while (stack.length > 0) {
            const [x, y] = stack.pop();

            if (x < 0 || x >= width || y < 0 || y >= height) continue;

            const key = `${x},${y}`;
            if (visited.has(key)) continue;
            visited.add(key);

            const index = (y * width + x) * 4;
            const r = data[index];
            const g = data[index + 1];
            const b = data[index + 2];
            const a = data[index + 3];

            // Skip if already transparent
            if (a === 0) continue;

            // Check if color is within tolerance
            const colorDistance = Math.sqrt(
                Math.pow(r - targetR, 2) +
                Math.pow(g - targetG, 2) +
                Math.pow(b - targetB, 2)
            );

            if (colorDistance <= tolerance) {
                // Make pixel transparent
                data[index + 3] = 0;

                // Add neighbors to stack
                stack.push([x + 1, y]);
                stack.push([x - 1, y]);
                stack.push([x, y + 1]);
                stack.push([x, y - 1]);
            }
        }
    }

    undo() {
        if (this.removedAreas.length > 0) {
            const previousState = this.removedAreas.pop();
            this.currentImageData.data.set(previousState.data);
            this.ctx.putImageData(this.currentImageData, 0, 0);

            if (this.removedAreas.length === 0) {
                document.getElementById('undoBtn').disabled = true;
            }
        }
    }

    reset() {
        this.currentImageData.data.set(this.originalImageData.data);
        this.ctx.putImageData(this.currentImageData, 0, 0);
        this.removedAreas = [];
        document.getElementById('undoBtn').disabled = true;
        document.getElementById('previewSection').style.display = 'none';
    }

    clearAll() {
        const data = this.currentImageData.data;
        for (let i = 3; i < data.length; i += 4) {
            data[i] = 0; // Set all alpha to 0
        }
        this.ctx.putImageData(this.currentImageData, 0, 0);
        document.getElementById('undoBtn').disabled = false;
    }

    async vectorize() {
        document.getElementById('progressSection').style.display = 'block';

        try {
            // Convert canvas to blob
            const blob = await new Promise(resolve => {
                this.canvas.toBlob(resolve, 'image/png');
            });

            // Send to backend
            const formData = new FormData();
            formData.append('image', blob, 'edited_image.png');
            formData.append('epsilon', '0.02');

            // Use API Gateway URL
            const apiUrl = `${this.API_BASE_URL}/process_interactive`;

            const response = await fetch(apiUrl, {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }

            const result = await response.json();

            if (result.success) {
                this.displayResults(result);
            } else {
                this.showError(result.error || 'Vectorization failed');
            }
        } catch (error) {
            this.showError(`Error: ${error.message}`);
        } finally {
            document.getElementById('progressSection').style.display = 'none';
        }
    }

    displayResults(result) {
        // Show preview canvas
        const previewImg = new Image();
        previewImg.onload = () => {
            this.previewCtx.clearRect(0, 0, this.previewCanvas.width, this.previewCanvas.height);
            this.previewCtx.drawImage(previewImg, 0, 0, this.previewCanvas.width, this.previewCanvas.height);
        };
        previewImg.src = `data:image/png;base64,${result.no_bg_image}`;

        // Show SVG
        document.getElementById('svgContainer').innerHTML = result.svg_content;

        // Store data for downloads
        this.pngData = result.no_bg_image;
        this.svgData = result.svg_content;

        // Show download buttons
        document.getElementById('downloadPngBtn').style.display = 'block';
        document.getElementById('downloadSvgBtn').style.display = 'block';

        // Show preview section
        document.getElementById('previewSection').style.display = 'block';
        document.getElementById('previewSection').scrollIntoView({ behavior: 'smooth' });
    }

    downloadPng() {
        if (!this.pngData) return;

        const link = document.createElement('a');
        link.download = `${this.getFileName()}_background_removed.png`;
        link.href = `data:image/png;base64,${this.pngData}`;
        link.click();
    }

    downloadSvg() {
        if (!this.svgData) return;

        const blob = new Blob([this.svgData], { type: 'image/svg+xml' });
        const url = URL.createObjectURL(blob);

        const link = document.createElement('a');
        link.download = `${this.getFileName()}_vector.svg`;
        link.href = url;
        link.click();

        URL.revokeObjectURL(url);
    }

    getFileName() {
        if (!this.currentFile) return 'logo';
        return this.currentFile.name.split('.')[0];
    }

    showError(message) {
        const toast = document.createElement('div');
        toast.className = 'error-toast';
        toast.innerHTML = `
            <i class="fas fa-exclamation-circle"></i>
            <span>${message}</span>
            <button onclick="this.parentElement.remove()">
                <i class="fas fa-times"></i>
            </button>
        `;

        document.body.appendChild(toast);
        setTimeout(() => {
            if (toast.parentElement) toast.remove();
        }, 5000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new InteractiveBackgroundRemover();
});