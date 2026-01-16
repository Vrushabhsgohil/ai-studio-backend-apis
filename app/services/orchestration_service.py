from typing import Dict, Any, Optional, List
import time
import os
import requests
import json
import base64
import uuid
from app.services.base_service import BaseService
from app.services.openai_service import openai_service
from app.services.database_service import db_service
from app.core.exceptions import ModerationError, AIServiceError, ValidationError, AIStudioError
from app.core.utils import extract_json_from_text, process_and_resize_image, download_image

class OrchestrationService(BaseService):
    """
    Main orchestrator for all complex workflows (Video, Image, etc.).
    Follows the single entry point pattern requested by the user.
    """

    # --- IMAGE WORKFLOWS ---

    def initiate_image_generation(self, user_content: str, reference_image_url: str, user_id: Optional[str]) -> str:
        """
        Initial entry point for image generation. Creates DB record.
        Matches schema: title, image_url, ref_image_url, user_content, status, user_id.
        """
        self.log_info(f"Initiating image generation for user {user_id}")
        
        image_data = {
            "title": "Generated Image",
            "ref_image_url": reference_image_url,
            "user_content": user_content,
            "status": "pending",
            "user_id": user_id
        }
        image_data = {k: v for k, v in image_data.items() if v is not None}
        
        record = db_service.insert_record("image_assets", image_data)
        return record["id"]

    def run_image_orchestration_flow(self, image_db_id: str, content: str, image_link: str):
        """
        Orchestrates image refinement, generation, and storage in the background.
        """
        self.log_info(f"Running image orchestration for {image_db_id}")
        try:
            # 1. Refine Prompt
            db_service.update_record("image_assets", image_db_id, {"status": "pending"}) # Re-assert pending or refine
            refined_content = self.refine_prompt(content, image_link)
            
            # 2. Generate Image
            image_url = self.generate_image(refined_content, image_link)
            
            # 3. Generate Title
            title = self._generate_creative_title(refined_content)
            
            # 4. Download and Upload to Supabase Storage
            self.log_info(f"Downloading generated image from {image_url}")
            image_bytes = download_image(image_url)
            
            # Generate a unique path in bucket
            file_extension = "png"
            file_path = f"{image_db_id}.{file_extension}"
            
            storage_url = db_service.upload_file(
                bucket_name="ai_images",
                file_path=file_path,
                file_content=image_bytes,
                content_type=f"image/{file_extension}"
            )
            
            # 5. Final DB Update
            db_service.update_record("image_assets", image_db_id, {
                "status": "completed",
                "image_url": storage_url,
                "image_prompt": refined_content,
                "title": title
            })
            
        except Exception as e:
            self.log_error(f"Image orchestration flow failed for {image_db_id}", e)
            db_service.update_record("image_assets", image_db_id, {
                "status": "failed",
                "error_message": str(e)
            })

    def refine_prompt(self, content: str, image_url: str) -> str:
        messages = [
            {"role": "system", "content": "You are a creative director. Refine the given prompt based on the user content and reference image to be more descriptive and suitable for image generation."},
            {"role": "user", "content": f"User Content: {content}\nReference Image: {image_url}"}
        ]
        return openai_service.chat_completion(model="gpt-4o-mini", messages=messages)

    def generate_image(self, prompt: str, image_url: str) -> str:
        service_type = self.settings.SERVICE_TYPE.lower()
        if service_type == "replicate":
            from app.services.replicate_service import replicate_service
            return replicate_service.generate_image(prompt, image_url)
        else:
            from app.services.falai_service import fal_ai_service
            return fal_ai_service.generate_image(prompt, image_url)

    # --- VIDEO WORKFLOWS ---

    def initiate_video_generation(self, video_type: str, user_content: str, reference_image_b64: Optional[str], reference_image_url: Optional[str], user_id: Optional[str], voice_over: bool, promo_vibe: str) -> str:
        """
        Initial entry point for video generation. Creates DB record and prepares image.
        Matches schema: title, image_url, user_content, status, user_id.
        """
        self.log_info(f"Initiating {video_type} video generation for user {user_id}")
        
        # 1. Prepare image
        image_b64 = reference_image_b64
        if not image_b64 and reference_image_url:
            try:
                image_content = download_image(reference_image_url)
                image_b64 = base64.b64encode(image_content).decode("utf-8")
            except Exception as e:
                raise ValidationError(f"Failed to download image: {str(e)}")
        
        if not image_b64:
            raise ValidationError("Reference image must be provided either as base64 or URL")

        # 2. Database record creation
        video_data = {
            "title": f"{video_type.capitalize()} Video",
            "image_url": reference_image_url,
            "user_content": user_content,
            "status": "pending",
            "user_id": user_id
        }
        # Filter out None values to let DB defaults work (like user_id)
        video_data = {k: v for k, v in video_data.items() if v is not None}
        
        record = db_service.insert_record("video_assets", video_data)
        return record["id"], image_b64

    def initiate_video_remix(self, video_id: str, prompt: str, user_id: Optional[str]) -> str:
        """
        Initial entry point for video remixing. Creates a new DB record linked to the previous one if possible.
        """
        self.log_info(f"Initiating video remix for {video_id}")
        
        # Check if video_id is a DB ID (UUID) or OpenAI Job ID
        existing = None
        try:
            # Validate if it's a UUID before querying to avoid Supabase errors
            uuid.UUID(str(video_id))
            existing = db_service.get_record_by_id("video_assets", video_id)
        except (ValueError, AttributeError):
            self.log_info(f"{video_id} is not a UUID, assuming it's an OpenAI Job ID")
            existing = None
        
        video_data = {
            "title": "Remixed Video",
            "user_content": prompt,
            "status": "pending",
            "user_id": user_id,
            "image_url": existing.get("image_url") if existing else None
        }
        video_data = {k: v for k, v in video_data.items() if v is not None}
        
        record = db_service.insert_record("video_assets", video_data)
        return record["id"]

    def run_fashion_orchestration_flow(self, video_db_id: str, user_content: str, reference_image_b64: str, voice_over: bool, promo_vibe: str):
        """
        Orchestrates the 5-agent flow for Fashion video generation.
        Only one final DB update (success or failure) after the initial pending record.
        """
        try:
            self.log_info(f"Starting fashion orchestration flow for {video_db_id}")
            
            # Agent Chain
            self.log_info(f"[{video_db_id}] Step 1: Running Fashion Concept Agent")
            concept = self._run_fashion_concept_agent(user_content)
            
            self.log_info(f"[{video_db_id}] Step 2: Running Fashion Visual Agent")
            visuals = self._run_fashion_visual_agent(concept)
            
            self.log_info(f"[{video_db_id}] Step 3: Running Fashion Audio Agent")
            audio = self._run_fashion_audio_agent(concept, visuals, voice_over, promo_vibe)
            
            self.log_info(f"[{video_db_id}] Step 4: Running Fashion Assembly Agent")
            refined_prompt = self._run_fashion_assembly_agent(concept, visuals, audio)
            
            # QA Loop
            self.log_info(f"[{video_db_id}] Step 5: Running QA Loop")
            final_prompt, qa_res = self._run_qa_loop("Fashion QA Agent", refined_prompt, user_content, "fashion")
            
            # Moderation
            self.log_info(f"[{video_db_id}] Step 6: Checking Moderation")
            if openai_service.moderation_check(final_prompt):
                self.log_warning(f"[{video_db_id}] Fashion prompt flagged. Sanitizing...")
                final_prompt = self._sanitize_prompt(final_prompt)
            else:
                self.log_info(f"[{video_db_id}] Moderation check passed.")

            # Submit to OpenAI
            self.log_info(f"[{video_db_id}] Step 7: Submitting job to OpenAI")
            ref_bytes = process_and_resize_image(reference_image_b64)
            job_id = openai_service.create_video_job(final_prompt, ref_bytes)
            self.log_info(f"[{video_db_id}] OpenAI job created: {job_id}")
            
            # Orchestration finished, now start polling
            self.poll_and_save_video(video_db_id, job_id, final_prompt)
            
        except Exception as e:
            self.log_error(f"Fashion orchestration flow failed for {video_db_id}", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

    def run_promo_orchestration_flow(self, video_db_id: str, user_content: str, reference_image_b64: str, voice_over: bool, promo_vibe: str):
        """
        Orchestrates the 5-agent flow for Promotional video generation.
        Only one final DB update (success or failure) after the initial pending record.
        """
        try:
            self.log_info(f"Starting promo orchestration flow for {video_db_id}")
            
            # Agent Chain
            self.log_info(f"[{video_db_id}] Step 1: Running Promo Concept Agent")
            concept = self._run_promo_concept_agent(user_content)
            
            self.log_info(f"[{video_db_id}] Step 2: Running Promo Visual Agent")
            visuals = self._run_promo_visual_agent(concept)
            
            self.log_info(f"[{video_db_id}] Step 3: Running Promo Audio Agent")
            audio = self._run_promo_audio_agent(concept, visuals, voice_over, promo_vibe)
            
            self.log_info(f"[{video_db_id}] Step 4: Running Promo Assembly Agent")
            refined_prompt = self._run_promo_assembly_agent(concept, visuals, audio)
            
            # QA Loop
            self.log_info(f"[{video_db_id}] Step 5: Running QA Loop")
            final_prompt, qa_res = self._run_qa_loop("Promo QA Agent", refined_prompt, user_content, "promo")
            
            # Moderation
            self.log_info(f"[{video_db_id}] Step 6: Checking Moderation")
            if openai_service.moderation_check(final_prompt):
                self.log_warning(f"[{video_db_id}] Promo prompt flagged. Sanitizing...")
                final_prompt = self._sanitize_prompt(final_prompt)
            else:
                self.log_info(f"[{video_db_id}] Moderation check passed.")

            # Submit to OpenAI
            self.log_info(f"[{video_db_id}] Step 7: Submitting job to OpenAI")
            ref_bytes = process_and_resize_image(reference_image_b64)
            job_id = openai_service.create_video_job(final_prompt, ref_bytes)
            self.log_info(f"[{video_db_id}] OpenAI job created: {job_id}")
            
            # Start polling
            self.poll_and_save_video(video_db_id, job_id, final_prompt)
            
        except Exception as e:
            self.log_error(f"Promo orchestration flow failed for {video_db_id}", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

    # --- AGENT HELPERS ---

    def _run_fashion_concept_agent(self, user_content: str) -> str:
        prompt = """
        You are a Creative Director for High-End Fashion Films. 
        Interpret user content, extract garment details (color, fabric, cut) from the implied reference.
        HUMAN PRESENCE IS ALLOWED.
        Output JSON: narrative_concept, key_visuals, garment_details, character_direction, setting_biography, visual_style_guide.
        """
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}])
        self.log_info(f"Fashion Concept Agent Response: {res[:500]}...")
        return res

    def _run_fashion_visual_agent(self, concept: str) -> str:
        prompt = """
        You are a fashion cinematographer. Define 3-4 key shots for a 12s fashion video.
        Output JSON: shot_list, lighting_plan, color_grade, motion_dynamics.
        """
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": concept}])
        self.log_info(f"Fashion Visual Agent Response: {res[:500]}...")
        return res

    def _run_fashion_audio_agent(self, concept: str, visuals: str, voice_over: bool, vibe: str) -> str:
        prompt = f"You are a fashion sound designer. Define audio for a {vibe} film. {'Include 18-20 word script' if voice_over else 'No voiceover'}. Output JSON."
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": f"{concept}\n{visuals}"}])
        self.log_info(f"Fashion Audio Agent Response: {res[:500]}...")
        return res

    def _run_fashion_assembly_agent(self, concept: str, visuals: str, audio: str) -> str:
        prompt = """
        Assemble final SORA-2 prompt paragraph. PRIORITIZE USER CONTENT.
        
        STRICT RULES:
        1. Logical Consistency: Actions must be physically plausible and logically consistent for a fashion film.
        2. Narrative Completion: Ensure the visual sequence and script are fully completed before the video ends. No abrupt cuts.
        3. High-Fidelity Realism: Inject keywords like 'Arri Alexa RAW', '35mm format', 'subsurface scattering (SSS)', and 'volumetric lighting'.
        4. Reference Matching: Append 'REFERENCE IMAGE RULE: The product visual attributes must match reference exactly.'
        """
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": f"{concept}\n{visuals}\n{audio}"}])
        self.log_info(f"Fashion Assembly Agent Response: {res[:500]}...")
        return res

    def _run_promo_concept_agent(self, user_content: str) -> str:
        prompt = "Lead Promo Concept Analyst. ZERO HUMAN REFERENCES. Focus on PRODUCT ITSELF. Output JSON with product specs."
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": user_content}])
        self.log_info(f"Promo Concept Agent Response: {res[:500]}...")
        return res

    def _run_promo_visual_agent(self, concept: str) -> str:
        prompt = "Promo Visual Director. ZERO HUMAN REFERENCES. Define 3-5 camera shots for 12s commercial. Output JSON."
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": concept}])
        self.log_info(f"Promo Visual Agent Response: {res[:500]}...")
        return res

    def _run_promo_audio_agent(self, concept: str, visuals: str, voice_over: bool, vibe: str) -> str:
        prompt = f"Promo Script Writer. {'Include 18-20 word high-impact VO' if voice_over else 'No voiceover'}. TONE: {vibe}. Output JSON."
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": f"{concept}\n{visuals}"}])
        self.log_info(f"Promo Audio Agent Response: {res[:500]}...")
        return res

    def _run_promo_assembly_agent(self, concept: str, visuals: str, audio: str) -> str:
        prompt = """
        Assemble final SORA-2 prompt paragraph for PRODUCT-ONLY commercial. ZERO HUMAN REFERENCES.
        
        STRICT RULES:
        1. Logical Consistency: Product actions (rotations, slides, lighting shifts) must be physically plausible.
        2. Narrative Completion: The commercial must feel finished within 12 seconds. No unfinished motion or script.
        3. Cinematic Quality: Use 'Zeiss Master Prime look', 'ray-traced reflections', '8k photorealistic', and 'uncompressed RAW'.
        """
        res = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": prompt}, {"role": "user", "content": f"{concept}\n{visuals}\n{audio}"}])
        self.log_info(f"Promo Assembly Agent Response: {res[:500]}...")
        return res

    def _run_qa_loop(self, agent_role: str, initial_prompt: str, user_content: str, v_type: str) -> (str, Dict):
        qa_prompt = f"""
        You are a {v_type} quality controller for High-Fidelity cinematic content. Score 0-100. Need >= 88 to pass.
        Check for:
        - Cinematic Realism: Does it use technical terms like SSS, volumetric lighting, or RAW camera specs?
        - Logical Consistency: Are actions physically plausible?
        - Narrative Completion: Does the sequence end naturally (not abruptly)?
        - Alignment with user intent and reference rules.
        Return JSON: approved, score, violations, qa_summary.
        """
        current_prompt = initial_prompt
        
        for i in range(3):
            self.log_info(f"Running QA check (Attempt {i+1}/3)")
            qa_res_str = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": qa_prompt}, {"role": "user", "content": f"Prompt: {current_prompt}\nUser Content: {user_content}"}])
            self.log_info(f"QA Agent Response: {qa_res_str[:500]}...")
            qa_res = extract_json_from_text(qa_res_str)
            score = qa_res.get("score", 0)
            
            self.log_info(f"QA Score: {score}")
            if score >= 80:
                self.log_info("QA Passed.")
                return current_prompt, qa_res
                
            if i < 2:
                self.log_info(f"QA Failed. Violations: {qa_res.get('violations')}. Retrying improvement...")
                fix_prompt = f"Fix these violations: {json.dumps(qa_res.get('violations'))}. Return fixed prompt paragraph."
                current_prompt = openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": fix_prompt}, {"role": "user", "content": current_prompt}])
                self.log_info(f"QA Improvement Response: {current_prompt[:500]}...")
        
        self.log_warning(f"QA Loop finished after 3 attempts with final score {score}.")
        return current_prompt, qa_res

    def _sanitize_prompt(self, prompt: str) -> str:
        self.log_info("Sanitizing prompt for moderation safety.")
        fixer_prompt = "Rewrite this video prompt to be 100% safe for work. Focus on clothes/product and artistic composition. Remove suggestive content."
        return openai_service.chat_completion("gpt-4o-mini", [{"role": "system", "content": fixer_prompt}, {"role": "user", "content": prompt}])

    def _generate_creative_title(self, prompt: str) -> str:
        """Generates a catchy title from the prompt."""
        self.log_info("Generating creative title from prompt.")
        messages = [
            {"role": "system", "content": "You are a creative writer. Generate a short, catchy, 3-5 word title for creative content based on the provided prompt. Return only the title text."},
            {"role": "user", "content": prompt}
        ]
        return openai_service.chat_completion(model="gpt-4o-mini", messages=messages)

    # --- REMIX WORKFLOW ---
    
    def run_remix_orchestration_flow(self, video_db_id: str, original_job_id: str, prompt: str):
        """
        Orchestrates the video remix flow.
        """
        try:
            self.log_info(f"Starting remix flow for {video_db_id} (Original Job: {original_job_id})")
            
            # 1. Moderation Check
            if openai_service.moderation_check(prompt):
                raise ModerationError("Remix prompt flagged by moderation")
            
            # 2. Create Remix Job
            job_id = openai_service.remix_video_job(original_job_id, prompt)
            self.log_info(f"[{video_db_id}] Remix job created: {job_id}")
            
            # 3. Poll and Save (with local storage)
            self.poll_and_save_remix(video_db_id, job_id, prompt)
            
        except Exception as e:
            self.log_error(f"Remix flow failed for {video_db_id}", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

    def poll_and_save_remix(self, video_db_id: str, job_id: str, video_prompt: str):
        """
        Polls for remix status and saves to DB, storage, AND local device.
        """
        try:
            start_time = time.time()
            max_wait = self.settings.POLL_MAX_MIN * 60
            
            while time.time() - start_time < max_wait:
                status_data = openai_service.get_video_job_status(job_id)
                status = status_data.get("status")
                self.log_info(f"[{video_db_id}] Remix status: {status}...")
                
                if status == "completed":
                    self.log_info(f"[{video_db_id}] Remix completed. Downloading...")
                    
                    # 1. Download
                    video_bytes = openai_service.download_video_content(job_id)
                    
                    # 2. Save locally
                    local_dir = os.path.join(os.getcwd(), "remixes")
                    if not os.path.exists(local_dir):
                        os.makedirs(local_dir)
                    local_path = os.path.join(local_dir, f"{video_db_id}.mp4")
                    with open(local_path, "wb") as f:
                        f.write(video_bytes)
                    self.log_info(f"[{video_db_id}] Remixed video saved locally at: {local_path}")
                    
                    # 3. Upload to Supabase
                    storage_url = db_service.upload_file(
                        bucket_name="ai_videos",
                        file_path=f"remix_{video_db_id}.mp4",
                        file_content=video_bytes,
                        content_type="video/mp4"
                    )
                    
                    # 4. Update DB
                    db_service.update_record("video_assets", video_db_id, {
                        "status": "completed",
                        "video_url": storage_url,
                        "video_prompt": video_prompt,
                        "title": "Remixed Video"
                    })
                    return
                
                elif status == "failed":
                    error = status_data.get("error", "Unknown error")
                    raise AIServiceError(f"OpenAI remix job failed: {error}")
                
                time.sleep(self.settings.POLL_INTERVAL_SEC)
                
            raise AIServiceError("Remix polling timed out")
            
        except Exception as e:
            self.log_error(f"[{video_db_id}] Remix polling/saving failed", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

    # --- POLLING & STATUS ---

    def poll_and_save_video(self, video_db_id: str, job_id: str, video_prompt: str):
        """
        Polls OpenAI for video status and updates DB.
        Schema: status, video_url, title.
        """
        try:
            start_time = time.time()
            max_wait = self.settings.POLL_MAX_MIN * 60
            
            while time.time() - start_time < max_wait:
                status_data = openai_service.get_video_job_status(job_id)
                status = status_data.get("status")
                self.log_info(f"[{video_db_id}] Video status: {status}...")
                
                if status == "completed":
                    self.log_info(f"[{video_db_id}] Video generation completed. Downloading content...")
                    
                    try:
                        # 1. Download video content
                        video_bytes = openai_service.download_video_content(job_id)
                        
                        # 2. Upload to Supabase Storage
                        file_path = f"{video_db_id}.mp4"
                        self.log_info(f"[{video_db_id}] Uploading video to Supabase storage...")
                        storage_url = db_service.upload_file(
                            bucket_name="ai_videos",
                            file_path=file_path,
                            file_content=video_bytes,
                            content_type="video/mp4"
                        )
                        
                        # 3. Generate catchy title
                        try:
                            title = self._generate_creative_title(video_prompt)
                        except Exception as title_err:
                            self.log_warning(f"[{video_db_id}] Failed to generate catchy title: {str(title_err)}. Using default.")
                            title = "Generated Video"

                        # 4. Final DB Update
                        self.log_info(f"[{video_db_id}] Finalizing DB record with storage URL: {storage_url}")
                        db_service.update_record("video_assets", video_db_id, {
                            "status": "completed", 
                            "video_url": storage_url,
                            "video_prompt": video_prompt,
                            "title": title
                        })
                        self.log_info(f"[{video_db_id}] Workflow finished successfully.")
                        
                    except Exception as download_err:
                        self.log_error(f"[{video_db_id}] Failed to download or upload video content", download_err)
                        db_service.update_record("video_assets", video_db_id, {
                            "status": "failed",
                            "error_message": f"Video storage failed: {str(download_err)}"
                        })
                    return
                
                elif status == "failed":
                    error = status_data.get("error", "Unknown error")
                    self.log_error(f"[{video_db_id}] OpenAI job failed: {error}")
                    db_service.update_record("video_assets", video_db_id, {
                        "status": "failed", 
                        "error_message": str(error),
                        "video_prompt": video_prompt
                    })
                    return
                
                time.sleep(self.settings.POLL_INTERVAL_SEC)
            
            self.log_error(f"[{video_db_id}] Polling timed out after {self.settings.POLL_MAX_MIN} minutes.")
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": "Timed out"})
        except Exception as e:
            self.log_error(f"[{video_db_id}] Polling failed for job {job_id}", e)
            db_service.update_record("video_assets", video_db_id, {"status": "failed", "error_message": str(e)})

orchestrator = OrchestrationService()
