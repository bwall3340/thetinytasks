# Logo Vectorizer Tool

A Python tool to remove white backgrounds from logos and convert them to vector SVG format using precise color-based white detection and contour vectorization.

## Features

- **Precise White Removal**: Targets only white pixels (RGB 245+), preserving light yellow and other colors
- **Hard Edge Preservation**: No blur effects - maintains crisp, sharp logo edges
- **Vectorization**: Converts raster images to scalable SVG vector format
- **Three Interfaces**: Command-line tool, Gradio web GUI, and custom HTML interface
- **Multiple Formats**: Supports PNG, JPG, JPEG, BMP, TIFF input formats
- **Customizable**: Adjustable contour simplification for different detail levels

## Installation

1. **Clone or download** this repository
2. **Install Python 3.7+** if not already installed
3. **Run the setup script**:
   ```bash
   python setup.py
   ```

This will automatically install all required dependencies.

## Usage

### Web Interfaces (Recommended)

**Gradio Interface:**
```bash
python logo_vectorizer_gui.py
```

**Custom HTML Interface:**
```bash
python run_html.py
```

Both interfaces allow you to:
- Upload your logo image
- Adjust vectorization settings
- Preview the results
- Download PNG and SVG files

### Command Line Interface

Process a single image:
```bash
python logo_vectorizer.py path/to/your/logo.png
```

With custom output directory:
```bash
python logo_vectorizer.py path/to/your/logo.png --output-dir ./output/
```

With custom simplification factor:
```bash
python logo_vectorizer.py path/to/your/logo.png --epsilon 0.01
```

## Output Files

For each processed image, the tool generates:

1. **`*_no_bg.png`** - Image with background removed
2. **`*_binary.png`** - Binary preprocessing preview
3. **`*_vector.svg`** - Final vectorized SVG file

## Parameters

- **Epsilon Factor** (0.005 - 0.1): Controls contour simplification
  - Lower values = more detail, larger files
  - Higher values = simplified shapes, smaller files
  - Default: 0.02

## Tips for Best Results

1. **White Backgrounds**: Tool specifically removes white pixels (RGB 245+)
2. **Light Yellow Safe**: Light yellow, cream, and other near-white colors are preserved
3. **High Contrast**: Logos with strong contrast work better
4. **Sharp Edges**: No blur applied - perfect for logos with hard edges
5. **File Size**: Start with epsilon 0.02, adjust based on results

## Dependencies

- `opencv-python==4.9.0.80` - Image processing and contour detection
- `Pillow==10.2.0` - Image handling and manipulation
- `numpy==1.26.4` - Numerical operations
- `scikit-image==0.22.0` - Image processing algorithms
- `click==8.1.7` - CLI interface
- `gradio==4.16.0` - Web GUI
- `Flask==3.0.0` - HTML web interface

## Troubleshooting

### Installation Issues
- Ensure Python 3.7+ is installed
- Try upgrading pip: `python -m pip install --upgrade pip`
- On Windows, you may need Visual Studio Build Tools for some packages

### Processing Issues
- **Poor vectorization**: Try adjusting the epsilon factor
- **Missing details**: Lower the epsilon value
- **Too many contours**: Increase the epsilon value
- **Background not removed**: Ensure the image has sufficient contrast

## Example Workflow

1. Start with a logo image (PNG/JPG)
2. Run through the tool to remove background
3. Adjust epsilon factor if needed for optimal detail/simplicity balance
4. Use the generated SVG file in your projects

The SVG files are scalable and perfect for web use, print materials, or further editing in vector graphics software.