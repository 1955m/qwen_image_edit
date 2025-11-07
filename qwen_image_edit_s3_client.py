#!/usr/bin/env python3
"""
Qwen Image Edit API client with S3 upload functionality
Complete client that uploads files using RunPod Network Volume S3 and calls Qwen Image Edit API

Image Role Convention (Official Qwen Documentation):
- image_path (Image 1) = DONOR: Source of elements to transfer (person, outfit, object, etc.)
- image_path_2 (Image 2) = CANVAS: Base image that receives edits (background remains)

Example: To swap a person from photo A into the scene from photo B:
    - image_path = photo A (person to extract)
    - image_path_2 = photo B (scene/background to keep)
    - prompt = "Replace the person in the second image with the person in the first image..."
"""

import os
import requests
import json
import boto3
from botocore.client import Config
import time
import base64
from typing import Optional, Dict, Any, List
from pathlib import Path
import logging

# Logging configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class QwenImageEditS3Client:
    def __init__(
        self,
        runpod_endpoint_id: str,
        runpod_api_key: str,
        s3_endpoint_url: str,
        s3_access_key_id: str,
        s3_secret_access_key: str,
        s3_bucket_name: str,
        s3_region: str = 'eu-ro-1'
    ):
        """
        Initialize Qwen Image Edit S3 client

        Args:
            runpod_endpoint_id: RunPod endpoint ID
            runpod_api_key: RunPod API key
            s3_endpoint_url: S3 endpoint URL
            s3_access_key_id: S3 access key ID
            s3_secret_access_key: S3 secret access key
            s3_bucket_name: S3 bucket name
            s3_region: S3 region
        """
        self.runpod_endpoint_id = runpod_endpoint_id
        self.runpod_api_key = runpod_api_key
        self.runpod_api_endpoint = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/run"
        self.status_url = f"https://api.runpod.ai/v2/{runpod_endpoint_id}/status"

        # S3 configuration
        self.s3_endpoint_url = s3_endpoint_url
        self.s3_access_key_id = s3_access_key_id
        self.s3_secret_access_key = s3_secret_access_key
        self.s3_bucket_name = s3_bucket_name
        self.s3_region = s3_region

        # Initialize S3 client
        self.s3_client = boto3.client(
            's3',
            endpoint_url=s3_endpoint_url,
            aws_access_key_id=s3_access_key_id,
            aws_secret_access_key=s3_secret_access_key,
            region_name=s3_region,
            config=Config(signature_version='s3v4')
        )

        # Initialize HTTP session
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {runpod_api_key}',
            'Content-Type': 'application/json'
        })

        logger.info(f"QwenImageEditS3Client initialized - Endpoint: {runpod_endpoint_id}")

    def upload_to_s3(self, file_path: str, s3_key: str) -> Optional[str]:
        """
        Upload file to S3

        Args:
            file_path: Local path of file to upload
            s3_key: Key (path) to store in S3

        Returns:
            S3 path or None (on failure)
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"File does not exist: {file_path}")
                return None

            logger.info(f"S3 upload started: {file_path} -> s3://{self.s3_bucket_name}/{s3_key}")

            self.s3_client.upload_file(file_path, self.s3_bucket_name, s3_key)

            s3_path = f"/runpod-volume/{s3_key}"
            logger.info(f"✅ S3 upload successful: {s3_path}")
            return s3_path

        except Exception as e:
            logger.error(f"❌ S3 upload failed: {e}")
            return None

    def submit_job(self, input_data: Dict[str, Any]) -> Optional[str]:
        """
        Submit job to RunPod

        Args:
            input_data: API input data

        Returns:
            Job ID or None (on failure)
        """
        payload = {"input": input_data}

        try:
            logger.info(f"Submitting job to RunPod: {self.runpod_api_endpoint}")
            logger.info(f"Input data: {json.dumps(input_data, indent=2, ensure_ascii=False)}")

            response = self.session.post(self.runpod_api_endpoint, json=payload, timeout=30)
            response.raise_for_status()

            response_data = response.json()
            job_id = response_data.get('id')

            if job_id:
                logger.info(f"✅ Job submission successful! Job ID: {job_id}")
                return job_id
            else:
                logger.error(f"❌ Failed to receive Job ID: {response_data}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"❌ Job submission failed: {e}")
            return None

    def wait_for_completion(self, job_id: str, check_interval: int = 10, max_wait_time: int = 1800) -> Dict[str, Any]:
        """
        Wait for job completion

        Args:
            job_id: Job ID
            check_interval: Status check interval (seconds)
            max_wait_time: Maximum wait time (seconds)

        Returns:
            Job result dictionary
        """
        start_time = time.time()

        while time.time() - start_time < max_wait_time:
            try:
                logger.info(f"⏱️ Checking job status... (Job ID: {job_id})")

                response = self.session.get(f"{self.status_url}/{job_id}", timeout=30)
                response.raise_for_status()

                status_data = response.json()
                status = status_data.get('status')

                if status == 'COMPLETED':
                    logger.info("✅ Job completed!")
                    return {
                        'status': 'COMPLETED',
                        'output': status_data.get('output'),
                        'job_id': job_id
                    }
                elif status == 'FAILED':
                    logger.error("❌ Job failed.")
                    return {
                        'status': 'FAILED',
                        'error': status_data.get('error', 'Unknown error'),
                        'job_id': job_id
                    }
                elif status in ['IN_QUEUE', 'IN_PROGRESS']:
                    logger.info(f"🏃 Job in progress... (status: {status})")
                    time.sleep(check_interval)
                else:
                    logger.warning(f"❓ Unknown status: {status}")
                    return {
                        'status': 'UNKNOWN',
                        'data': status_data,
                        'job_id': job_id
                    }

            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Error checking status: {e}")
                time.sleep(check_interval)

        logger.error(f"❌ Job wait timeout ({max_wait_time} seconds)")
        return {
            'status': 'TIMEOUT',
            'job_id': job_id
        }

    def save_image_result(self, result: Dict[str, Any], output_path: str) -> bool:
        """
        Save image file from job result

        Args:
            result: Job result dictionary
            output_path: File path to save

        Returns:
            Save success status
        """
        try:
            if result.get('status') != 'COMPLETED':
                logger.error(f"Job not completed: {result.get('status')}")
                return False

            output = result.get('output', {})
            image_b64 = output.get('image')

            if not image_b64:
                logger.error("No image data available")
                return False

            # Create directory
            os.makedirs(os.path.dirname(output_path) or '.', exist_ok=True)

            # Remove data URI prefix if present
            if ',' in image_b64:
                image_b64 = image_b64.split(',', 1)[1]

            # Decode and save image
            decoded_image = base64.b64decode(image_b64)

            with open(output_path, 'wb') as f:
                f.write(decoded_image)

            file_size = os.path.getsize(output_path)
            logger.info(f"✅ Image saved successfully: {output_path} ({file_size / 1024:.1f}KB)")
            return True

        except Exception as e:
            logger.error(f"❌ Image save failed: {e}")
            return False

    def edit_single_image(
        self,
        image_path: str,
        prompt: str,
        seed: int = 12345,
        width: int = 1024,
        height: int = 1024,
        steps: int = 40,
        cfg: float = 4.0,
        negative_prompt: str = " ",
        use_lightning: bool = False
    ) -> Dict[str, Any]:
        """
        Edit a single image using Qwen Image Edit

        Args:
            image_path: Image file path to edit
            prompt: Edit description (e.g., "change hair color to blonde, add sunglasses")
            seed: Random seed for generation (default: 12345)
            width: Output width in pixels (default: 1024)
            height: Output height in pixels (default: 1024)
            steps: Number of inference steps (default: 40, use 4 with use_lightning=True)
            cfg: CFG scale / true_cfg_scale (default: 4.0, official recommendation)
            negative_prompt: Negative prompt (default: " " single space, official recommendation)
            use_lightning: Use Lightning mode for faster generation (4 steps)

        Returns:
            Job result dictionary
        """
        # Check file existence
        if not os.path.exists(image_path):
            return {"error": f"Image file does not exist: {image_path}"}

        # Upload image to S3
        timestamp = int(time.time())
        image_s3_key = f"input/qwen/{timestamp}_{os.path.basename(image_path)}"
        image_s3_path = self.upload_to_s3(image_path, image_s3_key)

        if not image_s3_path:
            return {"error": "Image S3 upload failed"}

        # Override steps if Lightning mode enabled
        if use_lightning:
            steps = 4
            logger.info("⚡ Lightning mode enabled: using 4 steps for faster generation")

        # Configure API input data
        input_data = {
            "image_path": image_s3_path,
            "prompt": prompt,
            "seed": seed,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "negative_prompt": negative_prompt
        }

        # Submit job and wait
        job_id = self.submit_job(input_data)
        if not job_id:
            return {"error": "Job submission failed"}

        result = self.wait_for_completion(job_id)
        return result

    def edit_dual_image(
        self,
        image_path: str,
        image_path_2: str,
        prompt: str,
        seed: int = 12345,
        width: int = 1024,
        height: int = 1024,
        steps: int = 40,
        cfg: float = 4.0,
        negative_prompt: str = " ",
        use_lightning: bool = False
    ) -> Dict[str, Any]:
        """
        Edit using two images (person/object swap workflow)

        Image Role Convention (Official Qwen Documentation):
        - image_path (Image 1) = DONOR: Source of elements to transfer
        - image_path_2 (Image 2) = CANVAS: Base image that receives edits

        Example: To swap person from photo A into scene from photo B:
            - image_path = photo A (person to extract)
            - image_path_2 = photo B (scene/background to keep)
            - prompt = "Replace the person in the second image with the person in the first image..."

        Args:
            image_path: First image (DONOR - source of elements)
            image_path_2: Second image (CANVAS - base that receives edits)
            prompt: Edit description explaining the swap/transfer
            seed: Random seed for generation (default: 12345)
            width: Output width in pixels (default: 1024)
            height: Output height in pixels (default: 1024)
            steps: Number of inference steps (default: 40, use 4 with use_lightning=True)
            cfg: CFG scale / true_cfg_scale (default: 4.0, official recommendation)
            negative_prompt: Negative prompt (default: " " single space, official recommendation)
            use_lightning: Use Lightning mode for faster generation (4 steps)

        Returns:
            Job result dictionary
        """
        # Check file existence
        if not os.path.exists(image_path):
            return {"error": f"First image file does not exist: {image_path}"}

        if not os.path.exists(image_path_2):
            return {"error": f"Second image file does not exist: {image_path_2}"}

        # Upload images to S3
        timestamp = int(time.time())

        # Upload first image (donor)
        image_s3_key = f"input/qwen/{timestamp}_donor_{os.path.basename(image_path)}"
        image_s3_path = self.upload_to_s3(image_path, image_s3_key)

        if not image_s3_path:
            return {"error": "First image S3 upload failed"}

        # Upload second image (canvas)
        image_s3_key_2 = f"input/qwen/{timestamp}_canvas_{os.path.basename(image_path_2)}"
        image_s3_path_2 = self.upload_to_s3(image_path_2, image_s3_key_2)

        if not image_s3_path_2:
            return {"error": "Second image S3 upload failed"}

        # Override steps if Lightning mode enabled
        if use_lightning:
            steps = 4
            logger.info("⚡ Lightning mode enabled: using 4 steps for faster generation")

        # Configure API input data
        input_data = {
            "image_path": image_s3_path,
            "image_path_2": image_s3_path_2,
            "prompt": prompt,
            "seed": seed,
            "width": width,
            "height": height,
            "steps": steps,
            "cfg": cfg,
            "negative_prompt": negative_prompt
        }

        # Submit job and wait
        job_id = self.submit_job(input_data)
        if not job_id:
            return {"error": "Job submission failed"}

        result = self.wait_for_completion(job_id)
        return result

    def batch_edit_images(
        self,
        image_folder_path: str,
        output_folder_path: str = "output/qwen_batch",
        valid_image_extensions: tuple = ('.jpg', '.jpeg', '.png', '.bmp'),
        prompt: str = "enhance image quality",
        seed: int = 12345,
        width: int = 1024,
        height: int = 1024,
        steps: int = 40,
        cfg: float = 4.0,
        negative_prompt: str = " ",
        use_lightning: bool = False
    ) -> Dict[str, Any]:
        """
        Batch process image edits from folder

        Args:
            image_folder_path: Folder path containing image files
            output_folder_path: Folder path to save results
            valid_image_extensions: Image file extensions to process
            prompt: Edit description text
            seed: Random seed for generation
            width: Output width in pixels
            height: Output height in pixels
            steps: Number of inference steps
            cfg: CFG scale / true_cfg_scale
            negative_prompt: Negative prompt
            use_lightning: Use Lightning mode for faster generation

        Returns:
            Batch processing result dictionary
        """
        # Check path
        if not os.path.isdir(image_folder_path):
            return {"error": f"Image folder does not exist: {image_folder_path}"}

        # Create output folder
        os.makedirs(output_folder_path, exist_ok=True)

        # Get image file list
        image_files = [
            f for f in os.listdir(image_folder_path)
            if f.lower().endswith(valid_image_extensions)
        ]

        if not image_files:
            return {"error": f"No image files to process: {image_folder_path}"}

        logger.info(f"Batch processing started: {len(image_files)} images")

        results = {
            "total_files": len(image_files),
            "successful": 0,
            "failed": 0,
            "results": []
        }

        # Process each image file
        for i, image_filename in enumerate(image_files):
            logger.info(f"\n==================== Processing started: {image_filename} ====================")

            image_path = os.path.join(image_folder_path, image_filename)

            # Edit image
            result = self.edit_single_image(
                image_path=image_path,
                prompt=prompt,
                seed=seed + i,  # Different seed for each file
                width=width,
                height=height,
                steps=steps,
                cfg=cfg,
                negative_prompt=negative_prompt,
                use_lightning=use_lightning
            )

            if result.get('status') == 'COMPLETED':
                # Save result file
                base_filename = Path(image_filename).stem
                output_filename = os.path.join(output_folder_path, f"edited_{base_filename}.png")

                if self.save_image_result(result, output_filename):
                    logger.info(f"✅ [{image_filename}] Processing completed")
                    results["successful"] += 1
                    results["results"].append({
                        "filename": image_filename,
                        "status": "success",
                        "output_file": output_filename,
                        "job_id": result.get('job_id')
                    })
                else:
                    logger.error(f"[{image_filename}] Result save failed")
                    results["failed"] += 1
                    results["results"].append({
                        "filename": image_filename,
                        "status": "failed",
                        "error": "Result save failed",
                        "job_id": result.get('job_id')
                    })
            else:
                logger.error(f"[{image_filename}] Job failed: {result.get('error', 'Unknown error')}")
                results["failed"] += 1
                results["results"].append({
                    "filename": image_filename,
                    "status": "failed",
                    "error": result.get('error', 'Unknown error'),
                    "job_id": result.get('job_id')
                })

            logger.info(f"==================== Processing completed: {image_filename} ====================")

        logger.info(f"\n🎉 Batch processing completed: {results['successful']}/{results['total_files']} successful")
        return results


def main():
    """Usage example"""

    # Configuration (change to actual values)
    ENDPOINT_ID = "your-endpoint-id"
    RUNPOD_API_KEY = "your-runpod-api-key"

    # S3 configuration
    S3_ENDPOINT_URL = "https://s3api-eu-ro-1.runpod.io/"
    S3_ACCESS_KEY_ID = "your-s3-access-key"
    S3_SECRET_ACCESS_KEY = "your-s3-secret-key"
    S3_BUCKET_NAME = "your-bucket-name"
    S3_REGION = "eu-ro-1"

    # Initialize client
    client = QwenImageEditS3Client(
        runpod_endpoint_id=ENDPOINT_ID,
        runpod_api_key=RUNPOD_API_KEY,
        s3_endpoint_url=S3_ENDPOINT_URL,
        s3_access_key_id=S3_ACCESS_KEY_ID,
        s3_secret_access_key=S3_SECRET_ACCESS_KEY,
        s3_bucket_name=S3_BUCKET_NAME,
        s3_region=S3_REGION
    )

    print("=== Qwen Image Edit S3 Client Usage Example ===\n")

    # Example 1: Single image edit
    print("1. Single image edit")
    result1 = client.edit_single_image(
        image_path="./example_image.jpeg",
        prompt="change hair color to blonde, add sunglasses",
        seed=12345,
        width=1024,
        height=1024,
        steps=40,
        cfg=4.0
    )

    if result1.get('status') == 'COMPLETED':
        client.save_image_result(result1, "./output_single_edit.png")
    else:
        print(f"Error: {result1.get('error')}")

    print("\n" + "-"*50 + "\n")

    # Example 2: Dual image edit (person swap)
    print("2. Dual image edit (person/object swap)")
    print("Note: Image 1 = DONOR (source), Image 2 = CANVAS (base)")
    result2 = client.edit_dual_image(
        image_path="./person_a.jpg",  # DONOR: person to extract
        image_path_2="./scene_b.jpg",  # CANVAS: scene to keep
        prompt="Replace the person in the second image with the person in the first image while keeping the background of the second image the same.",
        seed=12345,
        width=1024,
        height=1024,
        steps=40,
        cfg=4.0
    )

    if result2.get('status') == 'COMPLETED':
        client.save_image_result(result2, "./output_person_swap.png")
    else:
        print(f"Error: {result2.get('error')}")

    print("\n" + "-"*50 + "\n")

    # Example 3: Lightning mode (fast generation)
    print("3. Lightning mode (4 steps, faster generation)")
    result3 = client.edit_single_image(
        image_path="./example_image.jpeg",
        prompt="make it look vintage, add film grain",
        seed=12345,
        width=1024,
        height=1024,
        use_lightning=True  # Automatically sets steps=4
    )

    if result3.get('status') == 'COMPLETED':
        client.save_image_result(result3, "./output_lightning_edit.png")
    else:
        print(f"Error: {result3.get('error')}")

    print("\n=== All examples completed ===")


if __name__ == "__main__":
    main()
