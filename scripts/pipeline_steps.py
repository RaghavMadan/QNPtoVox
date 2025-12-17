"""
Pipeline Steps for QNPtoVox Pipeline
Individual step implementations for the workflow
"""

import os
import sys
import subprocess
import logging
import csv
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Optional
import pandas as pd
import numpy as np
import nibabel as nib
from nibabel import processing

# Import utilities
from pipeline_utils import PipelineConfig, create_output_directories, check_existing_outputs, run_r_script


class BaseStep:
    """Base class for pipeline steps"""
    
    def __init__(self, config: PipelineConfig):
        """Initialize step with configuration
        
        Args:
            config: Pipeline configuration
        """
        self.config = config
    
    def execute(self, subjects: List[int], force: bool = False, dry_run: bool = False, logger: Optional[logging.Logger] = None) -> bool:
        """Execute the step for all subjects
        
        Args:
            subjects: List of subject IDs
            force: Force overwrite existing outputs
            dry_run: Show what would be done without executing
            logger: Logger instance
            
        Returns:
            True if successful, False otherwise
        """
        if logger is None:
            logger = logging.getLogger(__name__)
        
        # Check existing outputs
        if not force:
            existing = check_existing_outputs(self.config, subjects, self.get_step_suffix(), logger)
            if existing:
                subjects = [s for s in subjects if s not in existing]
        
        if not subjects:
            logger.info("No subjects to process")
            return True
        
        # Create output directories
        create_output_directories(self.config, subjects, logger)
        
        # Process subjects
        success_count = 0
        for subject in subjects:
            if self._process_subject(subject, dry_run, logger):
                success_count += 1
        
        logger.info(f"Step completed: {success_count}/{len(subjects)} subjects successful")
        return success_count == len(subjects)
    
    def get_step_suffix(self) -> str:
        """Get the step directory suffix
        
        Returns:
            Step directory suffix
        """
        raise NotImplementedError
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        """Process a single subject
        
        Args:
            subject_id: Subject ID
            dry_run: Show what would be done without executing
            logger: Logger instance
            
        Returns:
            True if successful, False otherwise
        """
        raise NotImplementedError


class UpsamplingStep(BaseStep):
    """Step 1: Manual upsampling and reorientation (requires FSLeyes GUI)"""
    
    def get_step_suffix(self) -> str:
        return "_upsampled"
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        """Check for manually created upsampled files"""
        try:
            # Check for the expected upsampled file
            output_dir = self.config.get_subject_step_dir(subject_id, self.get_step_suffix())
            expected_file = output_dir / f"{subject_id}_001_up_re.nii.gz"
            
            if dry_run:
                logger.info(f"DRY RUN: Would check for {expected_file}")
                return True
            
            if expected_file.exists():
                logger.info(f"Subject {subject_id}: Found upsampled file {expected_file}")
                return True
            else:
                logger.error(f"Subject {subject_id}: Upsampled file not found: {expected_file}")
                logger.error(f"Please follow the manual instructions in: manual_upsampling_instructions.md")
                logger.error(f"Expected file: {expected_file}")
                logger.error(f"After creating the file manually, re-run the pipeline")
                return False
            
        except Exception as e:
            logger.error(f"Subject {subject_id}: Upsampling check failed - {e}")
            return False


