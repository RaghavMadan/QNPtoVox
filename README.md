# QNPtoVox Pipeline

A comprehensive pipeline for processing Quantitative Neuropathology (QNP) data from Halo annotations and registering them to MNI space.

## Overview

The QNPtoVox pipeline processes brain imaging data and Halo annotations to extract quantitative neuropathology values. The pipeline consists of five main automated steps, followed by a separate ANTs-based MNI transformation step:

**Main Pipeline Steps:**
1. **Upsampling and Reorientation**: Convert MGZ files to NIfTI format and upsample to 0.5mm resolution
2. **Brain Slicing**: Generate 0.5mm slices from anterior to posterior using R script
3. **Coordinate Extraction**: Extract coordinates and AT8 values from Halo annotation files
4. **Coordinate Transformation**: Transform coordinates using manual input and create 3D blocks
5. **Kernel Application**: Apply 2mm Gaussian kernel smoothing to aligned blocks

**Separate ANTs Transformation Step:**
6. **MNI Registration**: Register native brain to MNI 2009b and transform QNP masks to MNI space using ANTs (Advanced Normalization Tools)

> **Note**: The ANTs MNI transformation is **not** part of the automated pipeline script. It must be run separately using the instructions in [ANTs_MNI_Transformation.md](ANTs_MNI_Transformation.md). See the [ANTs Transformation Section](#ants-mni-transformation) below for details.

## Directory Structure

```
QNPtoVox/
├── config/
│   ├── pipeline_config.txt      # Main configuration file
│   ├── manual_coordinates.txt    # Manual coordinate inputs for transformation
│   └── subject_list.txt          # List of subjects to process (optional)
├── scripts/
│   ├── run_qnp_pipeline.py       # Main pipeline script
│   ├── pipeline_utils.py        # Utility functions
│   ├── pipeline_steps.py         # Step implementations
│   └── virtualmeatslicerNative.R # R script for brain slicing
├── Input/
│   ├── exvivo_transformed/       # MGZ files for each subject
│   │   └── XXXX/                 # Subject-specific folder (e.g., 6966X/)
│   │       ├── 001.mgz           # Main brain image
│   │       └── aseg.mgz          # Segmentation (optional)
│   ├── Halo_extract/
│   │   ├── Annotations/          # Halo annotation files
│   │   │   └── XXXX-XX-AT8.annotations  # Annotation file naming: SUBJECT-SLICE-MARKER.annotations
│   │   └── Summary Analysis(in).csv    # AT8 summary data
│   └── mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz  # MNI template (optional, can be in config)
├── output/                       # Pipeline outputs
│   └── XXXX/                    # Subject-specific outputs
│       ├── XXXX_upsampled/      # Upsampled NIfTI files
│       ├── XXXX_slices/         # Brain slice images
│       ├── XXXX_coordinates/    # Extracted coordinates and AT8 values
│       ├── XXXX_transformation/ # Transformed coordinates and 3D blocks
│       ├── XXXX_kernel/         # Smoothed kernel blocks
│       └── XXXX_mni_registration/ # MNI registration outputs
├── logs/                         # Pipeline logs
├── requirements.txt              # Python dependencies
├── setup.sh                     # Setup script
└── README.md                    # This file
```

## Installation

### Prerequisites

1. **Python 3.7+** with pip
2. **R** with required packages:
   - `RNifti`
   - `png`
3. **FreeSurfer** (for MGZ to NIfTI conversion)
4. **ANTs (Advanced Normalization Tools)** (for MNI registration - see [ANTs Installation](#ants-mni-transformation) below)
5. **NIfTI tools** (optional, for additional processing)

### Setup

1. **Clone or navigate to the QNPtoVox directory**:
   ```bash
   cd QNPtoVox
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Install R packages** (if not already installed):
   ```r
   install.packages(c("RNifti", "png"))
   ```

4. **Verify FreeSurfer installation**:
   ```bash
   which mri_convert
   ```
   If not found, set up FreeSurfer:
   ```bash
   export FREESURFER_HOME=/path/to/freesurfer
   source $FREESURFER_HOME/SetUpFreeSurfer.sh
   ```

5. **Run setup script**:
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

6. **Install ANTs (for MNI transformation step)**:
   > **Note**: ANTs is only required for the separate MNI transformation step, not for the main pipeline.
   
   See [ANTs_MNI_Transformation.md](ANTs_MNI_Transformation.md) for detailed ANTs installation instructions. Quick installation:
   ```bash
   # macOS (Homebrew)
   brew install ants
   
   # Verify installation
   which antsRegistrationSyN.sh
   ```

## Configuration

The pipeline uses a simple text configuration file (`config/pipeline_config.txt`) with key=value pairs. Key configuration sections include:

### Pipeline Information
- Pipeline name, version, and description

### Directory Structure
- Input and output directory paths
- Step-specific output suffixes

### Subject Configuration
- List of subjects to process
- MGZ filename pattern
- Special annotation suffixes for specific subjects

### Step Parameters
- **Upsampling**: Target resolution, interpolation method
- **Slicing**: Slice thickness, output format, R script path
- **Coordinate Extraction**: XML parser, coordinate scaling
- **Transformation**: Block size, manual coordinate file
- **Kernel**: Smoothing parameters
- **MNI Registration**: Template path, registration parameters

## Usage

### Basic Usage

Run the complete pipeline for all subjects:
```bash
python3 scripts/run_qnp_pipeline.py
```

### Advanced Usage

**Run specific steps** (main pipeline only):
```bash
python3 scripts/run_qnp_pipeline.py --steps upsample slice extract transform kernel
```

> **Note**: The `mni` step is **not** available in the automated pipeline. MNI transformation must be performed separately using ANTs. See [ANTs MNI Transformation](#ants-mni-transformation) section below.

**Process specific subjects**:
```bash
python3 scripts/run_qnp_pipeline.py --subjects 6966 7038 --steps upsample
```

**Debug mode with dry run**:
```bash
python3 scripts/run_qnp_pipeline.py --steps upsample --dry-run --verbose --subjects 6966
```

**Force overwrite existing files**:
```bash
python3 scripts/run_qnp_pipeline.py --steps upsample --force
```

**Show pipeline status**:
```bash
python3 scripts/run_qnp_pipeline.py --info
```

**Validate inputs only**:
```bash
python3 scripts/run_qnp_pipeline.py --validate-only
```

### Command Line Options

- `--steps`: Specify pipeline steps to run (`upsample`, `slice`, `extract`, `transform`, `kernel`)
  - **Note**: `mni` step is not available in the automated pipeline. Use the separate [ANTs transformation guide](ANTs_MNI_Transformation.md) for MNI registration.
- `--subjects`: List of subject IDs to process
- `--force`: Overwrite existing output files
- `--dry-run`: Show what would be done without executing
- `--verbose`: Enable verbose logging
- `--config`: Path to configuration file
- `--info`: Show pipeline status and exit
- `--validate-only`: Only validate inputs and exit

## Input File Naming Conventions

### MGZ Files
- **Location**: `Input/exvivo_transformed/XXXXX/`
- **Naming Pattern**: `001.mgz` (standard name)
- **Example**: `Input/exvivo_transformed/6966X/001.mgz`
- **Subject Folder**: Subject ID + suffix (default: `X`), e.g., `6966X/`, `7038X/`

### Halo Annotation Files
- **Location**: `Input/Halo_extract/Annotations/`
- **Naming Pattern**: `{SUBJECT_ID}-{SLICE_ID}-{MARKER}.annotations`
- **Examples**:
  - `6966-A1-AT8.annotations` (standard)
  - `7038-A2-AT8.annotations` (special case, defined in config)
  - `7101-A2-AT8.annotations` (special case, defined in config)
- **Format**: XML format containing coordinate annotations

### Summary Analysis CSV
- **Location**: `Input/Halo_extract/Summary Analysis(in).csv`
- **Format**: CSV with columns including:
  - `Image Tag`: Subject identifier (e.g., `6966-A1-AT8`)
  - `Analysis Region`: Tile identifier (e.g., `Tile 1`, `Tile 2`)
  - `% AT8 Positive Tissue`: AT8 percentage value

### MNI Template
- **Location**: `Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz` (or path in config)
- **Name**: `mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz`
- **Description**: MNI ICBM 152 2009b nonlinear symmetric high-resolution template

## Output File Naming Conventions

### Upsampled Files
- **Location**: `output/XXXX/XXXX_upsampled/`
- **Naming Pattern**: `{SUBJECT_ID}_001_up_re.nii.gz`
- **Example**: `output/6966/6966_upsampled/6966_001_up_re.nii.gz`
- **Description**: Upsampled and reoriented NIfTI file at 0.5mm resolution

### Brain Slices
- **Location**: `output/XXXX/XXXX_slices/`
- **Naming Pattern**: `{SUBJECT_ID}_s.{SLICE_NUMBER:03d}.png`
- **Examples**:
  - `6966_s.001.png`
  - `6966_s.002.png`
  - `6966_s.278.png`
- **Description**: PNG images of brain slices from anterior to posterior

### Coordinate Files
- **Location**: `output/XXXX/XXXX_coordinates/`
- **Files**:
  - `{SUBJECT_ID}_tile_coord.csv`: Raw coordinate data from XML
  - `{SUBJECT_ID}_AT8.csv`: AT8 values extracted from summary CSV
  - `{SUBJECT_ID}_tile_proc.csv`: Processed coordinates combined with AT8 values
- **Example**: `output/6966/6966_coordinates/6966_tile_coord.csv`

### Transformation Files
- **Location**: `output/XXXX/XXXX_transformation/`
- **Files**:
  - `{SUBJECT_ID}_QNP_AT8_mask_block.nii.gz`: 3D block mask in native space
  - `{SUBJECT_ID}_QNP_AT8_mask_block_aligned.nii.gz`: Manually aligned block mask
  - `{SUBJECT_ID}_transformed_coordinates.csv`: Transformed coordinate data
- **Example**: `output/6966/6966_transformation/6966_QNP_AT8_mask_block.nii.gz`

### Kernel Files
- **Location**: `output/XXXX/XXXX_kernel/`
- **Naming Pattern**: `{SUBJECT_ID}_QNP_AT8_smoothed_sig2.nii.gz`
- **Example**: `output/6966/6966_kernel/6966_QNP_AT8_smoothed_sig2.nii.gz`
- **Description**: 2mm Gaussian kernel smoothed QNP mask

### MNI Registration Files
- **Location**: `output/XXXX/XXXX_mni_registration/`
- **Files**:
  - `{SUBJECT_ID}_0GenericAffine.mat`: Affine transformation matrix
  - `{SUBJECT_ID}_1Warp.nii.gz`: Warp field transformation
  - `{SUBJECT_ID}_QNP_mask_ToMNI.nii.gz`: Final QNP mask in MNI space
  - `{SUBJECT_ID}_Warped.nii.gz`: Registered native brain in MNI space (optional)
- **Example**: `output/6966/6966_mni_registration/6966_QNP_mask_ToMNI.nii.gz`

## Pipeline Steps

### Step 1: Upsampling and Reorientation

**Purpose**: Convert MGZ files to NIfTI format and upsample to 0.5mm resolution

**Input**: `Input/exvivo_transformed/XXXXX/001.mgz`
**Output**: `output/XXXX/XXXX_upsampled/XXXX_001_up_re.nii.gz`

**Process**:
1. Convert MGZ to NIfTI using FreeSurfer's `mri_convert`
2. Upsample to 0.5mm resolution using nibabel
3. Save as compressed NIfTI file

**Note**: This step may require manual intervention using FSLeyes for proper reorientation.

### Step 2: Brain Slicing

**Purpose**: Generate 0.5mm slices from anterior to posterior

**Input**: `output/XXXX/XXXX_upsampled/XXXX_001_up_re.nii.gz`
**Output**: `output/XXXX/XXXX_slices/XXXX_s.XXX.png`

**Process**:
1. Load upsampled NIfTI file using R
2. Find brain boundaries (anterior to posterior)
3. Generate slices at 0.5mm intervals
4. Normalize and rotate images
5. Save as PNG files

### Step 3: Coordinate Extraction

**Purpose**: Extract coordinates and AT8 values from Halo annotations

**Input**: 
- `Input/Halo_extract/Annotations/XXXX-XX-AT8.annotations`
- `Input/Halo_extract/Summary Analysis(in).csv`

**Output**: 
- `output/XXXX/XXXX_coordinates/XXXX_tile_coord.csv`
- `output/XXXX/XXXX_coordinates/XXXX_AT8.csv`
- `output/XXXX/XXXX_coordinates/XXXX_tile_proc.csv`

**Process**:
1. Parse XML annotation files
2. Extract coordinate data (X, Y positions)
3. Extract AT8 values from summary CSV
4. Combine coordinates and AT8 values
5. Save as CSV files

### Step 4: Coordinate Transformation

**Purpose**: Transform coordinates using manual input and create 3D blocks

**Input**: 
- `output/XXXX/XXXX_coordinates/XXXX_tile_proc.csv`
- `output/XXXX/XXXX_upsampled/XXXX_001_up_re.nii.gz`
- `config/manual_coordinates.txt`

**Output**: 
- `output/XXXX/XXXX_transformation/XXXX_QNP_AT8_mask_block.nii.gz`
- `output/XXXX/XXXX_transformation/XXXX_transformed_coordinates.csv`

**Process**:
1. Load manual coordinates from config file
2. Transform tile coordinates using offsets
3. Create 3D blocks around transformed coordinates
4. Assign AT8 values to blocks
5. Save as NIfTI mask and CSV

**Note**: Manual alignment may be required. See `manual_alignment_instructions.md` if available.

### Step 5: Kernel Application

**Purpose**: Apply 2mm Gaussian kernel smoothing to aligned blocks

**Input**: `output/XXXX/XXXX_transformation/XXXX_QNP_AT8_mask_block_aligned.nii.gz`
**Output**: `output/XXXX/XXXX_kernel/XXXX_QNP_AT8_smoothed_sig2.nii.gz`

**Process**:
1. Load aligned block mask
2. Apply 2mm Gaussian kernel (sigma=2)
3. Apply threshold mask (>0.01)
4. Save smoothed mask

**Note**: Requires manual alignment step to create `*_block_aligned.nii.gz` file.

### Step 6: MNI Registration

**Purpose**: Register native brain to MNI 2009b and transform QNP masks

**Input**: 
- `output/XXXX/XXXX_upsampled/XXXX_001_up_re.nii.gz`
- `output/XXXX/XXXX_kernel/XXXX_QNP_AT8_smoothed_sig2.nii.gz`
- `Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz`

**Output**: 
- `output/XXXX/XXXX_mni_registration/XXXX_0GenericAffine.mat`
- `output/XXXX/XXXX_mni_registration/XXXX_1Warp.nii.gz`
- `output/XXXX/XXXX_mni_registration/XXXX_QNP_mask_ToMNI.nii.gz`

**Process**:
1. Register native brain to MNI using ANTs SyN registration
2. Generate transformation matrices and warp fields
3. Apply transforms to kernel block mask
4. Save final QNP mask in MNI space

## Manual Configuration

### Manual Coordinates File

The `config/manual_coordinates.txt` file contains manually identified coordinates for each subject:

```
# Format: subject_id=X_offset,Y_slice,Z_offset
6966=200,278,200
7038=117,289,200
7051=200,277,200
...
```

- **X_offset**: X coordinate offset in native space
- **Y_slice**: Fixed slice number (manually identified)
- **Z_offset**: Z coordinate offset in native space

### Subject-Specific Annotation Suffixes

Some subjects may have different annotation file naming. Configure in `config/pipeline_config.txt`:

```
special_annotation_7038=-A2-AT8.annotations
special_annotation_7101=-A2-AT8.annotations
```

## Logging

The pipeline creates detailed logs in the `logs/` directory:

- `pipeline.log`: Main pipeline log with timestamps and levels
- Console output: Real-time progress and error messages

## Error Handling

The pipeline includes comprehensive error handling:

- **Input validation**: Checks for required input files
- **Step validation**: Verifies prerequisites for each step
- **Graceful failures**: Continues processing other subjects if one fails
- **Detailed logging**: Records all errors and warnings

## ANTs MNI Transformation

The MNI transformation step is **separate** from the main automated pipeline and requires ANTs (Advanced Normalization Tools).

### Quick Reference

- **Full Guide**: See [ANTs_MNI_Transformation.md](ANTs_MNI_Transformation.md) for complete instructions
- **When to Run**: After completing all main pipeline steps (`upsample`, `slice`, `extract`, `transform`, `kernel`)
- **Installation**: See [ANTs Installation Guide](ANTs_MNI_Transformation.md#ants-installation) in the transformation guide
- **Requirements**: 
  - ANTs installed and in PATH
  - MNI template: `Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz`
  - Completed kernel step outputs

### Quick Start

```bash
# 1. Install ANTs (if not already installed)
brew install ants  # macOS
# OR see ANTs_MNI_Transformation.md for other methods

# 2. Verify installation
which antsRegistrationSyN.sh

# 3. Follow instructions in ANTs_MNI_Transformation.md
# The guide includes:
#   - Step-by-step transformation commands
#   - Batch processing scripts
#   - Troubleshooting guide
```

**For detailed instructions, see [ANTs_MNI_Transformation.md](ANTs_MNI_Transformation.md)**

## Troubleshooting

### Common Issues

1. **FreeSurfer not found**:
   ```bash
   export FREESURFER_HOME=/path/to/freesurfer
   source $FREESURFER_HOME/SetUpFreeSurfer.sh
   ```

2. **R packages missing**:
   ```r
   install.packages(c("RNifti", "png"))
   ```

3. **ANTs not found** (for MNI transformation):
   - See [ANTs_MNI_Transformation.md](ANTs_MNI_Transformation.md) for installation instructions
   - Quick install: `brew install ants` (macOS)
   - Verify: `which antsRegistrationSyN.sh`

4. **Permission errors**:
   ```bash
   chmod +x scripts/run_qnp_pipeline.py
   chmod +x setup.sh
   ```

5. **Memory issues**: Reduce `max_workers` in configuration

6. **MNI template not found**:
   - Download from [ICBM 152 Nonlinear Symmetric 2009b](https://www.bic.mni.mcgill.ca/ServicesAtlases/ICBM152NLin2009)
   - Place in `Input/` directory
   - Required for ANTs transformation step

### Debug Mode

Use verbose logging and dry-run mode for debugging:
```bash
python3 scripts/run_qnp_pipeline.py --verbose --dry-run --steps upsample --subjects 6966
```

## Output Structure Summary

For each subject (e.g., 6966), the pipeline creates:

```
output/6966/
├── 6966_upsampled/
│   └── 6966_001_up_re.nii.gz          # Upsampled NIfTI file
├── 6966_slices/
│   ├── 6966_s.001.png                  # Brain slice images
│   ├── 6966_s.002.png
│   └── ...
├── 6966_coordinates/
│   ├── 6966_tile_coord.csv             # Raw coordinates
│   ├── 6966_AT8.csv                    # AT8 values
│   └── 6966_tile_proc.csv              # Processed coordinates + AT8
├── 6966_transformation/
│   ├── 6966_QNP_AT8_mask_block.nii.gz  # 3D block mask
│   ├── 6966_QNP_AT8_mask_block_aligned.nii.gz  # Aligned mask (manual)
│   └── 6966_transformed_coordinates.csv # Transformed coordinates
├── 6966_kernel/
│   └── 6966_QNP_AT8_smoothed_sig2.nii.gz  # Smoothed mask
└── 6966_mni_registration/
    ├── 6966_0GenericAffine.mat         # Affine transform
    ├── 6966_1Warp.nii.gz               # Warp field
    └── 6966_QNP_mask_ToMNI.nii.gz     # Final MNI space mask
```

## Contributing

When modifying the pipeline:

1. Update configuration files for new parameters
2. Add new steps to `pipeline_steps.py`
3. Update documentation and README
4. Test with a subset of subjects first
5. Maintain backward compatibility

## License

This pipeline is part of the NeuroPathPredict project and is intended for open source availability.

## Contact

For questions or issues, please refer to the main project documentation or create an issue in the repository.

