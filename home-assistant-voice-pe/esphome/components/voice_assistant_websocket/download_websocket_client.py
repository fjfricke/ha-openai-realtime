#!/usr/bin/env python3
"""
Download ESP WebSocket Client files from espressif/esp-protocols repository.

This script downloads the required files and places them in the correct locations.
"""

import os
import sys
import tempfile
import shutil
import zipfile
import urllib.request
from pathlib import Path

REPO_URL = "https://github.com/espressif/esp-protocols"
BRANCH = "master"
COMPONENT_NAME = "esp_websocket_client"


def download_file(url: str, dest: Path) -> None:
    """Download a file from URL to destination."""
    print(f"Downloading {url}...")
    urllib.request.urlretrieve(url, dest)


def extract_zip(zip_path: Path, extract_to: Path) -> None:
    """Extract a zip file to a directory."""
    print(f"Extracting {zip_path.name}...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(extract_to)


def main():
    """Main function to download and copy ESP WebSocket Client files."""
    script_dir = Path(__file__).parent.resolve()
    component_dir = script_dir
    
    print(f"Downloading ESP WebSocket Client from {REPO_URL}...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        zip_path = temp_path / "esp-protocols.zip"
        extract_path = temp_path / "extracted"
        
        # Download repository
        zip_url = f"{REPO_URL}/archive/refs/heads/{BRANCH}.zip"
        download_file(zip_url, zip_path)
        
        # Extract
        extract_zip(zip_path, extract_path)
        
        # Find the extracted directory (name varies with commit hash)
        extracted_dirs = list(extract_path.glob("esp-protocols-*"))
        if not extracted_dirs:
            print("Error: Could not find extracted directory", file=sys.stderr)
            sys.exit(1)
        
        source_dir = extracted_dirs[0] / "components" / COMPONENT_NAME
        
        if not source_dir.exists():
            print(f"Error: Component directory not found: {source_dir}", file=sys.stderr)
            sys.exit(1)
        
        # Copy files
        print("Copying files to component directory...")
        
        # Main source and header files (directly in component directory)
        shutil.copy2(source_dir / "esp_websocket_client.c", component_dir)
        shutil.copy2(source_dir / "include" / "esp_websocket_client.h", component_dir)
        
        # CMakeLists.txt and LICENSE (in esp_websocket_client subdirectory)
        esp_ws_dir = component_dir / "esp_websocket_client"
        esp_ws_dir.mkdir(exist_ok=True)
        shutil.copy2(source_dir / "CMakeLists.txt", esp_ws_dir)
        shutil.copy2(source_dir / "LICENSE", esp_ws_dir)
    
    print("✅ ESP WebSocket Client files downloaded successfully!")
    print()
    print("Files updated:")
    print("  - esp_websocket_client.c")
    print("  - esp_websocket_client.h")
    print("  - esp_websocket_client/CMakeLists.txt")
    print("  - esp_websocket_client/LICENSE")


if __name__ == "__main__":
    main()