class SlicingStep(BaseStep):
    """Step 2: Brain slicing using R script"""
    
    def get_step_suffix(self) -> str:
        return "_slices"
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        """Generate brain slices for a subject using R script"""
        try:
            # Get input and output paths
            upsampled_dir = self.config.get_subject_step_dir(subject_id, '_upsampled')
            output_dir = self.config.get_subject_step_dir(subject_id, self.get_step_suffix())
            
            # Find the upsampled NIfTI file
            input_nii = upsampled_dir / f"{subject_id}_001_up_re.nii.gz"
            
            if dry_run:
                logger.info(f"DRY RUN: Would generate slices for {input_nii} to {output_dir}")
                return True
            
            if not input_nii.exists():
                logger.error(f"Subject {subject_id}: Upsampled NIfTI file not found - {input_nii}")
                logger.error(f"Please run the upsampling step first or create the file manually")
                logger.error(f"See manual_upsampling_instructions.md for details")
                return False
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy the NIfTI file to the expected location for R script
            # The R script expects the file to be in {subject_id}X/{subject_id}_001_up_re.nii.gz
            r_input_dir = Path(f"{subject_id}X")
            r_input_dir.mkdir(exist_ok=True)
            r_input_file = r_input_dir / f"{subject_id}_001_up_re.nii.gz"
            
            # Copy file if it doesn't exist or is different
            if not r_input_file.exists() or not r_input_file.samefile(input_nii):
                import shutil
                shutil.copy2(input_nii, r_input_file)
            
            # Run R script
            r_script_path = "scripts/virtualmeatslicerNative.R"
            
            # Run R script
            success = run_r_script(
                r_script_path,
                [str(subject_id)],
                logger,
                cwd=Path.cwd()
            )
            
            if success:
                # Move generated slices to output directory
                slices_dir = Path(f"{subject_id}_slices")
                if slices_dir.exists():
                    import shutil
                    for slice_file in slices_dir.glob("*.png"):
                        shutil.move(str(slice_file), str(output_dir / slice_file.name))
                    
                    # Remove temporary slices directory
                    slices_dir.rmdir()
                
                # Clean up temporary input directory and file
                try:
                    import shutil
                    if r_input_dir.exists():
                        shutil.rmtree(r_input_dir)
                        logger.debug(f"Subject {subject_id}: Cleaned up temporary directory {r_input_dir}")
                except Exception as e:
                    logger.warning(f"Subject {subject_id}: Failed to clean up temporary directory {r_input_dir}: {e}")
                
                logger.info(f"Subject {subject_id}: Generated slices in {output_dir}")
                return True
            else:
                # Clean up temporary input directory even if R script failed
                try:
                    import shutil
                    if r_input_dir.exists():
                        shutil.rmtree(r_input_dir)
                        logger.debug(f"Subject {subject_id}: Cleaned up temporary directory {r_input_dir} after failure")
                except Exception as e:
                    logger.warning(f"Subject {subject_id}: Failed to clean up temporary directory {r_input_dir}: {e}")
                
                logger.error(f"Subject {subject_id}: R script failed")
                return False
            
        except Exception as e:
            # Clean up temporary input directory in case of exception
            try:
                import shutil
                r_input_dir = Path(f"{subject_id}X")
                if r_input_dir.exists():
                    shutil.rmtree(r_input_dir)
                    logger.debug(f"Subject {subject_id}: Cleaned up temporary directory {r_input_dir} after exception")
            except Exception as cleanup_error:
                logger.warning(f"Subject {subject_id}: Failed to clean up temporary directory {r_input_dir}: {cleanup_error}")
            
            logger.error(f"Subject {subject_id}: Slicing failed - {e}")
            return False


