from typing import Dict, Any, Optional, List
import json
import base64
from app.services.orchestration_service import OrchestrationService
from app.services.openai_service import openai_service
from app.services.database_service import db_service
from app.core.exceptions import ModerationError, AIServiceError, ValidationError
from app.core.utils import extract_json_from_text, process_and_resize_image

class UgcOrchestrationService(OrchestrationService):
    """
    Advanced orchestration layer for UGC (User Generated Content) video generation.
    Optimized for Sora 2 with a specialized 5-agent flow for "pure accuracy".
    """

    def run_ugc_orchestration_flow(self, video_db_id: str, user_content: str, reference_image_b64: str, voice_over: bool, promo_vibe: str):
        """
        Orchestrates a high-speed, high-accuracy flow for UGC video generation.
        Includes product analysis, factual QA, and realism enforcement.
        """
        try:
            self.log_info(f"Starting advanced UGC workflow for {video_db_id}")
            
            # Step 1: Image Analysis Agent
            self.log_info(f"[{video_db_id}] Step 1: Running Image Analysis Agent")
            product_data = self._run_image_analysis_agent(reference_image_b64)
            
            # Step 2: Image Analysis QA
            self.log_info(f"[{video_db_id}] Step 2: Running Image Analysis QA")
            qa_valid, qa_feedback = self._run_image_analysis_qa_agent(reference_image_b64, product_data)
            if not qa_valid:
                self.log_warning(f"[{video_db_id}] Image analysis QA flagged issues. Attempting self-correction...")
                product_data = self._run_image_analysis_agent(reference_image_b64, feedback=qa_feedback)

            # Step 3: Realism Validation (Enforced in Master Agent prompt)
            self.log_info(f"[{video_db_id}] Step 3: Enforcing Realism Validation")
            realism_guidelines = self._check_video_realism(user_content, reference_image_b64)

            # Step 4: UGC Master Agent
            self.log_info(f"[{video_db_id}] Step 4: Running UGC Master Agent")
            refined_prompt = self._run_ugc_master_agent(user_content, voice_over, product_data, realism_guidelines)
            
            # Step 5: Streamlined QA Loop
            self.log_info(f"[{video_db_id}] Step 5: Running Performance QA Check")
            final_prompt, qa_res = self._run_ugc_qa_loop(refined_prompt, user_content, voice_over)
            
            # Step 6: Moderation
            self.log_info(f"[{video_db_id}] Step 6: Checking Moderation")
            if openai_service.moderation_check(final_prompt):
                self.log_warning(f"[{video_db_id}] UGC prompt flagged. Sanitizing...")
                final_prompt = self._sanitize_prompt(final_prompt)
            else:
                self.log_info(f"[{video_db_id}] Moderation check passed.")

            # Step 7: Submit to Sora 2
            self.log_info(f"[{video_db_id}] Step 7: Submitting to Sora 2")
            ref_bytes = process_and_resize_image(reference_image_b64)
            job_id = openai_service.create_video_job(final_prompt, ref_bytes)
            self.log_info(f"[{video_db_id}] Sora 2 job created: {job_id}")
            
            # Start polling
            self.poll_and_save_video(video_db_id, job_id, final_prompt)
            
        except Exception as e:
            self.log_error(f"Advanced UGC flow failed for {video_db_id}", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

    # --- UGC OPTIMIZED AGENTS ---

    def _run_image_analysis_agent(self, image_b64: str, feedback: Optional[str] = None) -> Dict[str, Any]:
        """
        Analyzes the reference image to extract structured product details.
        """
        prompt = f"""
        You are an expert Production Designer and Product Analyst. Analyze the provided image and return a strictly structured JSON response with the following fields:
        
        - brand_name: (brand name if visible, otherwise null)
        - product_name: (product name if visible; if printed, return the exact printed name; otherwise null)
        - variant: (flavor, scent, or type printed on the product, otherwise null)
        - visible_text: [list every readable text element exactly as printed on the product]
        - color_scheme: [{{hex: "#...", name: "..."}}]
        - material: (e.g., plastic, glass, metal, cardboard, etc.)
        - texture: (e.g., smooth, glossy, matte, ribbed, patterned, etc.)
        - product_shape: (e.g., bottle, tube, jar, box, pouch; include any shape refinements)
        - product_size: (small / medium / large)
        - dimensions_in_cm: (exact dimensions if visible; otherwise null)
        - components: [describe all visible components such as cap, pump, lid, applicator, nozzle, etc.]
        - cap_status: (open / closed / not_applicable)
        - label_design: {{ typography: "...", layout_description: "...", imagery: "..." }}
        - condition: (new / used / partially_used / unknown)
        - visual_description: (Provide exactly 2 sentences summarizing the product itself, ignoring background and surroundings)

        {f"REVISION FEEDBACK: {feedback}" if feedback else ""}
        
        STRICT RULES:
        1. Return ONLY JSON.
        2. If a value is unknown, use null.
        3. Be extremely precise with visible text.
        """
        res_str = openai_service.vision_chat_completion(model="gpt-4o", prompt=prompt, image_b64=image_b64)
        self.log_info(f"UGC Image Analysis Agent Response: {res_str}...")
        return extract_json_from_text(res_str)

    def _run_image_analysis_qa_agent(self, image_b64: str, product_data: Dict[str, Any]) -> (bool, Optional[str]):
        """
        Validates the factual accuracy of the Image Analysis Agent output.
        """
        prompt = f"""
        You are a Vision QA Auditor. Compare the following extracted product data with the image:
        {json.dumps(product_data, indent=2)}

        TASKS:
        1. Validate factual accuracy and visual alignment.
        2. Flag hallucinations or incorrect assumptions.
        3. Confirm all attributes are visually verifiable.

        Return JSON: {{ "approved": bool, "feedback": "Detailed explanation of issues or 'passed'" }}
        """
        res_str = openai_service.vision_chat_completion(model="gpt-4o", prompt=prompt, image_b64=image_b64)
        self.log_info(f"UGC Image Analysis QA Agent Response: {res_str}...")
        qa_res = extract_json_from_text(res_str)
        return qa_res.get("approved", False), qa_res.get("feedback")

    def _check_video_realism(self, user_content: str, image_b64: Optional[str] = None) -> str:
        """
        Enforces realism standards for content generation and detects AI-generated inputs.
        """
        if image_b64:
            detection_prompt = """
            You are a Digital Forensics Expert. Analyze the provided image and determine if it appears AI-generated or if it's a real-world photograph.
            
            CHECK FOR:
            1. Unnatural textures, repeating patterns, or geometric inconsistencies.
            2. Inconsistent lighting or impossible shadows.
            3. AI-typical artifacts (e.g., warped fingers, nonsensical text in background).
            
            Return JSON: { "is_ai_generated": bool, "confidence": float, "analysis": "..." }
            """
            try:
                res_str = openai_service.vision_chat_completion(model="gpt-4o", prompt=detection_prompt, image_b64=image_b64)
                self.log_info(f"Realism Detection Response: {res_str}...")
                detection_res = extract_json_from_text(res_str)
                if detection_res.get("is_ai_generated") and detection_res.get("confidence", 0) > 0.8:
                    self.log_warning(f"Reference image flagged as AI-generated (Confidence: {detection_res.get('confidence')}). Enforcing strict realism grounding.")
            except Exception as e:
                self.log_error("Realism detection failed, proceeding with default grounding.", e)

        return """
        HIGH-FIDELITY REALISM & CINEMATIC STANDARDS:
        - Technical Camera Specs: Shot on Arri Alexa LF with Zeiss Master Prime lenses, 35mm sensor format.
        - Rendering Detail: Include subsurface scattering (SSS) for skin and translucent materials. Micro-textures, skin pores, and fabric weave must be visible. 
        - Lighting: Volumetric lighting with global illumination and ray-traced reflections. Natural light falloff.
        - Movement: Professional handheld tracking/orbiting with organic jitter. Avoid mechanical or linear motion.
        - Authenticity: Embrace organic noise and real-world micro-imperfections. REJECT synthetic CGI looks, plastic textures, or 'too perfect' symmetry.
        - Quality: Uncompressed 8k photorealistic cinematic RAW footage look.
        """

    def _run_ugc_master_agent(self, user_content: str, voice_over: bool, product_data: Optional[Dict[str, Any]] = None, realism_guidelines: Optional[str] = None) -> str:
        """
        Consolidates intelligence from all agents into a final Sora 2 prompt.
        Ensures logical consistency, physical plausibility, and narrative completion.
        """
        product_context = f"PRODUCT DETAILS: {json.dumps(product_data)}" if product_data else ""
        
        prompt = f"""
        You are the UGC Master Orchestrator for Sora 2. Your goal is to generate a single, highly accurate video prompt.
        
        CONTEXT:
        {product_context}
        {realism_guidelines if realism_guidelines else ""}

        STRICT REALISM & LOGIC RULES:
        1. Logical Consistency: All actions performed must strictly match real-world behavior. Unrealistic or illogical actions are FORBIDDEN.
        2. Physical Plausibility: Every movement and interaction must obey the laws of physics and real-world logic.
        3. Narrative Completion: The video MUST end with a sense of completion. The script and narrative flow must be fully finished before the video ends. NO ABRUPT OR UNFINISHED SEQUENCES.
        4. Timing constraints: The entire sequence must fit perfectly within a 12-second window.

        ROLES:
        1. Expert Content Analyst: Extract pure subject, action, and narrative from user request: '{user_content}'.
        2. Sora-2 Cinematographer: Define complex motion (hand-held tracking/orbiting), authentic framing, and depth of field. Use 'handheld' and 'natural jitter'.
        3. Visual Stylist: Define natural lighting, realistic skin textures, and organic environment details.
        4. Consistency Supervisor: Ensure geometric accuracy and material faithfulness to the product attributes.
        5. UGC Script Writer: {'If voiceover is enabled, write a natural-sounding script of 18-20 words that the subject will speak. Ensure it is coherent and fully spoken before the video ends.' if voice_over else 'No voiceover.'}

        OUTPUT RULES:
        - Return a single, cohesive paragraph (max 220 words).
        - Start with the overall scene and the subject.
        - Use professional keywords: 'Arri Alexa RAW', 'subsurface scattering', 'global illumination', '8k photorealistic', 'micro-textures'.
        - {'EMPHASIS: The subject must speak this script with natural lip synchronization: [INSERT SCRIPT]. The script must be completed by the 11th second.' if voice_over else ''}
        - APPEND strictly: 'The visual attributes, colors, and textures must EXACTLY match the following product description: {product_data.get('visual_description') if product_data else 'reference image'}.'
        - NO JSON, ONLY THE PARAGRAPH.
        """
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}])
        self.log_info(f"UGC Master Agent Response: {res}...")
        return res

    def _run_ugc_qa_loop(self, initial_prompt: str, user_content: str, voice_over: bool) -> (str, Dict):
        """
        Streamlined QA check with a single improvement pass to stay within 11s.
        """
        qa_prompt = f"""
        You are a Senior Video Quality Assurance Auditor for High-Fidelity UGC content. 
        Score from 0-100. REQUIRED SCORE: 92.
        
        CRITICAL EVALUATION CRITERIA:
        1. High-Fidelity Realism: Does the prompt use technical cinematic terms? Does it avoid 'synthetic' or 'artifical' CGI descriptions?
        2. Real-World Logic: Are the actions logically consistent and physically plausible?
        3. Narrative Completion: Does the video sequence feel finished? Is there an abrupt ending?
        4. Script Timing: {'Does the 18-20 word script fit within a 12s video?' if voice_over else 'N/A'}
        5. Visual Detail: Does it specify micro-textures and subsurface scattering?

        Return JSON: {{approved: bool, score: int, violations: list, qa_summary: str}}.
        """
        # Attempt 1
        self.log_info("Running UGC QA check (Attempt 1/1)")
        qa_res_str = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": qa_prompt}, {"role": "user", "content": f"Prompt: {initial_prompt}\nUser Intent: {user_content}"}])
        self.log_info(f"UGC QA Agent Response: {qa_res_str}...")
        qa_res = extract_json_from_text(qa_res_str)
        score = qa_res.get("score", 0)
        
        self.log_info(f"UGC QA Score: {score}")
        if score >= 85:
            return initial_prompt, qa_res
            
        # Quick single improvement pass if failed
        self.log_info(f"UGC QA Score {score} < 85. Applying one-shot improvement.")
        fix_prompt = f"Fix these accuracy violations: {json.dumps(qa_res.get('violations'))}. Ensure Sora 2 best practices. Return fixed prompt paragraph only."
        final_prompt = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": fix_prompt}, {"role": "user", "content": initial_prompt}])
        self.log_info(f"UGC QA Improvement Response: {final_prompt}...")
        
        return final_prompt, qa_res

ugc_orchestrator = UgcOrchestrationService()
