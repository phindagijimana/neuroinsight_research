#!/usr/bin/env python3
"""
Test script to directly test MRI processing pipeline
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from pipeline.processors import MRIProcessor

def test_processing():
    # Create a test job ID
    job_id = uuid4()
    print(f"Testing with job ID: {job_id}")

    # Create processor
    def progress_callback(progress, step):
        print(f"Progress: {progress}% - {step}")

    processor = MRIProcessor(job_id, progress_callback=progress_callback)
    print("Processor created successfully")

    # Test with the nibabel test file
    test_file = "/tmp/test_anatomical.nii"

    print(f"Starting processing with file: {test_file}")
    result = processor.process(test_file)
    print(f"Processing completed: {result}")

if __name__ == "__main__":
    test_processing()
"""
Test script to directly test MRI processing pipeline
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from pipeline.processors import MRIProcessor

def test_processing():
    # Create a test job ID
    job_id = uuid4()
    print(f"Testing with job ID: {job_id}")

    # Create processor
    def progress_callback(progress, step):
        print(f"Progress: {progress}% - {step}")

    processor = MRIProcessor(job_id, progress_callback=progress_callback)
    print("Processor created successfully")

    # Test with the nibabel test file
    test_file = "/tmp/test_anatomical.nii"

    print(f"Starting processing with file: {test_file}")
    result = processor.process(test_file)
    print(f"Processing completed: {result}")

if __name__ == "__main__":
    test_processing()
"""
Test script to directly test MRI processing pipeline
"""

import sys
sys.path.insert(0, '.')

from uuid import uuid4
from pipeline.processors import MRIProcessor

def test_processing():
    # Create a test job ID
    job_id = uuid4()
    print(f"Testing with job ID: {job_id}")

    # Create processor
    def progress_callback(progress, step):
        print(f"Progress: {progress}% - {step}")

    processor = MRIProcessor(job_id, progress_callback=progress_callback)
    print("Processor created successfully")

    # Test with the nibabel test file
    test_file = "/tmp/test_anatomical.nii"

    print(f"Starting processing with file: {test_file}")
    result = processor.process(test_file)
    print(f"Processing completed: {result}")

if __name__ == "__main__":
    test_processing()







