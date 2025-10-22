class LogoVectorizer {
    constructor() {
        this.initializeElements();
        this.setupEventListeners();
        this.currentFile = null;
    }

    initializeElements() {
        this.uploadArea = document.getElementById('uploadArea');
        this.fileInput = document.getElementById('fileInput');
        this.epsilonSlider = document.getElementById('epsilonSlider');
        this.epsilonValue = document.getElementById('epsilonValue');
        this.processBtn = document.getElementById('processBtn');
        this.resultsSection = document.getElementById('resultsSection');
        this.progressBar = document.getElementById('progressBar');
        this.originalImage = document.getElementById('originalImage');
        this.noBgImage = document.getElementById('noBgImage');
        this.binaryImage = document.getElementById('binaryImage');
        this.svgContainer = document.getElementById('svgContainer');
        this.downloadPngBtn = document.getElementById('downloadPngBtn');
        this.downloadSvgBtn = document.getElementById('downloadSvgBtn');
        this.processingInfo = document.getElementById('processingInfo');
    }

    setupEventListeners() {
        // File input
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        // Drag and drop
        this.uploadArea.addEventListener('dragover', (e) => this.handleDragOver(e));
        this.uploadArea.addEventListener('dragleave', (e) => this.handleDragLeave(e));
        this.uploadArea.addEventListener('drop', (e) => this.handleDrop(e));

        // Epsilon slider
        this.epsilonSlider.addEventListener('input', (e) => this.updateEpsilonValue(e));

        // Process button
        this.processBtn.addEventListener('click', () => this.processImage());

        // Download buttons
        this.downloadPngBtn.addEventListener('click', () => this.downloadPng());
        this.downloadSvgBtn.addEventListener('click', () => this.downloadSvg());
    }

    handleFileSelect(event) {
        const file = event.target.files[0];
        if (file) {
            this.loadFile(file);
        }
    }

    handleDragOver(event) {
        event.preventDefault();
        this.uploadArea.classList.add('drag-over');
    }

    handleDragLeave(event) {
        event.preventDefault();
        this.uploadArea.classList.remove('drag-over');
    }

    handleDrop(event) {
        event.preventDefault();
        this.uploadArea.classList.remove('drag-over');

        const files = event.dataTransfer.files;
        if (files.length > 0) {
            this.loadFile(files[0]);
        }
    }

    loadFile(file) {
        // Validate file type
        const validTypes = ['image/png', 'image/jpeg', 'image/jpg', 'image/bmp', 'image/tiff'];
        if (!validTypes.includes(file.type)) {
            this.showError('Please select a valid image file (PNG, JPG, JPEG, BMP, TIFF)');
            return;
        }

        // Validate file size (max 10MB)
        if (file.size > 10 * 1024 * 1024) {
            this.showError('File size must be less than 10MB');
            return;
        }

        this.currentFile = file;

        // Show preview
        const reader = new FileReader();
        reader.onload = (e) => {
            this.originalImage.src = e.target.result;
            this.uploadArea.style.display = 'none';
            this.processBtn.disabled = false;

            // Update upload area to show selected file
            this.uploadArea.innerHTML = `
                <div class="file-selected">
                    <i class="fas fa-check-circle"></i>
                    <h3>File Selected</h3>
                    <p>${file.name}</p>
                    <p class="file-size">${this.formatFileSize(file.size)}</p>
                    <button class="change-file-btn" onclick="this.changeFile()">
                        <i class="fas fa-exchange-alt"></i> Change File
                    </button>
                </div>
            `;
            this.uploadArea.style.display = 'block';
        };
        reader.readAsDataURL(file);
    }

    changeFile() {
        this.uploadArea.innerHTML = `
            <div class="upload-content">
                <i class="fas fa-cloud-upload-alt"></i>
                <h3>Upload Your Logo</h3>
                <p>Drag and drop an image file here, or click to browse</p>
                <p class="file-types">Supports: PNG, JPG, JPEG, BMP, TIFF</p>
                <input type="file" id="fileInput" accept=".png,.jpg,.jpeg,.bmp,.tiff" hidden>
                <button class="browse-btn" onclick="document.getElementById('fileInput').click()">
                    <i class="fas fa-folder-open"></i> Browse Files
                </button>
            </div>
        `;

        // Re-initialize file input
        this.fileInput = document.getElementById('fileInput');
        this.fileInput.addEventListener('change', (e) => this.handleFileSelect(e));

        this.currentFile = null;
        this.processBtn.disabled = true;
        this.resultsSection.style.display = 'none';
    }

    updateEpsilonValue(event) {
        this.epsilonValue.textContent = event.target.value;
    }

    async processImage() {
        if (!this.currentFile) {
            this.showError('Please select a file first');
            return;
        }

        this.showProgress();

        const formData = new FormData();
        formData.append('image', this.currentFile);
        formData.append('epsilon', this.epsilonSlider.value);
        formData.append('detail_level', document.getElementById('detailMode').value);

        try {
            const response = await fetch('/process', {
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
                this.showError(result.error || 'Processing failed');
            }
        } catch (error) {
            this.showError(`Error: ${error.message}`);
        } finally {
            this.hideProgress();
        }
    }

    displayResults(result) {
        // Show results section
        this.resultsSection.style.display = 'block';

        // Display images
        this.noBgImage.src = `data:image/png;base64,${result.no_bg_image}`;
        this.binaryImage.src = `data:image/png;base64,${result.binary_image}`;

        // Display SVG
        this.svgContainer.innerHTML = result.svg_content;

        // Show download buttons
        this.downloadPngBtn.style.display = 'block';
        this.downloadSvgBtn.style.display = 'block';

        // Store data for downloads
        this.pngData = result.no_bg_image;
        this.svgData = result.svg_content;

        // Display processing info
        this.processingInfo.innerHTML = `
            <div class="info-item">
                <strong>Processing Status:</strong> Complete
            </div>
            <div class="info-item">
                <strong>Contours Found:</strong> ${result.contour_count}
            </div>
            <div class="info-item">
                <strong>Original Size:</strong> ${result.original_size}
            </div>
            <div class="info-item">
                <strong>Detail Level:</strong> ${result.epsilon_factor}
            </div>
            <div class="info-item">
                <strong>Processing Time:</strong> ${result.processing_time}s
            </div>
        `;

        // Scroll to results
        this.resultsSection.scrollIntoView({ behavior: 'smooth' });
    }

    downloadPng() {
        if (!this.pngData) return;

        const link = document.createElement('a');
        link.download = `${this.getFileName()}_no_bg.png`;
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

    showProgress() {
        this.progressBar.style.display = 'block';
        this.processBtn.disabled = true;
        this.processBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Processing...';
    }

    hideProgress() {
        this.progressBar.style.display = 'none';
        this.processBtn.disabled = false;
        this.processBtn.innerHTML = '<i class="fas fa-magic"></i> Process Image';
    }

    showError(message) {
        // Create error toast
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

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentElement) {
                toast.remove();
            }
        }, 5000);
    }

    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    new LogoVectorizer();
});

// Global function for change file button
window.changeFile = function() {
    if (window.logoVectorizer) {
        window.logoVectorizer.changeFile();
    }
};