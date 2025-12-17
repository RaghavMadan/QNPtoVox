#!/bin/bash
# QNPtoVox Pipeline Setup Script
# This script sets up the pipeline environment and makes scripts executable

echo "Setting up QNPtoVox Pipeline..."

# Make scripts executable
chmod +x scripts/run_qnp_pipeline.py

# Create necessary directories
mkdir -p output
mkdir -p logs

# Check if Python dependencies are available
echo "Checking Python dependencies..."
python3 -c "import nibabel, pandas, numpy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "Warning: Some Python dependencies may be missing."
    echo "Run: pip install -r requirements.txt"
else
    echo "Python dependencies check passed."
fi

# Check if R is available
if command -v Rscript &> /dev/null; then
    echo "R is available."
else
    echo "Warning: R is not found. Brain slicing step will fail."
fi

# Check if FreeSurfer is available
if command -v mri_convert &> /dev/null; then
    echo "FreeSurfer is available."
else
    echo "Warning: FreeSurfer not found. Upsampling step will fail."
    echo "Set FREESURFER_HOME and source SetUpFreeSurfer.sh"
fi

# Check if required R packages are installed
if command -v Rscript &> /dev/null; then
    Rscript -e "library(RNifti); library(png)" 2>/dev/null
    if [ $? -eq 0 ]; then
        echo "Required R packages are available."
    else
        echo "Warning: Required R packages (RNifti, png) may be missing."
        echo "Run: R -e \"install.packages(c('RNifti', 'png'))\""
    fi
fi

echo ""
echo "Setup complete!"
echo ""
echo "To run the pipeline:"
echo "  python3 scripts/run_qnp_pipeline.py --info"
echo ""
echo "To validate inputs:"
echo "  python3 scripts/run_qnp_pipeline.py --validate-only"
echo ""
echo "To run the full pipeline:"
echo "  python3 scripts/run_qnp_pipeline.py" 