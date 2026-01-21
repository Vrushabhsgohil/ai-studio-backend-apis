import os
import io
import base64
from openai import OpenAI
from PIL import Image
from dotenv import load_dotenv

load_dotenv()

# -----------------------------
# OpenAI Client Setup
# -----------------------------
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise RuntimeError("OPENAI_API_KEY is missing from environment variables")

client = OpenAI(api_key=api_key)

MODEL_ID = "gpt-4.1-nano"

def generate_text(prompt: str, image: Image.Image = None) -> str:
    """
    Centralized OpenAI text generation with multimodal support.
    """
    try:
        messages = [
            {"role": "system", "content": "You are a professional video production and prompt engineering assistant."},
            {"role": "user", "content": [{"type": "text", "text": prompt}]}
        ]

        if image:
            # Convert PIL image to base64
            buffered = io.BytesIO()
            if image.mode in ("RGBA", "P"):
                image = image.convert("RGB")
            image.save(buffered, format="JPEG")
            base64_image = base64.b64encode(buffered.getvalue()).decode('utf-8')
            
            messages[1]["content"].append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
            })

        response = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            temperature=0.6,
            max_tokens=800
        )
        return response.choices[0].message.content.strip() if response.choices[0].message.content else ""
    except Exception as e:
        print(f"[OpenAI Error] {e}")
        return ""



