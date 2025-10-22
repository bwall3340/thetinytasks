class WhiteBackgroundRemover {
    constructor() {
        this.canvas = document.getElementById('imageCanvas');
        this.ctx = this.canvas.getContext('2d');
        this.originalImageData = null;
        this.currentImageData = null;
        this.tolerance = 100;
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        const fileInput = document.getElementById('fileInput');
        const imageArea = document.getElementById('imageArea');
        const toleranceSlider = document.getElementById('toleranceSlider');
        const toleranceValue = document.getElementById('toleranceValue');
        const resetBtn = document.getElementById('resetBtn');
        const downloadBtn = document.getElementById('downloadBtn');
        
        // File upload
        fileInput.addEventListener('change', (e) => this.handleImageUpload(e));
        
        // Drag and drop
        imageArea.addEventListener('dragover', (e) => {
            e.preventDefault();
            imageArea.classList.add('dragover');
        });
        
        imageArea.addEventListener('dragleave', () => {
            imageArea.classList.remove('dragover');
        });
        
        imageArea.addEventListener('drop', (e) => {
            e.preventDefault();
            imageArea.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                this.loadImage(files[0]);
            }
        });
        
        // Canvas click
        this.canvas.addEventListener('click', (e) => this.handleCanvasClick(e));
        
        // Tolerance slider
        toleranceSlider.addEventListener('input', (e) => {
            this.tolerance = parseInt(e.target.value);
            toleranceValue.textContent = this.tolerance;
        });
        
        // Control buttons
        resetBtn.addEventListener('click', () => this.resetToUpload());
        downloadBtn.addEventListener('click', () => this.downloadImage());
    }
    
    handleImageUpload(event) {
        const file = event.target.files[0];
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
                this.drawImage(img);
                this.enableControls();
            };
            img.src = e.target.result;
        };
        reader.readAsDataURL(file);
    }
    
    setupCanvas(img) {
        const maxWidth = 800;
        const maxHeight = 600;
        
        let { width, height } = img;
        
        // Scale down if image is too large
        if (width > maxWidth || height > maxHeight) {
            const ratio = Math.min(maxWidth / width, maxHeight / height);
            width *= ratio;
            height *= ratio;
        }
        
        this.canvas.width = width;
        this.canvas.height = height;
        
        // Hide upload prompt and show canvas
        document.getElementById('uploadPrompt').style.display = 'none';
        this.canvas.style.display = 'block';
    }
    
    drawImage(img) {
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        this.ctx.drawImage(img, 0, 0, this.canvas.width, this.canvas.height);
        
        // Store original image data
        this.originalImageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        this.currentImageData = this.ctx.createImageData(this.originalImageData);
        this.currentImageData.data.set(this.originalImageData.data);
    }
    
    handleCanvasClick(event) {
        const rect = this.canvas.getBoundingClientRect();
        const x = Math.floor((event.clientX - rect.left) * (this.canvas.width / rect.width));
        const y = Math.floor((event.clientY - rect.top) * (this.canvas.height / rect.height));
        
        this.removeBackgroundAt(x, y);
    }
    
    removeBackgroundAt(startX, startY) {
        const imageData = this.ctx.getImageData(0, 0, this.canvas.width, this.canvas.height);
        const data = imageData.data;
        const width = this.canvas.width;
        const height = this.canvas.height;
        
        // Get the color at the clicked position
        const startIndex = (startY * width + startX) * 4;
        const targetColor = {
            r: data[startIndex],
            g: data[startIndex + 1],
            b: data[startIndex + 2],
            a: data[startIndex + 3]
        };
        
        // Flood fill algorithm to find connected pixels
        const visited = new Set();
        const stack = [{x: startX, y: startY}];
        
        while (stack.length > 0) {
            const {x, y} = stack.pop();
            
            // Check bounds
            if (x < 0 || x >= width || y < 0 || y >= height) continue;
            
            const key = `${x},${y}`;
            if (visited.has(key)) continue;
            
            const index = (y * width + x) * 4;
            const currentColor = {
                r: data[index],
                g: data[index + 1],
                b: data[index + 2],
                a: data[index + 3]
            };
            
            // Check if current pixel matches target color within tolerance
            if (this.colorsMatch(targetColor, currentColor, this.tolerance)) {
                visited.add(key);
                
                // Make pixel transparent
                data[index + 3] = 0; // Set alpha to 0
                
                // Add neighboring pixels to stack
                stack.push({x: x + 1, y: y});
                stack.push({x: x - 1, y: y});
                stack.push({x: x, y: y + 1});
                stack.push({x: x, y: y - 1});
            }
        }
        
        // Update canvas with modified image data
        this.ctx.putImageData(imageData, 0, 0);
        
        // Store current state
        this.currentImageData = imageData;
    }
    
    colorsMatch(color1, color2, tolerance) {
        return Math.abs(color1.r - color2.r) <= tolerance &&
               Math.abs(color1.g - color2.g) <= tolerance &&
               Math.abs(color1.b - color2.b) <= tolerance;
    }
    
    resetImage() {
        if (this.originalImageData) {
            this.ctx.putImageData(this.originalImageData, 0, 0);
            this.currentImageData = this.ctx.createImageData(this.originalImageData);
            this.currentImageData.data.set(this.originalImageData.data);
        }
    }
    
    resetToUpload() {
        // Clear image data
        this.originalImageData = null;
        this.currentImageData = null;
        
        // Hide canvas and show upload prompt
        this.canvas.style.display = 'none';
        document.getElementById('uploadPrompt').style.display = 'block';
        
        // Reset file input
        document.getElementById('fileInput').value = '';
        
        // Disable controls
        this.disableControls();
    }
    
    downloadImage() {
        // Create a temporary canvas with transparent background
        const tempCanvas = document.createElement('canvas');
        const tempCtx = tempCanvas.getContext('2d');
        
        tempCanvas.width = this.canvas.width;
        tempCanvas.height = this.canvas.height;
        
        // Draw current image data to temp canvas
        tempCtx.putImageData(this.currentImageData || this.originalImageData, 0, 0);
        
        // Create download link
        tempCanvas.toBlob((blob) => {
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'background_removed_image.png';
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);
        }, 'image/png');
    }
    
    enableControls() {
        document.getElementById('resetBtn').disabled = false;
        document.getElementById('downloadBtn').disabled = false;
    }
    
    disableControls() {
        document.getElementById('resetBtn').disabled = true;
        document.getElementById('downloadBtn').disabled = true;
    }
}

// Initialize the application when the page loads
document.addEventListener('DOMContentLoaded', () => {
    new WhiteBackgroundRemover();
    initMobileMenu();
});

// Mobile menu functionality
function initMobileMenu() {
    const hamburgerMenu = document.getElementById('hamburger-menu');
    const mobileMenu = document.getElementById('mobile-menu');

    hamburgerMenu.addEventListener('click', function() {
        hamburgerMenu.classList.toggle('active');
        mobileMenu.classList.toggle('active');
    });

    // Close menu when clicking overlay
    mobileMenu.addEventListener('click', function(e) {
        if (e.target === mobileMenu) {
            hamburgerMenu.classList.remove('active');
            mobileMenu.classList.remove('active');
        }
    });

    // Close menu on escape key
    document.addEventListener('keydown', function(e) {
        if (e.key === 'Escape') {
            hamburgerMenu.classList.remove('active');
            mobileMenu.classList.remove('active');
        }
    });
}