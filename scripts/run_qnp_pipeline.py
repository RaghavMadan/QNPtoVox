#!/usr/bin/env python3
"""
QNPtoVox Pipeline - Main Script
Combined QNPtoVox and QNPtoMNI Pipeline
NeuroPathPredict - QNP to MNI Registration Pipeline

A comprehensive pipeline that processes QNP (Quantitative Neuropathology) data from Halo annotations
and registers them to MNI space. This pipeline combines the QNPtoVox and QNPtoMNI workflows.

Usage Examples:
    # Run full pipeline
    python3 scripts/run_qnp_pipeline.py
    
    # Run specific steps
    python3 scripts/run_qnp_pipeline.py --steps upsample slice extract transform kernel mni
    
    # Process specific subjects
    python3 scripts/run_qnp_pipeline.py --subjects 6966 7038 --steps slice
    
    # Debug mode with dry run
    python3 scripts/run_qnp_pipeline.py --steps slice --dry-run --verbose --subjects 6966
    
    # Force overwrite existing files
    python3 scripts/run_qnp_pipeline.py --steps slice --force
    
    # Show status and validate inputs
    python3 scripts/run_qnp_pipeline.py --info
    python3 scripts/run_qnp_pipeline.py --validate-only
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from typing import List, Optional

# Import pipeline components
from pipeline_utils import PipelineConfig, create_output_directories, check_existing_outputs
from pipeline_steps import (
    UpsamplingStep, SlicingStep, CoordinateExtractionStep, 
    CoordinateTransformationStep, KernelApplicationStep, MNIRegistrationStep
)


class QNPPipeline:
    """Combined QNPtoVox and QNPtoMNI Pipeline"""
    
    def __init__(self, config_path: str = "config/pipeline_config.txt", verbose: bool = False):
        """Initialize pipeline
        
        Args:
            config_path: Path to configuration file
            verbose: Enable verbose logging
        """
        self.config_path = config_path
        self.config = PipelineConfig(config_path)
        self.logger = self._setup_logging(verbose)
        
    def _setup_logging(self, verbose: bool = False) -> logging.Logger:
        """Setup logging"""
        level = logging.DEBUG if verbose else logging.INFO
        logging.basicConfig(
            level=level,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        return logging.getLogger(__name__)
    
    def show_info(self):
        """Show pipeline status information"""
        print("QNPtoVox Pipeline Status")
        print("=" * 50)
        print(f"Configuration: {self.config_path}")
        print(f"Pipeline Version: {self.config.get('pipeline_version', 'Unknown')}")
        print(f"Subjects: {len(self.config.get_subjects())}")
        print(f"Subject List: {', '.join(map(str, self.config.get_subjects()))}")
        
        # Show status of each step
        subjects = self.config.get_subjects()
        print("\nStep Status:")
        
        steps = [
            ('1. Upsampling', '_upsampled'),
            ('2. Brain Slicing', '_slices'),
            ('3. Coordinate Extraction', '_coordinates'),
            ('4. Coordinate Transformation', '_transformation'),
            ('5. Kernel Application', '_kernel'),
            ('6. MNI Registration (Separate)', '_mni_registration'),
        ]
        
        for step_name, suffix in steps:
            completed = 0
            for subject in subjects:
                step_dir = self.config.get_subject_step_dir(subject, suffix)
                if step_dir.exists() and any(step_dir.iterdir()):
                    completed += 1
            print(f"  {step_name}: {completed}/{len(subjects)} subjects")
    
    def validate_inputs(self, subjects: Optional[List[int]] = None) -> bool:
        """Validate input files for specified subjects"""
        subjects = subjects or self.config.get_subjects()
        self.logger.info(f"Validating inputs for {len(subjects)} subjects")
        
        missing_files = []
        
        for subject in subjects:
            # Check MGZ files
            mgz_path = self.config.get_input_mgz_path(subject)
            if not mgz_path.exists():
                missing_files.append(str(mgz_path))
            
            # Check annotation files
            annotation_path = self.config.get_input_annotation_path(subject)
            if not annotation_path.exists():
                missing_files.append(str(annotation_path))
        
        if missing_files:
            self.logger.error(f"Missing {len(missing_files)} input files:")
            for file in missing_files[:10]:
                self.logger.error(f"  - {file}")
            if len(missing_files) > 10:
                self.logger.error(f"  ... and {len(missing_files) - 10} more")
            return False
        
        self.logger.info("All input files validated successfully")
        return True
    
    def run_pipeline(self, subjects: Optional[List[int]] = None, steps: Optional[List[str]] = None,
                    force: bool = False, dry_run: bool = False) -> bool:
        """Run the complete pipeline or specified steps
        
        Pipeline Steps:
        1. upsample: Convert MGZ to NIfTI and upsample to 0.5mm
        2. slice: Generate brain slices from anterior to posterior
        3. extract: Extract coordinates and AT8 values from Halo annotations
        4. transform: Transform coordinates and create 3D blocks
        5. kernel: Apply 2mm Gaussian kernel smoothing
        
        Note: MNI registration (mni step) is NOT part of the automated pipeline.
        It must be run separately using ANTs. See ANTs_MNI_Transformation.md for details.
        """
        
        # Default to all subjects and all steps (excluding 'mni' which is separate)
        subjects = subjects or self.config.get_subjects()
        # Note: 'mni' step is not included by default as it requires separate ANTs execution
        steps = steps or ['upsample', 'slice', 'extract', 'transform', 'kernel']
        
        # Warn if user tries to use 'mni' step
        if 'mni' in steps:
            self.logger.warning("⚠️  The 'mni' step is not fully automated in this pipeline.")
            self.logger.warning("⚠️  Please use the separate ANTs transformation guide: ANTs_MNI_Transformation.md")
            self.logger.warning("⚠️  The MNI step will attempt to run but may require manual ANTs setup.")
        
        self.logger.info("Starting QNPtoVox Pipeline")
        self.logger.info(f"Subjects: {', '.join(map(str, subjects))}")
        self.logger.info(f"Steps: {', '.join(steps)}")
        
        if dry_run:
            self.logger.info("=== DRY RUN MODE ===")
        
        # Create output directories
        create_output_directories(self.config, subjects, self.logger)
        
        # Step mapping
        step_functions = {
            'upsample': UpsamplingStep(self.config),
            'slice': SlicingStep(self.config),
            'extract': CoordinateExtractionStep(self.config),
            'transform': CoordinateTransformationStep(self.config),
            'kernel': KernelApplicationStep(self.config),
            'mni': MNIRegistrationStep(self.config),
        }
        
        # Execute steps
        overall_success = True
        for step in steps:
            self.logger.info("")
            self.logger.info(f"=== STEP: {step.upper()} ===")
            
            if step not in step_functions:
                self.logger.error(f"Unknown step: {step}")
                overall_success = False
                break
            
            try:
                success = step_functions[step].execute(subjects, force, dry_run, self.logger)
                if not success:
                    self.logger.error(f"Step '{step}' failed")
                    overall_success = False
                    break
            except Exception as e:
                self.logger.error(f"Step '{step}' encountered an error: {e}")
                overall_success = False
                break
        
        # Final summary
        self.logger.info("")
        if overall_success:
            self.logger.info("Pipeline completed successfully!")
        else:
            self.logger.error("Pipeline failed. Check logs for details.")
        
        return overall_success


def main():
    """Main function with comprehensive flag support"""
    parser = argparse.ArgumentParser(
        description='Combined QNPtoVox and QNPtoMNI Pipeline',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    
    # Main operation modes
    parser.add_argument('--info', action='store_true',
                       help='Show pipeline status and exit')
    parser.add_argument('--validate-only', action='store_true',
                       help='Only validate inputs and exit')
    
    # Processing control
    parser.add_argument('--steps', nargs='+',
                       choices=['upsample', 'slice', 'extract', 'transform', 'kernel', 'mni'],
                       help='Pipeline steps to run (default: all steps except mni). '
                            'Note: mni step requires separate ANTs setup - see ANTs_MNI_Transformation.md')
    parser.add_argument('--subjects', nargs='+', type=int,
                       help='Subject IDs to process (default: all subjects from config)')
    
    # Execution flags
    parser.add_argument('--force', action='store_true',
                       help='Overwrite existing output files')
    parser.add_argument('--dry-run', action='store_true',
                       help='Show what would be done without executing')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Enable verbose logging')
    
    # Configuration
    parser.add_argument('--config', default='config/pipeline_config.txt',
                       help='Path to configuration file')
    
    args = parser.parse_args()
    
    # Initialize pipeline
    try:
        pipeline = QNPPipeline(config_path=args.config, verbose=args.verbose)
    except Exception as e:
        print(f"Error initializing pipeline: {e}")
        sys.exit(1)
    
    # Handle info mode
    if args.info:
        pipeline.show_info()
        return
    
    # Handle validate-only mode
    if args.validate_only:
        valid = pipeline.validate_inputs(args.subjects)
        if valid:
            print("All input files validated successfully")
            sys.exit(0)
        else:
            print("Input validation failed")
            sys.exit(1)
    
    # Run pipeline
    try:
        success = pipeline.run_pipeline(
            subjects=args.subjects,
            steps=args.steps,
            force=args.force,
            dry_run=args.dry_run
        )
        sys.exit(0 if success else 1)
        
    except KeyboardInterrupt:
        print("\nPipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"Pipeline failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