class CoordinateExtractionStep(BaseStep):
    """Step 3: Extract coordinates and AT8 values from Halo annotations"""
    
    def get_step_suffix(self) -> str:
        return "_coordinates"
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        """Extract coordinates and AT8 values for a subject"""
        try:
            # Get input and output paths
            annotation_file = self.config.get_input_annotation_path(subject_id)
            summary_csv_file = Path("Input/Halo_extract/Summary Analysis(in).csv")
            output_dir = self.config.get_subject_step_dir(subject_id, self.get_step_suffix())
            output_dir.mkdir(parents=True, exist_ok=True)
            
            if dry_run:
                logger.info(f"DRY RUN: Would extract coordinates from {annotation_file} to {output_dir}")
                return True
            
            if not annotation_file.exists():
                logger.error(f"Subject {subject_id}: Annotation file not found - {annotation_file}")
                return False
            
            if not summary_csv_file.exists():
                logger.error(f"Subject {subject_id}: Summary CSV file not found - {summary_csv_file}")
                return False
            
            logger.info(f"Subject {subject_id}: Processing {annotation_file}")
            
            # Parse XML and extract coordinates
            coordinates = self._extract_coordinates_from_xml(annotation_file, logger)
            
            if not coordinates:
                logger.error(f"Subject {subject_id}: No coordinates extracted")
                return False
            
            # Extract AT8 values from CSV
            at8_values = self._extract_at8_values_from_csv(summary_csv_file, subject_id, logger)
            
            # Save coordinates to CSV
            coord_output_file = output_dir / f"{subject_id}_tile_coord.csv"
            self._save_coordinates_to_csv(coordinates, coord_output_file)
            
            # Save AT8 values to CSV
            at8_output_file = output_dir / f"{subject_id}_AT8.csv"
            self._create_at8_file(at8_values, at8_output_file)
            
            # Create processed file (combining coordinates and AT8)
            proc_output_file = output_dir / f"{subject_id}_tile_proc.csv"
            self._create_processed_file(coord_output_file, at8_output_file, proc_output_file)
            
            logger.info(f"Subject {subject_id}: Coordinate extraction completed")
            return True
            
        except Exception as e:
            logger.error(f"Subject {subject_id}: Coordinate extraction failed - {e}")
            return False
    
    def _extract_coordinates_from_xml(self, annotation_file: Path, logger: logging.Logger) -> List[dict]:
        """Extract coordinates from XML annotation file"""
        try:
            tree = ET.parse(annotation_file)
            root = tree.getroot()
            
            coordinates = []
            
            for annotation in root.findall(".//Annotation"):
                name = annotation.get("Name")
                
                # Skip Layer 1 annotations
                if name == "Layer 1":
                    continue
                
                # Extract coordinates
                for vertex in annotation.findall(".//V"):
                    x = vertex.get("X")
                    y = vertex.get("Y")
                    
                    coordinates.append({
                        'Name': name,
                        'X': x,
                        'Y': y
                    })
            
            logger.info(f"Extracted {len(coordinates)} coordinates (excluding Layer 1)")
            return coordinates
            
        except Exception as e:
            logger.error(f"Failed to parse XML file {annotation_file}: {e}")
            return []
    
    def _extract_at8_values_from_csv(self, csv_file: Path, subject_id: int, logger: logging.Logger) -> List[dict]:
        """Extract AT8 values from Summary Analysis CSV file"""
        try:
            # Read the CSV file with proper encoding
            df = pd.read_csv(csv_file, encoding='latin-1')
            
            # Filter for the specific subject
            subject_pattern = f"{subject_id}-"
            subject_data = df[df['Image Tag'].str.contains(subject_pattern, na=False)]
            
            at8_values = []
            
            for _, row in subject_data.iterrows():
                analysis_region = row['Analysis Region']
                at8_percentage = row['% AT8 Positive Tissue']
                
                # Only include tile data (skip Layer 1)
                if analysis_region.startswith('Tile'):
                    at8_values.append({
                        'Tile': analysis_region,
                        'AT8_Value': float(at8_percentage)
                    })
            
            logger.info(f"Extracted {len(at8_values)} AT8 values for subject {subject_id}")
            return at8_values
            
        except Exception as e:
            logger.error(f"Failed to extract AT8 values from CSV file {csv_file}: {e}")
            return []
    
    def _save_coordinates_to_csv(self, coordinates: List[dict], output_file: Path):
        """Save coordinates to CSV file"""
        with open(output_file, 'w', newline='') as csvfile:
            if coordinates:
                fieldnames = coordinates[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(coordinates)
    
    def _create_at8_file(self, at8_values: List[dict], output_file: Path):
        """Create AT8 file from extracted values"""
        with open(output_file, 'w', newline='') as csvfile:
            if at8_values:
                fieldnames = at8_values[0].keys()
                writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
                writer.writeheader()
                writer.writerows(at8_values)
            else:
                # If no AT8 values found, create empty file with headers
                writer = csv.DictWriter(csvfile, fieldnames=['Tile', 'AT8_Value'])
                writer.writeheader()
    
    def _create_processed_file(self, coord_file: Path, at8_file: Path, output_file: Path):
        """Create processed file combining coordinates and AT8 values"""
        try:
            # Read coordinates
            df_tiles = pd.read_csv(coord_file)
            
            # Read AT8 values
            df_at8 = pd.read_csv(at8_file)
            
            if len(df_at8) == 0:
                # If no AT8 values, create a simple processed file with just coordinates
                df_tiles['AT8'] = 0  # Default value
                df_tiles.to_csv(output_file, index=False)
                return
            
            # Process according to the reference script logic
            n_i, n_j = df_at8.shape
            tile_coords = np.empty([n_i, 4], dtype=object)
            
            for i in range(n_i):
                y = 5 * i  # Sample every 5th coordinate
                if y < len(df_tiles):
                    tile_coords[i][0] = df_tiles.iloc[y, 0]  # Name
                    tile_coords[i][1] = int(df_tiles.iloc[y, 1]) // 1000  # X coordinate
                    tile_coords[i][2] = int(df_tiles.iloc[y, 2]) // 1000  # Y coordinate (as Z)
                    tile_coords[i][3] = df_at8.iloc[i, 1]  # AT8 value
            
            # Create DataFrame
            df = pd.DataFrame(tile_coords)
            df = df.rename(columns={0: "Tile", 1: "X", 2: "Z", 3: "AT8"})
            
            # Save processed file
            df.to_csv(output_file, index=False)
            
        except Exception as e:
            # If processing fails, just copy the coordinate file
            import shutil
            shutil.copy2(coord_file, output_file)


class CoordinateTransformationStep(BaseStep):
    """Step 4: Transform coordinates using manual input and create 3D blocks"""
    
    def get_step_suffix(self) -> str:
        return "_transformation"
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        """Transform coordinates using manual input and create 3D blocks"""
        try:
            # Get input and output paths
            coord_dir = self.config.get_subject_step_dir(subject_id, '_coordinates')
            upsampled_dir = self.config.get_subject_step_dir(subject_id, '_upsampled')
            output_dir = self.config.get_subject_step_dir(subject_id, self.get_step_suffix())
            
            # Input files
            tile_proc_file = coord_dir / f"{subject_id}_tile_proc.csv"
            upsampled_nii = upsampled_dir / f"{subject_id}_001_up_re.nii.gz"
            manual_coords_file = Path(self.config.get('manual_coordinates_file', 'config/manual_coordinates.txt'))
            
            if dry_run:
                logger.info(f"DRY RUN: Would transform coordinates for {subject_id}")
                return True
            
            if not tile_proc_file.exists():
                logger.error(f"Subject {subject_id}: Processed tile file not found - {tile_proc_file}")
                return False
            
            if not upsampled_nii.exists():
                logger.error(f"Subject {subject_id}: Upsampled NIfTI file not found - {upsampled_nii}")
                return False
            
            if not manual_coords_file.exists():
                logger.error(f"Subject {subject_id}: Manual coordinates file not found - {manual_coords_file}")
                return False
            
            # Load manual coordinates
            manual_coords = self._load_manual_coordinates(manual_coords_file, subject_id, logger)
            if manual_coords is None:
                logger.error(f"Subject {subject_id}: Manual coordinates not found in {manual_coords_file}")
                logger.error(f"Please add coordinates for subject {subject_id} in the format: {subject_id}=X,Y,Z")
                return False
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Transform coordinates and create 3D blocks
            success = self._create_3d_blocks(
                subject_id, tile_proc_file, upsampled_nii, manual_coords, output_dir, logger
            )
            
            if success:
                logger.info(f"Subject {subject_id}: Coordinate transformation completed")
                return True
            else:
                logger.error(f"Subject {subject_id}: Coordinate transformation failed")
                return False
            
        except Exception as e:
            logger.error(f"Subject {subject_id}: Coordinate transformation failed - {e}")
            return False
    
    def _load_manual_coordinates(self, coords_file: Path, subject_id: int, logger: logging.Logger) -> Optional[tuple]:
        """Load manual coordinates for a subject"""
        try:
            with open(coords_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    
                    if '=' in line:
                        subj, coords = line.split('=', 1)
                        subj = subj.strip()
                        if subj == str(subject_id):
                            x, y, z = map(int, coords.strip().split(','))
                            logger.info(f"Subject {subject_id}: Manual coordinates X={x}, Y={y}, Z={z}")
                            return (x, y, z)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to load manual coordinates for subject {subject_id}: {e}")
            return None
    
    def _create_3d_blocks(self, subject_id: int, tile_proc_file: Path, upsampled_nii: Path, 
                          manual_coords: tuple, output_dir: Path, logger: logging.Logger) -> bool:
        """Create 3D blocks using the transformation script logic"""
        try:
            # Load the processed tile data
            df = pd.read_csv(tile_proc_file)
            logger.info(f"Subject {subject_id}: Loaded {len(df)} tile entries")
            
            # Load the upsampled NIfTI image
            img = nib.load(str(upsampled_nii))
            affine = img.affine
            logger.info(f"Subject {subject_id}: Image shape {img.shape}")
            
            # Create an empty mask array
            mask = np.zeros(img.shape)
            
            # Get manual coordinates (offsets)
            x_offset, y_slice, z_offset = manual_coords
            
            # Transform each tile entry
            block_size = self.config.get('block_size', 7)
            
            for i in range(len(df)):
                row = df.iloc[i]
                tile_name = row['Tile']
                original_x = row['X']
                original_z = row['Z']
                at8_value = row['AT8']
                
                # Calculate coordinates in MNI space using offsets
                # X = Original_X + X_offset
                # Y = Fixed slice number (Y_slice)
                # Z = Original_Z + Z_offset
                x = int(original_x) + x_offset
                y = y_slice
                z = int(original_z) + z_offset
                
                # Ensure coordinates are within image bounds
                if (0 <= x < img.shape[0] and 0 <= y < img.shape[1] and 0 <= z < img.shape[2]):
                    # Create a block around the coordinate
                    half_block = block_size // 2
                    for dx in range(-half_block, half_block + 1):
                        for dy in range(-half_block, half_block + 1):
                            for dz in range(-half_block, half_block + 1):
                                nx, ny, nz = x + dx, y + dy, z + dz
                                if (0 <= nx < img.shape[0] and 
                                    0 <= ny < img.shape[1] and 
                                    0 <= nz < img.shape[2]):
                                    mask[nx, ny, nz] = at8_value
                    
                    logger.debug(f"Subject {subject_id}: Placed block for {tile_name} at ({x},{y},{z}) with AT8={at8_value}")
                else:
                    logger.warning(f"Subject {subject_id}: Coordinates ({x},{y},{z}) out of bounds for {tile_name}")
            
            # Save the 3D mask
            output_mask = output_dir / f"{subject_id}_QNP_AT8_mask_block.nii.gz"
            nifti_img = nib.Nifti1Image(mask, affine=affine)
            nib.save(nifti_img, str(output_mask))
            
            # Save transformed coordinates
            output_coords = output_dir / f"{subject_id}_transformed_coordinates.csv"
            transformed_data = []
            for i in range(len(df)):
                row = df.iloc[i]
                original_x = row['X']
                original_z = row['Z']
                x = int(original_x) + x_offset
                y = y_slice
                z = int(original_z) + z_offset
                
                transformed_data.append({
                    'Tile': row['Tile'],
                    'X': x,
                    'Y': y,
                    'Z': z,
                    'AT8': row['AT8']
                })
            
            df_transformed = pd.DataFrame(transformed_data)
            df_transformed.to_csv(output_coords, index=False)
            
            logger.info(f"Subject {subject_id}: Created 3D mask with {len(df)} blocks")
            logger.info(f"Subject {subject_id}: Saved mask to {output_mask}")
            logger.info(f"Subject {subject_id}: Saved transformed coordinates to {output_coords}")
            
            return True
            
        except Exception as e:
            logger.error(f"Subject {subject_id}: Failed to create 3D blocks - {e}")
            return False 





class KernelApplicationStep(BaseStep):
    """Step 5: Apply 2mm Gaussian kernel to aligned blocks"""
    
    def get_step_suffix(self) -> str:
        return "_kernel"
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        try:
            # Input: aligned block from transformation step
            transformation_dir = Path(self.config.get('output_base', 'output')) / subject_id / f"{subject_id}_transformation"
            aligned_block_file = transformation_dir / f"{subject_id}_QNP_AT8_mask_block_aligned.nii.gz"
            
            # Output: smoothed block (save in separate kernel directory)
            output_dir = Path(self.config.get('output_base', 'output')) / subject_id / f"{subject_id}_kernel"
            output_file = output_dir / f"{subject_id}_QNP_AT8_smoothed_sig2.nii.gz"
            
            if dry_run:
                logger.info(f"Subject {subject_id}: Would apply 2mm kernel to {aligned_block_file} -> {output_file}")
                return True
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check if output already exists
            if output_file.exists():
                logger.info(f"Subject {subject_id}: Kernel output already exists - {output_file}")
                return True
            
            # Check if input file exists
            if not aligned_block_file.exists():
                logger.error(f"Subject {subject_id}: Aligned block file not found - {aligned_block_file}")
                logger.error(f"Please run the manual alignment step first")
                logger.error(f"See manual_alignment_instructions.md for details")
                return False
            
            # Apply 2mm Gaussian kernel
            success = self._apply_kernel(aligned_block_file, output_file, logger)
            
            if success:
                logger.info(f"Subject {subject_id}: 2mm kernel applied successfully")
                logger.info(f"Subject {subject_id}: Output saved to {output_file}")
            else:
                logger.error(f"Subject {subject_id}: Kernel application failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Subject {subject_id}: Kernel application failed - {e}")
            return False
    
    def _apply_kernel(self, input_file: Path, output_file: Path, logger: logging.Logger) -> bool:
        """Apply 2mm Gaussian kernel to the aligned block"""
        try:
            from scipy.ndimage import gaussian_filter
            
            # Load the aligned QNP mask
            img = nib.load(str(input_file))
            
            # Get the data array and affine from the image
            data = img.get_fdata()
            logger.debug(f"Data shape: {data.shape}")
            affine = img.affine
            
            # Apply a 2mm Gaussian kernel to the data
            data_smoothed = gaussian_filter(data, sigma=2)
            
            # Create a threshold mask
            mask = (data_smoothed > 0.01).astype(int)
            
            # Apply the mask to the smoothed data
            data_smoothed_masked = data_smoothed * mask
            
            # Create a new Nifti image with the masked smoothed data
            nifti_img_smoothed_masked = nib.Nifti1Image(data_smoothed_masked, affine=affine)
            
            # Save the masked smoothed image
            nib.save(nifti_img_smoothed_masked, str(output_file))
            
            logger.debug(f"Kernel application completed: {output_file}")
            return True
            
        except Exception as e:
            logger.error(f"Kernel application error: {e}")
            return False



class MNIRegistrationStep:
    """Step 6: Register native brain to MNI 2009b and transform kernel blocks"""
    
    def __init__(self, config):
        self.config = config
    
    def execute(self, subjects: List[int], force: bool = False, dry_run: bool = False, logger: Optional[logging.Logger] = None) -> bool:
        """Execute MNI registration for all subjects"""
        if logger is None:
            logger = logging.getLogger(__name__)
        
        success_count = 0
        for subject_id in subjects:
            if self._process_subject(subject_id, dry_run, logger):
                success_count += 1
        
        logger.info(f"{self.__class__.__name__}: {success_count}/{len(subjects)} subjects successful")
        return success_count == len(subjects)
    
    def _process_subject(self, subject_id: int, dry_run: bool, logger: logging.Logger) -> bool:
        try:
            # Input files
            upsampled_dir = Path(self.config.get('output_base', 'output')) / subject_id / f"{subject_id}_upsampled"
            native_brain = upsampled_dir / f"{subject_id}_001_up_re.nii.gz"
            
            kernel_dir = Path(self.config.get('output_base', 'output')) / subject_id / f"{subject_id}_kernel"
            kernel_block = kernel_dir / f"{subject_id}_QNP_AT8_smoothed_sig2.nii.gz"
            
            # MNI template - check config first, then default locations
            mni_template_path = self.config.get('mni_template_path', None)
            if mni_template_path:
                mni_template = Path(mni_template_path)
            else:
                # Try common locations
                mni_template = Path("Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz")
                if not mni_template.exists():
                    mni_template = Path("../V1/Cov_dev/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz")
            
            # Output directory
            output_dir = Path(self.config.get('output_base', 'output')) / subject_id / f"{subject_id}_mni_registration"
            
            if dry_run:
                logger.info(f"Subject {subject_id}: Would register to MNI -> {output_dir}")
                return True
            
            # Create output directory
            output_dir.mkdir(parents=True, exist_ok=True)
            
            # Check input files
            if not native_brain.exists():
                logger.error(f"Subject {subject_id}: Native brain file not found - {native_brain}")
                return False
            
            if not kernel_block.exists():
                logger.error(f"Subject {subject_id}: Kernel block file not found - {kernel_block}")
                return False
            
            if not mni_template.exists():
                logger.error(f"Subject {subject_id}: MNI template not found - {mni_template}")
                return False
            
            # Step 1: Register native brain to MNI
            success = self._register_to_mni(subject_id, native_brain, mni_template, output_dir, logger)
            if not success:
                return False
            
            # Step 2: Transform kernel block to MNI space
            success = self._transform_kernel_to_mni(subject_id, kernel_block, mni_template, output_dir, logger)
            if not success:
                return False
            
            logger.info(f"Subject {subject_id}: MNI registration completed successfully")
            return True
            
        except Exception as e:
            logger.error(f"Subject {subject_id}: MNI registration failed - {e}")
            return False
    
    def _register_to_mni(self, subject_id: int, native_brain: Path, mni_template: Path, output_dir: Path, logger: logging.Logger) -> bool:
        """Register native brain to MNI using ANTs"""
        try:
            # Define output prefix
            output_prefix = output_dir / f"{subject_id}"
            
            # Check if transformation files already exist
            forward_transform = output_dir / f"{subject_id}_0GenericAffine.mat"
            warp_transform = output_dir / f"{subject_id}_1Warp.nii.gz"
            
            if forward_transform.exists() and warp_transform.exists():
                logger.info(f"Subject {subject_id}: Transformation files already exist")
                return True
            
            # Run ANTs registration
            cmd = [
                "antsRegistrationSyN.sh",
                "-d", "3",
                "-f", str(mni_template),
                "-m", str(native_brain),
                "-o", str(output_prefix),
                "-n", "4"
            ]
            
            logger.info(f"Subject {subject_id}: Running ANTs registration...")
            logger.debug(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=output_dir)
            
            if result.returncode == 0:
                logger.info(f"Subject {subject_id}: ANTs registration completed successfully")
                return True
            else:
                logger.error(f"Subject {subject_id}: ANTs registration failed")
                logger.error(f"stdout: {result.stdout}")
                logger.error(f"stderr: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Subject {subject_id}: ANTs registration error - {e}")
            return False
    
    def _transform_kernel_to_mni(self, subject_id: int, kernel_block: Path, mni_template: Path, output_dir: Path, logger: logging.Logger) -> bool:
        """Transform kernel block to MNI space using ANTs transforms"""
        try:
            # Define transformation files
            forward_transform = output_dir / f"{subject_id}_0GenericAffine.mat"
            warp_transform = output_dir / f"{subject_id}_1Warp.nii.gz"
            
            # Define output file
            output_transformed = output_dir / f"{subject_id}_QNP_mask_ToMNI.nii.gz"
            
            # Check if output already exists
            if output_transformed.exists():
                logger.info(f"Subject {subject_id}: Transformed kernel block already exists")
                return True
            
            # Check if transformation files exist
            if not forward_transform.exists():
                logger.error(f"Subject {subject_id}: Forward transform not found - {forward_transform}")
                return False
            
            if not warp_transform.exists():
                logger.error(f"Subject {subject_id}: Warp transform not found - {warp_transform}")
                return False
            
            # Run ANTs transform
            cmd = [
                "antsApplyTransforms",
                "-d", "3",
                "-i", str(kernel_block),
                "-r", str(mni_template),
                "-o", str(output_transformed),
                "-n", "NearestNeighbor",
                "-t", str(warp_transform),
                "-t", str(forward_transform)
            ]
            
            logger.info(f"Subject {subject_id}: Applying ANTs transforms to kernel block...")
            logger.debug(f"Command: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=output_dir)
            
            if result.returncode == 0:
                logger.info(f"Subject {subject_id}: Kernel block transformed to MNI space successfully")
                return True
            else:
                logger.error(f"Subject {subject_id}: ANTs transform failed")
                logger.error(f"stdout: {result.stdout}")
                logger.error(f"stderr: {result.stderr}")
                return False
                
        except Exception as e:
            logger.error(f"Subject {subject_id}: ANTs transform error - {e}")
            return False
