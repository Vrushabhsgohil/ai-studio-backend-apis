# AI Studio Backend

AI Studio Backend is a state-of-the-art, enterprise-grade FastAPI application designed for advanced AI-driven media generation. It provides a robust orchestration layer that integrates multiple AI models to create high-fidelity images and cinematic videos with a focus on product realism and professional quality.

## 🚀 Key Features

### 🎬 Advanced Video Orchestration
- **Promotional Video Generation**: Optimized for product-centric commercials with automated "luxurious" or "stylish" vibes.
- **Fashion Video Generation**: Tailored for apparel, allowing human presence while strictly maintaining garment details from reference images.
- **UGC (User Generated Content) Orchestration**: A dedicated high-accuracy layer for natural-looking video content.
- **Multi-Agent Architecture**: Uses a chain of specialized agents (Concept, Visual, Audio, Assembly, and QA) to refine prompts and ensure high-quality output.
- **Automated QA & Moderation**: Built-in quality assurance loops with scoring and iterative refinement, coupled with multi-stage moderation checks.

### 🖼️ Intelligent Image Generation
- **Prompt Refinement**: Leverages OpenAI's `gpt-4o-mini` with specialized context to transform basic requests into detailed, photographic-style prompts.
- **Multi-Backend Support**: Seamlessly toggle between **FalAI** (Flux/ControlNet) and **Replicate** for image generation.
- **Product-Centric Realism**: Engineered to preserve product identity (text, shape, color) while transforming environments.

### ⚙️ Enterprise Architecture
- **Asynchronous Processing**: Background task management for long-running AI jobs using FastAPI BackgroundTasks.
- **Robust Storage**: Integration with **Supabase Storage** for secure and scalable hosting of generated assets.
- **Smart Polling**: Intelligent status tracking for external AI job completion.
- **Structured Logging**: Comprehensive logging for every step of the orchestration flow.

## 🛠️ Tech Stack

- **Framework**: FastAPI (Python 3.10+)
- **Large Language Models**: OpenAI (GPT-4 / GPT-4o-mini)
- **Video Generation**: OpenAI Sora-2
- **Image Generation**: FalAI (Flux), Replicate
- **Database & Storage**: Supabase (PostgreSQL & Storage)
- **Media Processing**: FFmpeg
- **Infrastructure**: Docker & Docker Compose

## 🛠️ Getting Started

### Prerequisites
- Python 3.10+
- Docker & Docker Compose (optional)

### Installation

1. **Clone the repository:**
   ```bash
   git clone <repository-url>
   cd ai-studio-backend-apis
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

### Configuration

Create a `.env` file in the root directory:

```env
OPENAI_API_KEY=your_openai_key
FAL_KEY=your_falai_key
REPLICATE_API_TOKEN=your_replicate_token
SUPABASE_URL=your_supabase_url
SUPABASE_KEY=your_supabase_key
SERVICE_TYPE=replicate  # "replicate" or "falai"
POLL_INTERVAL_SEC=10
POLL_MAX_MIN=15
```

### Running the Application

**Locally:**
```bash
uvicorn app.main:app --reload
```

**Using Docker:**
```bash
docker-compose up --build
```

The API will be available at `http://localhost:8000`. Documentation can be accessed at `http://localhost:8000/api/v1/docs`.

## 📂 Project Structure

```text
├── app/
│   ├── api/            # API routing and versioned endpoints
│   ├── core/           # Config, exceptions, and logging utilities
│   ├── schemas/        # Pydantic models for validation
│   ├── services/       # AI Service integrations and Orchestration logic
│   └── main.py         # Application entry point
├── outputs/            # Local storage for generated media (mapped to docker volumes)
├── Dockerfile          # Container definition
├── docker-compose.yml  # Multi-container orchestration
└── requirements.txt    # Python dependencies
```

## 🔌 Primary API Endpoints

### Video Generation
- `POST /api/v1/video/generate-promo-video`: Cinematic product commercials.
- `POST /api/v1/video/generate-fashion-video`: High-end fashion film generation.
- `POST /api/v1/video/generate-ugc-video`: Natural user-generated content orchestration.
- `GET /api/v1/video/status/{job_id}`: Poll generation status.

### Image Generation
- `POST /api/v1/generation/refine`: Refine prompts and generate images.

## 📄 License
[Commercial License / MIT]
