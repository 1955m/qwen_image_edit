# Qwen Image Edit for RunPod Serverless
[한국어 README 보기](README_kr.md)

This project is a template designed to easily deploy and use an image editing workflow (Qwen Image Edit via ComfyUI) in the RunPod Serverless environment.

[![Runpod](https://api.runpod.io/badge/wlsdml1114/qwen_image_edit)](https://console.runpod.io/hub/wlsdml1114/qwen_image_edit)

The template performs prompt-guided image editing using ComfyUI workflows. It supports one or two input images and accepts inputs as path, URL, or Base64.

## 🎨 Engui Studio Integration

[![EnguiStudio](https://raw.githubusercontent.com/wlsdml1114/Engui_Studio/main/assets/banner.png)](https://github.com/wlsdml1114/Engui_Studio)

This Qwen Image Edit template is primarily designed for **Engui Studio**, a comprehensive AI model management platform. While it can be used via API, Engui Studio provides enhanced features and broader model support.

**Engui Studio Benefits:**
- **Expanded Model Support**: Access to a wide variety of AI models beyond what's available through API
- **Enhanced User Interface**: Intuitive workflow management and model selection
- **Advanced Features**: Additional tools and capabilities for AI model deployment
- **Seamless Integration**: Optimized for Engui Studio's ecosystem

> **Note**: While this template works perfectly with API calls, Engui Studio users will have access to additional models and features that are planned for future releases.

## ✨ Key Features

*   **Prompt-Guided Image Editing**: Edit images based on a text prompt using Qwen-Image-Edit-2509 model.
*   **One or Two Input Images**: Automatically selects single- or dual-image workflow.
*   **Flexible Inputs**: Provide images via file path, URL, or Base64 string.
*   **Customizable Parameters**: Official Qwen parameters (seed, width, height, steps, cfg, negative_prompt).
*   **Lightning Mode**: Fast generation using Qwen-Image-Lightning-4steps (4 steps instead of 40).
*   **ComfyUI Integration**: Built on top of ComfyUI for flexible workflow management.
*   **Python Client Library**: Easy-to-use S3 client for batch processing and automation.

## 🚀 RunPod Serverless Template

This template includes all the necessary components to run Qwen Image Edit as a RunPod Serverless Worker.

*   **Dockerfile**: Configures the environment and installs all dependencies required for model execution.
*   **handler.py**: Implements the handler function that processes requests for RunPod Serverless.
*   **entrypoint.sh**: Performs initialization tasks when the worker starts.
*   **qwen_image_edit_1.json / qwen_image_edit_2.json**: ComfyUI workflows for single- or dual-image editing.

## 🎨 Understanding Image Roles in Dual-Image Workflow

**IMPORTANT**: When using two images, understanding the role of each image is critical for achieving expected results.

### Image Role Convention (Official Qwen Documentation)

According to the [official Qwen-Image-Edit-2509 documentation](https://huggingface.co/Qwen/Qwen-Image-Edit-2509):

- **Image 1 (`image_path`)** = **DONOR**: Source of elements to transfer (person, outfit, object, etc.)
- **Image 2 (`image_path_2`)** = **CANVAS**: Base image that receives edits (background/scene remains)

### Practical Example: Person Swap

To swap a person from Photo A into the scene from Photo B:

```json
{
  "input": {
    "image_path": "/path/to/photo_a.jpg",     // DONOR: person to extract
    "image_path_2": "/path/to/photo_b.jpg",   // CANVAS: scene/background to keep
    "prompt": "Replace the person in the second image with the person in the first image while keeping the background of the second image the same.",
    "seed": 12345,
    "width": 1024,
    "height": 1024
  }
}
```

**Result**: Person from Photo A appears in the scene from Photo B (Photo B's background is preserved).

### Common Use Cases

1. **Person Swap**: Extract person from Image 1, place into scene from Image 2
2. **Outfit Transfer**: Extract outfit from Image 1, apply to person in Image 2
3. **Object Placement**: Extract object from Image 1, place into scene from Image 2
4. **Style Transfer**: Transfer artistic style from Image 1 to content in Image 2

---

### Input Parameters

The `input` object must contain the following fields. Image inputs support **URL, file path, or Base64 encoded string**.

| Parameter | Type | Required | Default | Description |
| --- | --- | --- | --- | --- |
| `prompt` | `string` | **Yes** | `N/A` | Text prompt that guides the edit. **Must clearly specify image roles.** |
| `image_path` or `image_url` or `image_base64` | `string` | **Yes** | `N/A` | First image (DONOR - source of elements). |
| `image_path_2` or `image_url_2` or `image_base64_2` | `string` | No | `N/A` | Second image (CANVAS - base that receives edits). Enables dual-image workflow. |
| `seed` | `integer` | No | `12345` | Random seed for deterministic output. |
| `width` | `integer` | No | `1024` | Output image width in pixels (512-2048, multiple of 8). |
| `height` | `integer` | No | `1024` | Output image height in pixels (512-2048, multiple of 8). |
| `steps` | `integer` | No | `40` | Number of inference steps. Use `4` for Lightning mode (faster, slightly lower quality). |
| `cfg` | `float` | No | `4.0` | CFG scale / true_cfg_scale (official default: 4.0). Controls editing strength. |
| `negative_prompt` | `string` | No | `" "` | Negative prompt (official default: single space `" "`). |

**Notes**:
- If any of the `*_2` fields are provided, the dual-image workflow is selected automatically.
- Official parameters from Qwen-Image-Edit-2509: `steps=40`, `cfg=4.0`, `negative_prompt=" "` (single space).
- Lightning mode LoRA (`Qwen-Image-Lightning-4steps`) is included for faster generation.

**Request Example (single image via URL):**

```json
{
  "input": {
    "prompt": "add watercolor style, soft pastel tones",
    "image_url": "https://path/to/your/reference.jpg",
    "seed": 12345,
    "width": 768,
    "height": 1024
  }
}
```

**Request Example (dual images, path + URL):**

```json
{
  "input": {
    "prompt": "blend subject A and subject B, cinematic lighting",
    "image_path": "/network_volume/img_a.jpg",
    "image_url_2": "https://path/to/img_b.jpg",
    "seed": 7777,
    "width": 1024,
    "height": 1024
  }
}
```

**Request Example (single image via Base64):**

```json
{
  "input": {
    "prompt": "vintage look, grain, warm tones",
    "image_base64": "<BASE64_STRING>",
    "seed": 42,
    "width": 512,
    "height": 512
  }
}
```

### Output

#### Success

If the job is successful, it returns a JSON object with the generated image Base64 encoded.

| Parameter | Type | Description |
| --- | --- | --- |
| `image` | `string` | Base64 encoded image file data. |

**Success Response Example:**

```json
{
  "image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
}
```

#### Error

If the job fails, it returns a JSON object containing an error message.

| Parameter | Type | Description |
| --- | --- | --- |
| `error` | `string` | Description of the error that occurred. |

**Error Response Example:**

```json
{
  "error": "이미지를 찾을 수 없습니다."
}
```

## 🛠️ Usage and API Reference

### Method 1: Direct API Calls

1.  Create a Serverless Endpoint on RunPod based on this repository.
2.  Once the build is complete and the endpoint is active, submit jobs via HTTP POST requests according to the API Reference above.

### Method 2: Python Client Library (Recommended)

The **`qwen_image_edit_s3_client.py`** provides a high-level Python API for easy integration:

```python
from qwen_image_edit_s3_client import QwenImageEditS3Client

# Initialize client
client = QwenImageEditS3Client(
    runpod_endpoint_id="your-endpoint-id",
    runpod_api_key="your-api-key",
    s3_endpoint_url="https://s3api-eu-ro-1.runpod.io/",
    s3_access_key_id="your-s3-key",
    s3_secret_access_key="your-s3-secret",
    s3_bucket_name="your-bucket",
    s3_region="eu-ro-1"
)

# Example 1: Single image edit
result = client.edit_single_image(
    image_path="./photo.jpg",
    prompt="change hair color to blonde, add sunglasses",
    seed=12345,
    width=1024,
    height=1024
)

if result.get('status') == 'COMPLETED':
    client.save_image_result(result, "./output.png")

# Example 2: Dual image edit (person swap)
# Note: Image 1 = DONOR (source), Image 2 = CANVAS (base)
result = client.edit_dual_image(
    image_path="./person_a.jpg",  # DONOR: person to extract
    image_path_2="./scene_b.jpg",  # CANVAS: scene to keep
    prompt="Replace the person in the second image with the person in the first image while keeping the background of the second image the same.",
    seed=12345,
    width=1024,
    height=1024
)

if result.get('status') == 'COMPLETED':
    client.save_image_result(result, "./person_swap.png")

# Example 3: Lightning mode (fast generation - 4 steps)
result = client.edit_single_image(
    image_path="./photo.jpg",
    prompt="make it vintage style",
    use_lightning=True  # Automatically uses 4 steps instead of 40
)

# Example 4: Batch processing
batch_result = client.batch_edit_images(
    image_folder_path="./input_images",
    output_folder_path="./output",
    prompt="enhance image quality",
    use_lightning=True
)
print(f"Processed: {batch_result['successful']}/{batch_result['total_files']}")
```

**Client Features**:
- ✅ Automatic S3 upload handling
- ✅ Job submission and status polling
- ✅ Built-in Lightning mode support
- ✅ Batch processing capabilities
- ✅ Clear documentation of image roles
- ✅ Comprehensive error handling

### 📁 Using Network Volumes

Instead of directly transmitting Base64 encoded files, you can use RunPod's Network Volumes to handle large files. This is especially useful when dealing with large image files.

1.  **Create and Connect Network Volume**: Create a Network Volume (e.g., S3-based volume) from the RunPod dashboard and connect it to your Serverless Endpoint settings.
2.  **Upload Files**: Upload the image files you want to use to the created Network Volume.
3.  **Specify Paths**: When making an API request, specify the file paths within the Network Volume for `image_path` or `image_path_2`. For example, if the volume is mounted at `/my_volume` and you use `reference.jpg`, the path would be `"/my_volume/reference.jpg"`.

## 🔧 Workflow Configuration

This template includes the following workflow configurations:

*   **qwen_image_edit_1.json**: Single-image editing workflow
*   **qwen_image_edit_2.json**: Dual-image editing workflow

The workflows are based on ComfyUI and include necessary nodes for prompt-guided image editing and output processing.

## 🙏 Original Project

This project is based on the following repositories. All rights to the model and core logic belong to the original authors.

*   **ComfyUI:** [https://github.com/comfyanonymous/ComfyUI](https://github.com/comfyanonymous/ComfyUI)
*   **Qwen (project group):** [https://github.com/QwenLM/Qwen-Image](https://github.com/QwenLM/Qwen-Image)

## 📄 License

This template adheres to the licenses of the original projects.