class AgentSystem:
    """
    Multi-agent system for structured video prompt generation
    targeting OpenAI Sora 2.
    """

    @staticmethod
    def agent_1_intent_use_case(user_input: str, image: Image.Image = None) -> str:
        prompt_text = f"""
            You are an Intent & Use-Case Analysis Agent.

            Analyze the following user request and the attached product image (if provided):
            "{user_input}"

            CHECK FOR REALISM/HUMAN PRESENCE:
            - Does the user ask for "realistic", "realism", or "model"?
            - KEY INSTRUCTION: If the user mentions "realistic" or "realism", you MUST set "Human Model Required" to YES.

            Extract and summarize:
            - Video objective (marketing, catalog, cinematic, UGC, explainer)
            - Target audience
            - Primary platform (Instagram, YouTube, Website, Ads)
            - Emotional tone (luxury, cinematic, dramatic, energetic - avoid "minimal" unless explicitly requested)
            - Key Product Features (visualized from the image)
            - Human Model Required: [YES/NO] (Default to NO unless "realistic" or "model" is requested)

            Return a concise intent summary in plain text.
"""
        return generate_text(prompt_text, image=image)

    @staticmethod
    def agent_1b_script_generator(intent_summary: str, language: str = "English") -> str:
        prompt_text = f"""
            You are a professional script writer for short cinematic videos.

            Your task is to write a high-impact dialogue script based on this intent:
            "{intent_summary}"

            LANGUAGE REQUIREMENTS:
            - Write the script strictly in {language}.
            - Ensure the wording is natural, fluent, and culturally appropriate in {language}.
            - Preserve the intended meaning clearly and accurately.

            STRICT CONSTRAINTS:
            - WORD COUNT: The script must contain BETWEEN 8 AND 10 WORDS ONLY.
            - TONE: Match the emotional tone implied by the intent.
            - SAFETY: Do not include sexual themes, violence, real people, or sensitive anatomical references.
            - FORMAT: Output ONLY the script text. No titles, labels, or explanations.

            Script:
            """
        script = generate_text(prompt_text)
        return script


    @staticmethod
    def agent_2_visual_direction(intent_summary: str, language: str = "English", image: Image.Image = None) -> str:
        prompt_text = f"""
            You are a Visual Direction Agent.

            Based on this intent summary and the attached reference image:
            "{intent_summary}"

            CRITICAL INSTRUCTION:
            - If "Human Model Required" is YES in the intent summary, you MUST explicitly describe a **GENERIC, FICTIONAL** human model (specify gender/style if implied, but ensure they are described as a "model" or "actor"). Avoid describing real people or specific identities.
            - If "Human Model Required" is NO, focus on product-only shots unless the intent implies otherwise.

            Safety Filter Prevention:
            - DO NOT use terms like "chest", "bust", "cleavage", "curves", "seductive", "sexy". Use "upper body", "neckline", "silhouette", "outfit" instead.
            - Aim for "Professional Fashion" or "Catalog" aesthetics, avoiding "suggestive" angles.

            BALANCE INSTRUCTION:
            - Visuals must be related to the {language} language.
            - PROHIBIT obsessive "macro" dominance. The user wants a "Real Video" feel, not just a product showcase.
            - Prioritize **LIFESTYLE & ATMOSPHERE**. Show the model *existing* in the space.
            - Use **Medium** and **Wide** shots more than Close-ups.

            LANGUAGE–VISUAL BINDING (MANDATORY):
            - The selected language ({language}) MUST directly determine the cultural, geographic, architectural, lifestyle, fashion, and environmental context of the visuals.
            - Treat the language as an indicator of where the scene naturally exists in the real world.
            - The visual direction must feel native to regions where the language is commonly used, not generic or globally neutral.
            - If the visuals could plausibly belong to a different language region, they are incorrect and must be revised.
            - The viewer should be able to infer the language context purely from the visuals, even without text or audio.

            Define:
            - Environment (lifestyle, luxury interior, outdoor, cinematic set) - AVOID plain white studio backgrounds unless explicitly requested. Create depth and atmosphere. Ensure ENVIRONMENTAL STABILITY (no shifting walls or changing decor).
            - Lighting style (cinematic, golden hour, dramatic shadows, soft luxury) - LIGHTING MUST BE CONSISTENT. No random exposure changes or flickering sources.
            - Camera behavior (handheld realism, following the subject, wide cinematic masters) - Use "Weighted Camera Gear" feel to prevent micro-jitter.
            - Visual aesthetic (cinematic photorealism, rich textures, lifestyle-focused)
            - Subject Presentation: (Describe the model or product formatting clearly) - Product/Subject identity must remain CONSTANT.

            Return a clear visual direction guide in plain text.
        """
        return generate_text(prompt_text,image=image)

    @staticmethod
    def agent_3_scene_breakdown(intent_summary: str, visual_style: str) -> str:
        prompt_text = f"""
            You are a Scene & Shot Breakdown Agent.

            Intent:
            "{intent_summary}"

            Visual Style:
            "{visual_style}"

            Break the video into logical scenes for a **11-SECOND VIDEO**:
            - Opening hook (0-3s) - ESTABLISHING SHOT. Do not start with a macro. Show the vibe.
            - Primary focus scene (3-8s) - Model interacting with environment, walking, or moving comfortably. Product is visible but integrated naturally.
            - Closing frame or CTA (8-11s) - Final atmospheric shot.

            Ensure strict adherence to the 11-second total duration.
            Restrict scene descriptions to safe, professional language (no anatomical focus).
            Avoid "Extreme Close Up" spam. Use "Medium Shot" or "Wide Shot" to establish realism.
        """
        return generate_text(prompt_text)

    @staticmethod
    def agent_4_motion_timing(scene_breakdown: str) -> str:
        prompt = f"""
            You are a Motion & Timing Optimization Agent.

            Based on this scene breakdown:
            "{scene_breakdown}"

            Define:
            - Subject motion (MUST be observable and natural - e.g., walking through a room, turning around, interacting with a prop. Avoid static posing. Use "Rigid Body Physics" for objects.)
            - Camera movement speed (Cinematic, handheld feel, tracking shots. Apply "Cinematic Damping" to smooth out jitter.)
            - Scene timing (Must align to 11.0 seconds total)
            - Slow-motion vs real-time moments

            Optimize motion realism and clarity for Sora 2 video generation.
        """
        return generate_text(prompt)

    @staticmethod
    def agent_5_safety_compliance(combined_inputs: str) -> str:
        prompt = f"""
            You are a Safety & Compliance Agent.

            Review the following content for platform safety, realism, and visual stability:
            "{combined_inputs}"

            STRICT REALISM RULES:
            - If the content is flagged as "realistic", explicitly FORBID:
            - Illogical physics (flying objects, defying gravity, morphing)
            - Cartoonish or surreal elements unless explicitly requested
            - Distorted anatomy or impossible movement
            - Actions that cannot logically complete within 11 seconds
            
            TECHNICAL QA FAILURES TO REJECT:
            - Frame instability or jitter
            - Shape/Identity drift (objects changing form)
            - Texture flicker or "swimming" textures
            - Sudden, unjustified lighting changes
            - Inconsistent blur application

            ANATOMY SAFETY:
            - Reject any description focusing on "chest", "bust", "groin", or suggestive poses.
            - Ensure the prompt focuses on "Fashion" and "Product", not "Body".

            Output ONLY one safety constraint line.

            Default format:
            "Safety constraints: Ensure physical plausibility, professional fashion presentation, no distorted anatomy, no unnatural motion, no flickering, no visual artifacts."

            (Do not use the phrase "Realism enforced". Focus on "physical plausibility" and "professional presentation".)

            If required, add minor constraints, but keep it concise.
        """
        return generate_text(prompt)

    @staticmethod
    def agent_6_final_prompt(
        intent: str,
        visuals: str,
        scenes: str,
        motion: str,
        safety: str,
        language: str = "English",
        script: str = ""
    ) -> str:
        prompt = f"""
            You are the FINAL Prompt Aggregation Agent.

            Your task is to generate ONE unified, cinematic, production-ready video prompt
            optimized specifically for OpenAI Sora 2.

            Inputs:
            Intent: {intent}
            Visual Direction: {visuals}
            Scenes: {scenes}
            Motion: {motion}
            Safety: {safety}
            Script: {script}
            Language: {language}

            Rules:
            - Output ONE final prompt only
            - No agent references
            - No explanations
            - No markdown
            - Natural cinematic language
            - No contradictions
            - The visual direction must feel native to regions where the language ({language}) is commonly used, not generic or globally neutral.
            - IF INTENT says "Human Model Required: YES", ENSURE the prompt describes a person (using safe, professional terms).
            - STRICTLY LIMIT to 11 seconds worth of content descriptions.
            - ENSURE all actions are logically consistent and realistic. No impossible physics.

            Required format:
            Create a high-quality cinematic video showing [subject or product].
            The scene is set in [environment], with [lighting style].
            Camera movement includes [camera behavior], capturing [key moments].
            The motion is [motion description], with smooth transitions and realistic physics.
            The overall mood is [emotional tone], designed for [platform or use case].
            Ultra-realistic textures, natural depth of field, accurate reflections,
            and professional cinematic composition.
            Technical Specs: Temporal stability, consistent geometry, optical flow, rigid body physics.
            [safety line]
            Script: {script}
        """
        return generate_text(prompt)
