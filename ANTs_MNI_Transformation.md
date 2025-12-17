# ANTs MNI Transformation Guide

This guide provides instructions for transforming QNP masks from native space to MNI space using ANTs (Advanced Normalization Tools). This is a **separate step** that should be performed after completing the main QNPtoVox pipeline steps (upsample, slice, extract, transform, kernel).

## Overview

The ANTs MNI transformation step performs two main operations:

1. **Register native brain to MNI 2009b space** - Creates transformation matrices
2. **Transform QNP kernel masks to MNI space** - Applies transformations to the smoothed QNP masks

## Prerequisites

### 1. ANTs Installation

ANTs must be installed before running the transformation. See [ANTs Installation Guide](#ants-installation) below for detailed installation instructions.

**Quick Check:**
```bash
which antsRegistrationSyN.sh
which antsApplyTransforms
```

If these commands return paths, ANTs is installed. If not, proceed with installation.

### 2. Required Files

Before running the transformation, ensure you have completed the main pipeline steps and have:

- **Native brain image**: `output/XXXX/XXXX_upsampled/XXXX_001_up_re.nii.gz`
- **Kernel block mask**: `output/XXXX/XXXX_kernel/XXXX_QNP_AT8_smoothed_sig2.nii.gz`
- **MNI template**: `Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz`

**Note**: The MNI template can be downloaded from [ICBM 152 Nonlinear Symmetric 2009b](https://www.bic.mni.mcgill.ca/ServicesAtlases/ICBM152NLin2009) if not already present.

## ANTs Installation

### Method 1: Homebrew (Recommended for macOS)

```bash
# Install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install ANTs
brew install ants

# Verify installation
antsRegistrationSyN.sh --version
antsApplyTransforms --version
```

### Method 2: Manual Installation from Source

```bash
# Install prerequisites
xcode-select --install  # Xcode Command Line Tools
brew install cmake git

# Create installation directory
mkdir ~/ants_installation
cd ~/ants_installation

# Clone ANTs repository
git clone https://github.com/ANTsX/ANTs.git

# Create build and install directories
mkdir build install

# Configure and build
cd build
cmake \
    -DCMAKE_INSTALL_PREFIX=../install \
    -DBUILD_SHARED_LIBS=OFF \
    -DUSE_VTK=OFF \
    -DBUILD_TESTING=OFF \
    ../ANTs

# Build (takes 30-60 minutes)
make -j4

# Install
cd ANTS-build
make install

# Add to PATH (add to ~/.zshrc or ~/.bash_profile)
export PATH=$PATH:~/ants_installation/install/bin
source ~/.zshrc  # or source ~/.bash_profile
```

### Method 3: Using Project Installation Script

```bash
# Navigate to reference directory
cd ../V1/QNPtoMNI/Native_MNI_registration

# Run installation script
chmod +x installANTs.sh
./installANTs.sh

# Add to PATH
export PATH=$PATH:$(pwd)/install/bin
```

### Verification

After installation, verify ANTs is working:

```bash
# Check if tools are available
which antsRegistrationSyN.sh
which antsApplyTransforms

# Test with help command
antsRegistrationSyN.sh --help
```

## Step-by-Step Transformation Process

### Step 1: Prepare Input Files

Ensure you have the following structure:

```
output/
└── XXXX/                              # Subject ID (e.g., 6966)
    ├── XXXX_upsampled/
    │   └── XXXX_001_up_re.nii.gz      # Native brain (required)
    └── XXXX_kernel/
        └── XXXX_QNP_AT8_smoothed_sig2.nii.gz  # Kernel mask (required)
```

### Step 2: Create Output Directory

```bash
# Navigate to QNPtoVox directory
cd /path/to/QNPtoVox

# Create MNI registration output directory for each subject
mkdir -p output/XXXX/XXXX_mni_registration
```

### Step 3: Register Native Brain to MNI

This step creates the transformation matrices needed to transform images to MNI space.

```bash
# Set variables (replace XXXX with subject ID)
SUBJECT_ID=6966
NATIVE_BRAIN="output/${SUBJECT_ID}/${SUBJECT_ID}_upsampled/${SUBJECT_ID}_001_up_re.nii.gz"
MNI_TEMPLATE="Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz"
OUTPUT_PREFIX="output/${SUBJECT_ID}/${SUBJECT_ID}_mni_registration/${SUBJECT_ID}"

# Run ANTs registration
antsRegistrationSyN.sh \
    -d 3 \
    -f "${MNI_TEMPLATE}" \
    -m "${NATIVE_BRAIN}" \
    -o "${OUTPUT_PREFIX}" \
    -n 4
```

**Parameters:**
- `-d 3`: 3D registration
- `-f`: Fixed image (MNI template)
- `-m`: Moving image (native brain)
- `-o`: Output prefix
- `-n 4`: Number of CPU cores to use

**Expected Output Files:**
- `${SUBJECT_ID}_0GenericAffine.mat` - Affine transformation matrix
- `${SUBJECT_ID}_1Warp.nii.gz` - Warp field
- `${SUBJECT_ID}_1InverseWarp.nii.gz` - Inverse warp field
- `${SUBJECT_ID}_Warped.nii.gz` - Registered native brain in MNI space

**Processing Time:** 10-30 minutes per subject (depends on image size and system resources)

### Step 4: Transform Kernel Block to MNI Space

Apply the transformation matrices to the kernel block mask.

```bash
# Set variables
SUBJECT_ID=6966
KERNEL_BLOCK="output/${SUBJECT_ID}/${SUBJECT_ID}_kernel/${SUBJECT_ID}_QNP_AT8_smoothed_sig2.nii.gz"
MNI_TEMPLATE="Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz"
OUTPUT_DIR="output/${SUBJECT_ID}/${SUBJECT_ID}_mni_registration"
WARP_TRANSFORM="${OUTPUT_DIR}/${SUBJECT_ID}_1Warp.nii.gz"
AFFINE_TRANSFORM="${OUTPUT_DIR}/${SUBJECT_ID}_0GenericAffine.mat"
OUTPUT_TRANSFORMED="${OUTPUT_DIR}/${SUBJECT_ID}_QNP_mask_ToMNI.nii.gz"

# Apply transforms
antsApplyTransforms \
    -d 3 \
    -i "${KERNEL_BLOCK}" \
    -r "${MNI_TEMPLATE}" \
    -o "${OUTPUT_TRANSFORMED}" \
    -n NearestNeighbor \
    -t "${WARP_TRANSFORM}" \
    -t "${AFFINE_TRANSFORM}"
```

**Parameters:**
- `-d 3`: 3D transformation
- `-i`: Input image (kernel block)
- `-r`: Reference image (MNI template)
- `-o`: Output image
- `-n NearestNeighbor`: Interpolation method (preserves mask values)
- `-t`: Transformation files (warp first, then affine)

**Expected Output File:**
- `${SUBJECT_ID}_QNP_mask_ToMNI.nii.gz` - QNP mask in MNI space

**Processing Time:** 1-5 minutes per subject

## Batch Processing Script

A batch processing script is provided for processing multiple subjects automatically:

The batch script (`scripts/batch_ants_transformation.sh`) is included in the pipeline and handles:
- Automatic subject processing
- Input file validation
- Error handling and logging
- Progress reporting
- Summary statistics

**Usage:**
```bash
# Make script executable (if not already)
chmod +x scripts/batch_ants_transformation.sh

# Run batch processing
./scripts/batch_ants_transformation.sh
```

The script will:
1. Check for ANTs installation
2. Verify MNI template exists
3. Process each subject in sequence
4. Create log files for each step
5. Provide a summary of successful and failed subjects

**Customizing the Subject List:**
Edit the `SUBJECTS` array in `scripts/batch_ants_transformation.sh` to process specific subjects.

## Expected Output Structure

After completing the transformation, you should have:

```
output/
└── XXXX/
    └── XXXX_mni_registration/
        ├── XXXX_0GenericAffine.mat          # Affine transformation
        ├── XXXX_1Warp.nii.gz                 # Warp field
        ├── XXXX_1InverseWarp.nii.gz          # Inverse warp (optional)
        ├── XXXX_Warped.nii.gz                # Registered brain (optional)
        └── XXXX_QNP_mask_ToMNI.nii.gz        # Final QNP mask in MNI space
```

## Verification

### Check Output Files

```bash
# Verify transformation files exist
ls -lh output/XXXX/XXXX_mni_registration/

# Check file sizes (should be non-zero)
du -h output/XXXX/XXXX_mni_registration/*.nii.gz
```

### Visual Inspection

Use a neuroimaging viewer to check the transformed masks:

```bash
# Using FSLeyes (if available)
fsleyes Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz \
        output/XXXX/XXXX_mni_registration/XXXX_QNP_mask_ToMNI.nii.gz

# Using FreeView (FreeSurfer)
freeview Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz \
         output/XXXX/XXXX_mni_registration/XXXX_QNP_mask_ToMNI.nii.gz
```

## Troubleshooting

### Common Issues

#### 1. ANTs Commands Not Found

**Error:** `antsRegistrationSyN.sh: command not found`

**Solution:**
```bash
# Check if ANTs is in PATH
which antsRegistrationSyN.sh

# If not found, add to PATH
export PATH=$PATH:/path/to/ants/bin

# Or use full path
/path/to/ants/bin/antsRegistrationSyN.sh [options]
```

#### 2. Memory Issues

**Error:** Out of memory during registration

**Solution:**
- Close other applications
- Reduce number of CPU cores: `-n 2` instead of `-n 4`
- Check available RAM: `top` or `Activity Monitor`
- Ensure at least 8GB RAM available

#### 3. File Not Found Errors

**Error:** `Cannot open file: ...`

**Solution:**
- Verify file paths are correct
- Check file permissions: `ls -l output/XXXX/...`
- Ensure files exist: `test -f path/to/file && echo "exists"`

#### 4. Registration Fails

**Error:** Registration returns non-zero exit code

**Solution:**
- Check input image quality and orientation
- Verify MNI template is correct version
- Check image dimensions match expected format
- Review ANTs log files for detailed error messages

#### 5. Transformation Produces Empty/Zero Images

**Error:** Output image is all zeros

**Solution:**
- Verify kernel block mask has non-zero values
- Check transformation order (warp before affine)
- Ensure reference image (MNI template) is correct
- Verify transformation files were created correctly

### Getting Help

#### ANTs Documentation
- [ANTs GitHub Repository](https://github.com/ANTsX/ANTs)
- [ANTs Wiki](https://github.com/ANTsX/ANTs/wiki)
- [ANTs User Guide](https://github.com/ANTsX/ANTs/wiki/User-Guide)
- [ANTs Registration Examples](https://github.com/ANTsX/ANTs/wiki/Registration-examples)

#### System Requirements
- **macOS**: 10.14 or later
- **Linux**: Most modern distributions
- **RAM**: At least 8GB (16GB recommended)
- **Disk Space**: At least 5GB free space
- **CPU**: Multi-core processor recommended

## Integration with Main Pipeline

### When to Run ANTs Transformation

The ANTs transformation should be run **after** completing these main pipeline steps:

1. ✅ Upsampling (`upsample`)
2. ✅ Brain Slicing (`slice`)
3. ✅ Coordinate Extraction (`extract`)
4. ✅ Coordinate Transformation (`transform`)
5. ✅ Kernel Application (`kernel`)
6. 🔄 **ANTs MNI Transformation** ← **Run this step separately**

### Workflow

```bash
# Step 1: Run main pipeline (without MNI step)
python3 scripts/run_qnp_pipeline.py --steps upsample slice extract transform kernel

# Step 2: Run ANTs transformation (separate step)
# Use the batch script or individual commands from this guide
./batch_ants_transformation.sh
```

## Notes

- **Processing Time**: 
  - Registration: 10-30 minutes per subject
  - Transformation: 1-5 minutes per subject
  - Total: ~15-35 minutes per subject

- **Memory Usage**: ANTs registration is memory-intensive (8-16GB recommended)

- **Parallel Processing**: Can process multiple subjects in parallel if system resources allow

- **Output Files**: Transformation files can be reused for additional images from the same subject

## Support

If you encounter issues:

1. Check ANTs installation: `antsRegistrationSyN.sh --version`
2. Verify input files exist and are readable
3. Check system resources (memory, disk space)
4. Review ANTs log files for detailed error messages
5. Consult ANTs documentation and GitHub issues

