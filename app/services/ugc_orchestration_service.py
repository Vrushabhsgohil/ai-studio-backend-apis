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
        Optimized to complete within 11 seconds by using a single Master Agent.
        """
        try:
            self.log_info(f"Starting optimized UGC workflow for {video_db_id}")
            
            # Step 1: UGC Master Agent (Consolidates Concept, Cinematography, Atmosphere, and Consistency)
            self.log_info(f"[{video_db_id}] Step 1: Running UGC Master Agent")
            refined_prompt = self._run_ugc_master_agent(user_content, voice_over)
            
            # Step 2: Streamlined QA Loop (1 attempt for speed)
            self.log_info(f"[{video_db_id}] Step 2: Running Performance QA Check")
            final_prompt, qa_res = self._run_ugc_qa_loop(refined_prompt, user_content, voice_over)
            
            # Step 3: Moderation
            self.log_info(f"[{video_db_id}] Step 3: Checking Moderation")
            if openai_service.moderation_check(final_prompt):
                self.log_warning(f"[{video_db_id}] UGC prompt flagged. Sanitizing...")
                final_prompt = self._sanitize_prompt(final_prompt)
            else:
                self.log_info(f"[{video_db_id}] Moderation check passed.")

            # Step 4: Submit to Sora 2
            self.log_info(f"[{video_db_id}] Step 4: Submitting to Sora 2")
            ref_bytes = process_and_resize_image(reference_image_b64)
            job_id = openai_service.create_video_job(final_prompt, ref_bytes)
            self.log_info(f"[{video_db_id}] Sora 2 job created: {job_id}")
            
            # Start polling
            self.poll_and_save_video(video_db_id, job_id, final_prompt)
            
        except Exception as e:
            self.log_error(f"Optimized UGC flow failed for {video_db_id}", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

    # --- UGC OPTIMIZED AGENTS ---

    def _run_ugc_master_agent(self, user_content: str, voice_over: bool) -> str:
        """
        Combines multiple specialized roles into one expert prompt engineer call.
        Covers: Concept, Cinematography, Atmosphere, and Reference Consistency.
        """
        prompt = f"""
        You are the UGC Master Orchestrator for Sora 2. Your goal is to generate a single, highly accurate video prompt.
        You must perform the following roles simultaneously:
        1. Expert Content Analyst: Extract pure subject, action, and narrative context.
        2. Sora-2 Cinematographer: Define complex motion (hand-held tracking/orbiting for realism), framing (typically 35mm), and focus depth.
        3. Visual Stylist: Define natural lighting (warm indoor or overcast outdoor), realistic skin textures, and authentic environment details.
        4. Consistency Supervisor: Ensure geometric accuracy and material faithfulness to the reference image.
        5. UGC Script Writer: {'If voiceover is enabled, write a natural-sounding script of 25-30 words that the subject will speak directly to the camera.' if voice_over else 'No voiceover needed.'}

        OUTPUT RULES:
        - Return a single, cohesive paragraph (max 250 words).
        - Start with the overall scene and the subject.
        - Describe motion and camera techniques vividly (use terms like 'handheld', 'natural jitter', 'focus pull').
        - Define environment and atmosphere.
        - {'EMPHASIS: The subject must be seen speaking the following script naturally with synchronized lip movements: [INSERT SCRIPT HERE]. DIRECT TO CAMERA ADDRESS IS KEY.' if voice_over else ''}
        - APPEND strictly: 'The visual attributes, colors, and textures must EXACTLY match the provided reference image.'
        - NO JSON, NO MARKDOWN, ONLY THE PARAGRAPH.
        """
        return openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}])

    def _run_ugc_qa_loop(self, initial_prompt: str, user_content: str, voice_over: bool) -> (str, Dict):
        """
        Streamlined QA check with a single improvement pass to stay within 11s.
        """
        qa_prompt = f"""
        You are a Senior Video Quality Assurance Auditor for UGC content. 
        Score from 0-100. REQUIRED SCORE: 85.
        Check for: Alignment with intent, Sora 2 compatibility, and specificity.
        {'STRICT REQUIREMENT: If voiceover is enabled, verify the prompt includes a natural-sounding script of 25-30 words and explicit lipsync/speaking instructions.' if voice_over else ''}
        Return JSON: {{approved: bool, score: int, violations: list, qa_summary: str}}.
        """
        # Attempt 1
        self.log_info("Running UGC QA check (Attempt 1/1)")
        qa_res_str = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": qa_prompt}, {"role": "user", "content": f"Prompt: {initial_prompt}\nUser Intent: {user_content}"}])
        qa_res = extract_json_from_text(qa_res_str)
        score = qa_res.get("score", 0)
        
        self.log_info(f"UGC QA Score: {score}")
        if score >= 85:
            return initial_prompt, qa_res
            
        # Quick single improvement pass if failed
        self.log_info(f"UGC QA Score {score} < 85. Applying one-shot improvement.")
        fix_prompt = f"Fix these accuracy violations: {json.dumps(qa_res.get('violations'))}. Ensure Sora 2 best practices. Return fixed prompt paragraph only."
        final_prompt = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": fix_prompt}, {"role": "user", "content": initial_prompt}])
        
        return final_prompt, qa_res

ugc_orchestrator = UgcOrchestrationService()
