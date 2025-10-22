class EnhancedBackgroundRemover {
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
        this.currentTool = 'flood';
        this.isDrawing = false;

        this.setupEventListeners();
    }

    setupEventListeners() {
        // File upload
        const fileInput = document.getElementById('fileInput');
        const uploadArea = document.getElementById('uploadArea');

        fileInput.addEventListener('change', (e) => this.handleFileSelect(e));
        uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        uploadArea.addEventListener('drop', (e) => this.handleDrop(e));

        // Canvas interaction
        this.canvas.addEventListener('mousedown', (e) => this.handleMouseDown(e));
        this.canvas.addEventListener('mousemove', (e) => this.handleMouseMove(e));
        this.canvas.addEventListener('mouseup', (e) => this.handleMouseUp(e));
        this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));

        // Tool controls
        document.getElementById('toolMode').addEventListener('change', (e) => {
            this.currentTool = e.target.value;
            this.updateToolUI();
        });

        document.getElementById('toleranceSlider').addEventListener('input', (e) => {
            document.getElementById('toleranceValue').textContent = e.target.value;
        });

        document.getElementById('brushSize').addEventListener('input', (e) => {
            document.getElementById('brushSizeValue').textContent = e.target.value;
        });

        // Action buttons
        document.getElementById('undoBtn').addEventListener('click', () => this.undo());
        document.getElementById('resetBtn').addEventListener('click', () => this.reset());
        document.getElementById('clearAllBtn').addEventListener('click', () => this.clearAll());
        document.getElementById('vectorizeBtn').addEventListener('click', () => this.vectorize());

        // Download buttons
        document.getElementById('downloadPngBtn').addEventListener('click', () => this.downloadPng());
        document.getElementById('downloadSvgBtn').addEventListener('click', () => this.downloadSvg());
    }

    updateToolUI() {
        const brushGroup = document.getElementById('brushGroup');
        const canvas = this.canvas;

        if (this.currentTool === 'brush') {
            brushGroup.style.display = 'block';
            canvas.style.cursor = 'crosshair';
        } else {
            brushGroup.style.display = 'none';
            canvas.style.cursor = this.currentTool === 'flood' ? 'crosshair' : 'pointer';
        }
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
        const maxWidth = 900;
        const maxHeight = 700;

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

        this.ctx.drawImage(this.originalImage, 0, 0, width, height);

        this.originalImageData = this.ctx.getImageData(0, 0, width, height);
        this.currentImageData = this.ctx.createImageData(this.originalImageData);
        this.currentImageData.data.set(this.originalImageData.data);

        this.removedAreas = [];
        document.getElementById('vectorizeBtn').disabled = false;
    }

    showEditor() {
        document.getElementById('uploadSection').style.display = 'none';
        document.getElementById('editorSection').style.display = 'block';
        document.getElementById('canvasOverlay').style.display = 'none';
    }

    getMousePos(event) {
        const rect = this.canvas.getBoundingClientRect();
        return {
            x: Math.floor((event.clientX - rect.left) * (this.canvas.width / rect.width)),
            y: Math.floor((event.clientY - rect.top) * (this.canvas.height / rect.height))
        };
    }

    handleMouseDown(event) {
        if (this.currentTool === 'brush') {
            this.isDrawing = true;
            this.saveState();
            const pos = this.getMousePos(event);
            this.brushRemove(pos.x, pos.y);
        }
    }

    handleMouseMove(event) {
        if (this.currentTool === 'brush' && this.isDrawing) {
            const pos = this.getMousePos(event);
            this.brushRemove(pos.x, pos.y);
        }
    }

    handleMouseUp(event) {
        if (this.currentTool === 'brush') {
            this.isDrawing = false;
            this.ctx.putImageData(this.currentImageData, 0, 0);
        }
    }

    handleCanvasClick(event) {
        if (this.currentTool === 'flood' || this.currentTool === 'magic') {
            const pos = this.getMousePos(event);
            const tolerance = parseInt(document.getElementById('toleranceSlider').value);

            this.saveState();

            if (this.currentTool === 'flood') {
                this.floodFill(pos.x, pos.y, tolerance);
            } else if (this.currentTool === 'magic') {
                this.magicWand(pos.x, pos.y, tolerance);
            }

            this.ctx.putImageData(this.currentImageData, 0, 0);
        }
    }

    saveState() {
        const currentState = this.ctx.createImageData(this.currentImageData);
        currentState.data.set(this.currentImageData.data);
        this.removedAreas.push(currentState);
        document.getElementById('undoBtn').disabled = false;
    }

    floodFill(startX, startY, tolerance) {
        const width = this.currentImageData.width;
        const height = this.currentImageData.height;
        const data = this.currentImageData.data;

        const startIndex = (startY * width + startX) * 4;
        const targetR = data[startIndex];
        const targetG = data[startIndex + 1];
        const targetB = data[startIndex + 2];
        const targetA = data[startIndex + 3];

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

            if (a === 0) continue;

            const colorDistance = Math.sqrt(
                Math.pow(r - targetR, 2) +
                Math.pow(g - targetG, 2) +
                Math.pow(b - targetB, 2)
            );

            if (colorDistance <= tolerance) {
                data[index + 3] = 0;

                stack.push([x + 1, y]);
                stack.push([x - 1, y]);
                stack.push([x, y + 1]);
                stack.push([x, y - 1]);
            }
        }
    }

    magicWand(startX, startY, tolerance) {
        // Enhanced magic wand with edge detection
        const width = this.currentImageData.width;
        const height = this.currentImageData.height;
        const data = this.currentImageData.data;

        const startIndex = (startY * width + startX) * 4;
        const targetR = data[startIndex];
        const targetG = data[startIndex + 1];
        const targetB = data[startIndex + 2];
        const targetA = data[startIndex + 3];

        if (targetA === 0) return;

        // Find all similar pixels
        const similarPixels = [];
        for (let y = 0; y < height; y++) {
            for (let x = 0; x < width; x++) {
                const index = (y * width + x) * 4;
                const r = data[index];
                const g = data[index + 1];
                const b = data[index + 2];
                const a = data[index + 3];

                if (a === 0) continue;

                const colorDistance = Math.sqrt(
                    Math.pow(r - targetR, 2) +
                    Math.pow(g - targetG, 2) +
                    Math.pow(b - targetB, 2)
                );

                if (colorDistance <= tolerance) {
                    similarPixels.push({ x, y, index });
                }
            }
        }

        // Remove similar pixels
        similarPixels.forEach(pixel => {
            data[pixel.index + 3] = 0;
        });
    }

    brushRemove(x, y) {
        const brushSize = parseInt(document.getElementById('brushSize').value);
        const data = this.currentImageData.data;
        const width = this.currentImageData.width;
        const height = this.currentImageData.height;

        const radius = brushSize / 2;

        for (let dy = -radius; dy <= radius; dy++) {
            for (let dx = -radius; dx <= radius; dx++) {
                const distance = Math.sqrt(dx * dx + dy * dy);
                if (distance <= radius) {
                    const px = Math.floor(x + dx);
                    const py = Math.floor(y + dy);

                    if (px >= 0 && px < width && py >= 0 && py < height) {
                        const index = (py * width + px) * 4;
                        data[index + 3] = 0; // Set alpha to 0
                    }
                }
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
            data[i] = 0;
        }
        this.ctx.putImageData(this.currentImageData, 0, 0);
        document.getElementById('undoBtn').disabled = false;
    }

    async vectorize() {
        document.getElementById('progressSection').style.display = 'block';

        try {
            const blob = await new Promise(resolve => {
                this.canvas.toBlob(resolve, 'image/png');
            });

            const formData = new FormData();
            formData.append('image', blob, 'edited_image.png');
            formData.append('epsilon', document.getElementById('detailLevel').value);

            const response = await fetch('/process_interactive', {
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
        const previewImg = new Image();
        previewImg.onload = () => {
            this.previewCtx.clearRect(0, 0, this.previewCanvas.width, this.previewCanvas.height);
            this.previewCtx.drawImage(previewImg, 0, 0, this.previewCanvas.width, this.previewCanvas.height);
        };
        previewImg.src = `data:image/png;base64,${result.no_bg_image}`;

        document.getElementById('svgContainer').innerHTML = result.svg_content;

        this.pngData = result.no_bg_image;
        this.svgData = result.svg_content;

        document.getElementById('downloadPngBtn').style.display = 'block';
        document.getElementById('downloadSvgBtn').style.display = 'block';

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
    new EnhancedBackgroundRemover();
});