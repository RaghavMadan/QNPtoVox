#!/bin/bash
# Batch ANTs Transformation Script for QNPtoVox Pipeline
# This script processes multiple subjects through ANTs MNI transformation
# 
# Usage:
#   chmod +x scripts/batch_ants_transformation.sh
#   ./scripts/batch_ants_transformation.sh

# List of subjects (update as needed)
SUBJECTS=(6966 7038 7051 7064 7067 7101 7124 7144 7157 7297)

# Paths
MNI_TEMPLATE="Input/mni_icbm152_t1_nlin_sym_09b_hires_stripped.nii.gz"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if ANTs is installed
if ! command -v antsRegistrationSyN.sh &> /dev/null; then
    echo -e "${RED}ERROR: ANTs is not installed or not in PATH${NC}"
    echo "Please install ANTs first. See ANTs_MNI_Transformation.md for instructions."
    exit 1
fi

# Check if MNI template exists
if [ ! -f "${MNI_TEMPLATE}" ]; then
    echo -e "${RED}ERROR: MNI template not found: ${MNI_TEMPLATE}${NC}"
    echo "Please download the MNI template and place it in the Input/ directory."
    echo "See ANTs_MNI_Transformation.md for download instructions."
    exit 1
fi

echo "=========================================="
echo "ANTs MNI Transformation Batch Processing"
echo "=========================================="
echo "Subjects: ${SUBJECTS[@]}"
echo "MNI Template: ${MNI_TEMPLATE}"
echo ""

# Process each subject
SUCCESS_COUNT=0
FAIL_COUNT=0

for SUBJECT_ID in "${SUBJECTS[@]}"; do
    echo -e "${YELLOW}Processing subject: ${SUBJECT_ID}${NC}"
    
    # Define paths
    NATIVE_BRAIN="output/${SUBJECT_ID}/${SUBJECT_ID}_upsampled/${SUBJECT_ID}_001_up_re.nii.gz"
    KERNEL_BLOCK="output/${SUBJECT_ID}/${SUBJECT_ID}_kernel/${SUBJECT_ID}_QNP_AT8_smoothed_sig2.nii.gz"
    OUTPUT_DIR="output/${SUBJECT_ID}/${SUBJECT_ID}_mni_registration"
    OUTPUT_PREFIX="${OUTPUT_DIR}/${SUBJECT_ID}"
    
    # Create output directory
    mkdir -p "${OUTPUT_DIR}"
    
    # Check if input files exist
    if [ ! -f "${NATIVE_BRAIN}" ]; then
        echo -e "  ${RED}ERROR: Native brain not found: ${NATIVE_BRAIN}${NC}"
        echo -e "  ${YELLOW}Skipping subject ${SUBJECT_ID}${NC}"
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    
    if [ ! -f "${KERNEL_BLOCK}" ]; then
        echo -e "  ${RED}ERROR: Kernel block not found: ${KERNEL_BLOCK}${NC}"
        echo -e "  ${YELLOW}Skipping subject ${SUBJECT_ID}${NC}"
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    
    # Step 1: Register to MNI
    echo "  Step 1: Registering native brain to MNI..."
    if antsRegistrationSyN.sh \
        -d 3 \
        -f "${MNI_TEMPLATE}" \
        -m "${NATIVE_BRAIN}" \
        -o "${OUTPUT_PREFIX}" \
        -n 4 > "${OUTPUT_DIR}/registration.log" 2>&1; then
        echo -e "  ${GREEN}✓ Registration completed${NC}"
    else
        echo -e "  ${RED}✗ Registration failed for ${SUBJECT_ID}${NC}"
        echo -e "  ${YELLOW}Check log: ${OUTPUT_DIR}/registration.log${NC}"
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    
    # Check if transformation files were created
    if [ ! -f "${OUTPUT_PREFIX}_0GenericAffine.mat" ] || [ ! -f "${OUTPUT_PREFIX}_1Warp.nii.gz" ]; then
        echo -e "  ${RED}✗ Transformation files not created${NC}"
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    
    # Step 2: Transform kernel block
    echo "  Step 2: Transforming kernel block to MNI space..."
    if antsApplyTransforms \
        -d 3 \
        -i "${KERNEL_BLOCK}" \
        -r "${MNI_TEMPLATE}" \
        -o "${OUTPUT_PREFIX}_QNP_mask_ToMNI.nii.gz" \
        -n NearestNeighbor \
        -t "${OUTPUT_PREFIX}_1Warp.nii.gz" \
        -t "${OUTPUT_PREFIX}_0GenericAffine.mat" > "${OUTPUT_DIR}/transformation.log" 2>&1; then
        echo -e "  ${GREEN}✓ Transformation completed${NC}"
    else
        echo -e "  ${RED}✗ Transformation failed for ${SUBJECT_ID}${NC}"
        echo -e "  ${YELLOW}Check log: ${OUTPUT_DIR}/transformation.log${NC}"
        ((FAIL_COUNT++))
        echo ""
        continue
    fi
    
    # Verify output file
    if [ -f "${OUTPUT_PREFIX}_QNP_mask_ToMNI.nii.gz" ]; then
        FILE_SIZE=$(du -h "${OUTPUT_PREFIX}_QNP_mask_ToMNI.nii.gz" | cut -f1)
        echo -e "  ${GREEN}SUCCESS: ${SUBJECT_ID} transformation completed${NC}"
        echo -e "  Output file size: ${FILE_SIZE}"
        ((SUCCESS_COUNT++))
    else
        echo -e "  ${RED}ERROR: Output file not created for ${SUBJECT_ID}${NC}"
        ((FAIL_COUNT++))
    fi
    
    echo ""
done

# Summary
echo "=========================================="
echo "Batch Processing Summary"
echo "=========================================="
echo -e "${GREEN}Successful: ${SUCCESS_COUNT}${NC}"
echo -e "${RED}Failed: ${FAIL_COUNT}${NC}"
echo "Total: ${#SUBJECTS[@]}"
echo ""

if [ ${FAIL_COUNT} -eq 0 ]; then
    echo -e "${GREEN}All subjects processed successfully!${NC}"
    exit 0
else
    echo -e "${YELLOW}Some subjects failed. Check logs for details.${NC}"
    exit 1
fi

