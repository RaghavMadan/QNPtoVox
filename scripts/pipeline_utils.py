"""
Pipeline Utilities for QNPtoVox Pipeline
Configuration handling, logging, and validation functions
"""

import os
import sys
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
import subprocess


class PipelineConfig:
    """Configuration handler for the QNPtoVox pipeline"""
    
    def __init__(self, config_path: str):
        """Initialize configuration from text file
        
        Args:
            config_path: Path to text configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from text file"""
        try:
            config = {}
            with open(self.config_path, 'r') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        continue
                    # Parse key=value pairs
                    if '=' in line:
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip()
                        # Convert common value types
                        if value.lower() in ['true', 'false']:
                            value = value.lower() == 'true'
                        elif value.replace('.', '').isdigit():
                            value = float(value) if '.' in value else int(value)
                        elif ',' in value:
                            value = [item.strip() for item in value.split(',')]
                        config[key] = value
                    else:
                        print(f"Warning: Invalid config line {line_num}: {line}")
            return config
        except Exception as e:
            raise RuntimeError(f"Failed to load configuration from {self.config_path}: {e}")
    
    def get(self, key_path: str, default=None):
        """Get configuration value using dot notation
        
        Args:
            key_path: Configuration key path (e.g., 'pipeline.name')
            default: Default value if key not found
        """
        keys = key_path.split('.')
        value = self.config
        
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        
        return value
    
    def get_subjects(self, subjects: Optional[List[int]] = None) -> List[int]:
        """Get list of subjects to process
        
        Args:
            subjects: Optional list of specific subjects
            
        Returns:
            List of subject IDs
        """
        if subjects is not None:
            return subjects
        subject_list = self.get('subject_list', [])
        if isinstance(subject_list, str):
            return [int(s.strip()) for s in subject_list.split(',')]
        return subject_list
    
    def get_subject_output_dir(self, subject_id: int) -> Path:
        """Get the output directory for a specific subject
        
        Args:
            subject_id: Subject ID
            
        Returns:
            Path to subject output directory
        """
        output_base = self.get('output_base', 'output')
        return Path(output_base) / str(subject_id)
    
    def get_subject_step_dir(self, subject_id: int, step_suffix: str) -> Path:
        """Get the step-specific directory for a subject
        
        Args:
            subject_id: Subject ID
            step_suffix: Step directory suffix
            
        Returns:
            Path to step-specific directory
        """
        subject_dir = self.get_subject_output_dir(subject_id)
        return subject_dir / f"{subject_id}{step_suffix}"
    
    def get_input_mgz_path(self, subject_id: int) -> Path:
        """Get input MGZ file path for a subject
        
        Args:
            subject_id: Subject ID
            
        Returns:
            Path to input MGZ file
        """
        mgz_dir = self.get('input_mgz_images', 'Input/exvivo_transformed')
        mgz_filename = self.get('mgz_filename', '001.mgz')
        subject_suffix = self.get('subject_suffix', 'X')
        
        return Path(mgz_dir) / f"{subject_id}{subject_suffix}" / mgz_filename
    
    def get_input_annotation_path(self, subject_id: int) -> Path:
        """Get input annotation file path for a subject
        
        Args:
            subject_id: Subject ID
            
        Returns:
            Path to input annotation file
        """
        annotation_dir = self.get('input_halo_annotations', 'Input/Halo_extract/Annotations')
        
        # Check for special annotation suffix
        special_key = f'special_annotation_{subject_id}'
        if special_key in self.config:
            annotation_suffix = self.get(special_key)
        else:
            annotation_suffix = self.get('annotation_suffix', '-A1-AT8.annotations')
        
        return Path(annotation_dir) / f"{subject_id}{annotation_suffix}"
    
    def get_annotation_suffix(self, subject_id: int) -> str:
        """Get annotation suffix for a specific subject
        
        Args:
            subject_id: Subject ID
            
        Returns:
            Annotation file suffix
        """
        special_key = f'special_annotation_{subject_id}'
        if special_key in self.config:
            return self.get(special_key)
        return self.get('annotation_suffix', '-A1-AT8.annotations')


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging configuration
    
    Args:
        verbose: Enable verbose logging
        
    Returns:
        Configured logger
    """
    level = logging.DEBUG if verbose else logging.INFO
    
    # Create logs directory
    logs_dir = Path('logs')
    logs_dir.mkdir(exist_ok=True)
    
    # Setup logging
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(logs_dir / 'pipeline.log'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    
    return logging.getLogger('QNPtoVox')


def validate_inputs(config: PipelineConfig, subjects: List[int], logger: logging.Logger) -> bool:
    """Validate input files for all subjects
    
    Args:
        config: Pipeline configuration
        subjects: List of subject IDs
        logger: Logger instance
        
    Returns:
        True if all inputs are valid, False otherwise
    """
    logger.info(f"Validating inputs for {len(subjects)} subjects")
    
    missing_files = []
    
    for subject in subjects:
        # Check MGZ image
        mgz_path = config.get_input_mgz_path(subject)
        if not mgz_path.exists():
            missing_files.append(str(mgz_path))
        
        # Check annotation file
        annotation_path = config.get_input_annotation_path(subject)
        if not annotation_path.exists():
            missing_files.append(str(annotation_path))
    
    if missing_files:
        logger.error(f"Missing {len(missing_files)} input files:")
        for file in missing_files[:10]:  # Show first 10
            logger.error(f"  - {file}")
        if len(missing_files) > 10:
            logger.error(f"  ... and {len(missing_files) - 10} more")
        return False
    
    logger.info("All input files validated successfully")
    return True


def create_output_directories(config: PipelineConfig, subjects: List[int], logger: logging.Logger):
    """Create output directories for subjects
    
    Args:
        config: Pipeline configuration
        subjects: List of subject IDs
        logger: Logger instance
    """
    # Create main output directory
    output_base = config.get('output_base', 'output')
    Path(output_base).mkdir(parents=True, exist_ok=True)
    
    # Create logs directory
    logs_dir = config.get('logs_dir', 'logs')
    Path(logs_dir).mkdir(parents=True, exist_ok=True)
    
    # Create subject directories
    for subject in subjects:
        subject_dir = config.get_subject_output_dir(subject)
        subject_dir.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Created output directories for {len(subjects)} subjects")


def check_existing_outputs(config: PipelineConfig, subjects: List[int], step_suffix: str, logger: logging.Logger) -> List[int]:
    """Check which subjects have existing output for a step
    
    Args:
        config: Pipeline configuration
        subjects: List of subject IDs
        step_suffix: Step directory suffix
        logger: Logger instance
        
    Returns:
        List of subjects with existing outputs
    """
    existing = []
    
    for subject in subjects:
        step_dir = config.get_subject_step_dir(subject, step_suffix)
        if step_dir.exists() and any(step_dir.iterdir()):
            existing.append(subject)
    
    if existing:
        logger.warning(f"Found existing output for {len(existing)} subjects in step {step_suffix}")
    
    return existing


def run_r_script(script_path: str, args: List[str], logger: logging.Logger, cwd: Optional[Path] = None) -> bool:
    """Run an R script with arguments
    
    Args:
        script_path: Path to R script
        args: Arguments to pass to R script
        logger: Logger instance
        cwd: Working directory for R script
        
    Returns:
        True if successful, False otherwise
    """
    try:
        cmd = ['Rscript', script_path] + args
        logger.info(f"Running R script: {' '.join(cmd)}")
        
        result = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.stdout:
            logger.debug(f"R script stdout: {result.stdout}")
        if result.stderr:
            logger.debug(f"R script stderr: {result.stderr}")
        
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"R script failed with return code {e.returncode}")
        if e.stdout:
            logger.error(f"stdout: {e.stdout}")
        if e.stderr:
            logger.error(f"stderr: {e.stderr}")
        return False
    except Exception as e:
        logger.error(f"Failed to run R script: {e}")
        return False 