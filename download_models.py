#!/usr/bin/env python3
"""
Download and prepare InsightFace models for face analysis.
This script ensures models are properly extracted and initialized.
"""
import os
import zipfile

print("Downloading and preparing InsightFace antelopev2 model...")

# Set the model root directory
model_root = '.insightface'
os.makedirs(model_root, exist_ok=True)

# Download using the model_zoo which handles download and extraction properly
try:
    from insightface.model_zoo import model_zoo
    
    # This will download and extract the models
    print("Downloading models via model_zoo...")
    model_zoo.get_model('antelopev2', root=model_root)
    
    # Verify extraction by checking for model files
    model_path = os.path.join(model_root, 'models', 'antelopev2')
    if os.path.exists(model_path):
        files = os.listdir(model_path)
        print(f"✓ Models extracted successfully. Found {len(files)} files:")
        for f in files:
            print(f"  - {f}")
    
    print("✓ InsightFace models downloaded and prepared successfully!")
    
except Exception as e:
    print(f"✗ Error with model_zoo: {e}")
    
    # Fallback: manual download and extraction
    print("Attempting manual download and extraction...")
    try:
        from insightface.utils import download_onnx
        
        # Manually trigger download
        download_onnx('antelopev2', root=model_root)
        
        # Check if zip file exists and extract it manually
        zip_path = os.path.join(model_root, 'models', 'antelopev2.zip')
        extract_path = os.path.join(model_root, 'models', 'antelopev2')
        
        if os.path.exists(zip_path) and not os.path.exists(extract_path):
            print(f"Extracting {zip_path}...")
            os.makedirs(extract_path, exist_ok=True)
            with zipfile.ZipFile(zip_path, 'r') as zip_ref:
                zip_ref.extractall(extract_path)
            print("✓ Models extracted successfully!")
        
        print("✓ Models ready for use!")
        
    except Exception as e2:
        print(f"✗ Fallback also failed: {e2}")
        print("Models will be downloaded on first use.")
