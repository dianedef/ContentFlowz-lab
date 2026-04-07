"""Content template management and AI generation endpoints."""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from typing import Dict, Any, Optional
from datetime import datetime
import uuid
import json
import os

from api.models.templates import (
    GeneratePromptRequest,
    GeneratePromptResponse,
    GenerateContentRequest,
    GenerateContentResponse,
)
from api.dependencies.auth import require_current_user
from api.services.job_store import job_store
from api.services.template_defaults import get_default_templates

router = APIRouter(
    prefix="/api/templates",
    tags=["Templates"],
    dependencies=[Depends(require_current_user)],
)


JOB_TYPE = "content_generation"


@router.get(
    "/defaults",
    summary="Get default system templates",
    description="Returns the 4 built-in system templates (SEO article, newsletter, YouTube, short-form)",
)
async def get_defaults():
    """Return default system templates that users can clone and customize."""
    templates = get_default_templates()
    return [t.model_dump() for t in templates]


@router.post(
    "/generate-prompt",
    response_model=GeneratePromptResponse,
    summary="Generate AI prompt for a section",
    description="Uses LLM to generate an optimized prompt for a template section",
)
async def generate_prompt(request: GeneratePromptRequest):
    """
    Generate a smart AI prompt for a specific template section.

    Takes into account the template context (content type, other sections)
    to generate a targeted, effective prompt.
    """
    try:
        prompt = await _generate_section_prompt(request)
        return prompt
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Prompt generation failed: {str(e)}",
        )


@router.post(
    "/generate-content",
    summary="Generate content using a template",
    description="Generates full content using the hybrid pipeline (metadata → body → links/tags)",
)
async def generate_content(
    request: GenerateContentRequest,
    background_tasks: BackgroundTasks,
):
    """
    Start content generation as a background job using the hybrid pipeline.

    Pipeline:
    1. Pass 1 — Metadata: title, keywords, meta_description, entities
    2. Pass 2 — Body: intro, body sections, script using metadata context
    3. Pass 3 — Links/Tags: internal links, tags, CTAs using full content
    """
    job_id = str(uuid.uuid4())[:8]

    job = await job_store.upsert(
        job_id, JOB_TYPE, status="pending", progress=0, message="Job queued",
    )

    background_tasks.add_task(_run_content_generation, job_id, request)

    return job


@router.get(
    "/generate-content/{job_id}",
    summary="Check content generation status",
)
async def get_generation_status(job_id: str):
    """Check the status of a content generation job."""
    job = await job_store.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
    return job


# ─── Internal helpers ─────────────────────────────────────────────


def _get_llm_client():
    """Get an OpenRouter LLM client for generation."""
    openrouter_key = os.environ.get("OPENROUTER_API_KEY")
    if not openrouter_key:
        raise ValueError("No LLM API key found. Set OPENROUTER_API_KEY.")

    from openai import OpenAI
    return OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=openrouter_key,
    )


def _llm_call(system_prompt: str, user_prompt: str, model: str | None = None, temperature: float = 0.7) -> str:
    """Make a single LLM call via OpenRouter."""
    client = _get_llm_client()

    response = client.chat.completions.create(
        model=model or "anthropic/claude-sonnet-4-5",
        temperature=temperature,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
    )
    return response.choices[0].message.content


async def _generate_section_prompt(request: GeneratePromptRequest) -> GeneratePromptResponse:
    """Generate an optimized AI prompt for a template section."""
    sibling_context = ""
    if request.other_sections:
        siblings = ", ".join(
            f"{s.get('label', s.get('name', '?'))} ({s.get('fieldType', 'text')})"
            for s in request.other_sections
        )
        sibling_context = f"\nOther sections in this template: {siblings}"

    system_prompt = """You are an expert prompt engineer specializing in content creation prompts.
Your job is to write clear, specific AI prompts that produce high-quality content.

Rules:
- Be specific about format, length, and quality criteria
- Include the content type's best practices
- Reference the section's role within the broader template
- Use clear instructions, not vague guidance
- Include examples of good output where helpful"""

    user_prompt = f"""Generate an optimized AI prompt for this template section:

Template: {request.template_name} ({request.content_type})
Section: {request.section_label} (field type: {request.section_field_type})
Section name: {request.section_name}
{f'Description: {request.section_description}' if request.section_description else ''}
{sibling_context}

Write a prompt that will produce excellent {request.section_field_type} content for this section.
Return ONLY the prompt text, nothing else."""

    result = _llm_call(system_prompt, user_prompt, temperature=0.7)

    return GeneratePromptResponse(
        prompt=result.strip(),
        reasoning=f"Generated for {request.content_type} template, section '{request.section_label}' ({request.section_field_type})",
    )


async def _run_content_generation(job_id: str, request: GenerateContentRequest):
    """Execute the 3-pass hybrid content generation pipeline."""
    try:
        await job_store.update(job_id, status="running", progress=5, message="Preparing template...")

        template = request.template
        sections = template.get("sections", [])
        context = request.context
        user_inputs = request.user_inputs

        # Categorize sections into generation passes
        metadata_fields = {"title", "target_keyword", "meta_description", "semantic_entities", "subject_line", "preview_text", "thumbnail_text"}
        link_fields = {"internal_links", "tags", "hashtags", "cta"}

        metadata_sections = []
        body_sections = []
        link_sections = []

        for s in sections:
            name = s.get("name", "")
            if name in user_inputs and user_inputs[name]:
                continue  # Skip sections the user already filled in
            if name in metadata_fields:
                metadata_sections.append(s)
            elif name in link_fields:
                link_sections.append(s)
            else:
                body_sections.append(s)

        generated = dict(user_inputs)  # Start with user-provided values
        template_name = template.get("name", "Content")
        content_type = template.get("contentType", template.get("content_type", "article"))

        # ─── Pass 1: Metadata ───────────────────────────────────
        if metadata_sections:
            await job_store.update(job_id, progress=15, message="Generating metadata (pass 1/3)...")

            metadata_result = _generate_pass(
                template_name=template_name,
                content_type=content_type,
                sections=metadata_sections,
                context=context,
                prior_generated={},
            )
            generated.update(metadata_result)

        # ─── Pass 2: Body ──────────────────────────────────────
        if body_sections:
            await job_store.update(job_id, progress=45, message="Generating content body (pass 2/3)...")

            body_result = _generate_pass(
                template_name=template_name,
                content_type=content_type,
                sections=body_sections,
                context=context,
                prior_generated=generated,
            )
            generated.update(body_result)

        # ─── Pass 3: Links/Tags ────────────────────────────────
        if link_sections:
            await job_store.update(job_id, progress=75, message="Generating links and tags (pass 3/3)...")

            link_result = _generate_pass(
                template_name=template_name,
                content_type=content_type,
                sections=link_sections,
                context=context,
                prior_generated=generated,
            )
            generated.update(link_result)

        # ─── Create ContentRecord ──────────────────────────────
        await job_store.update(job_id, progress=90, message="Saving content record...")

        content_record_id = None
        try:
            content_record_id = _create_content_record(
                generated=generated,
                template=template,
                context=context,
                project_id=request.project_id,
            )
        except Exception as e:
            print(f"Warning: Failed to create content record: {e}")

        await job_store.update(
            job_id,
            status="completed",
            progress=100,
            message="Content generated successfully",
            result={
                "sections": generated,
                "metadata": {
                    "template_name": template_name,
                    "content_type": content_type,
                    "passes": 3,
                    "generated_at": datetime.now().isoformat(),
                },
                "content_record_id": content_record_id,
            },
        )

    except Exception as e:
        import logging
        logging.getLogger("api.templates").exception("Content generation failed for job %s", job_id)
        await job_store.update(job_id, status="failed", message=str(e))


def _generate_pass(
    template_name: str,
    content_type: str,
    sections: list[dict],
    context: dict,
    prior_generated: dict,
) -> dict:
    """Generate content for a batch of sections in one LLM call."""
    context_str = ""
    if context:
        parts = []
        for k, v in context.items():
            if v:
                parts.append(f"- {k}: {v}")
        if parts:
            context_str = "Context:\n" + "\n".join(parts)

    prior_str = ""
    if prior_generated:
        parts = []
        for k, v in prior_generated.items():
            if v:
                preview = str(v)[:300]
                parts.append(f"- {k}: {preview}")
        if parts:
            prior_str = "\nAlready generated content:\n" + "\n".join(parts)

    section_instructions = []
    for s in sections:
        prompt = s.get("userPrompt") or s.get("user_prompt") or s.get("defaultPrompt") or s.get("default_prompt") or f"Generate content for the {s.get('label', s.get('name', 'section'))} section."
        field_type = s.get("fieldType") or s.get("field_type", "text")
        name = s.get("name", "unnamed")
        label = s.get("label", name)

        type_hint = ""
        if field_type == "tags":
            type_hint = " (return as JSON array of strings)"
        elif field_type == "list":
            type_hint = " (return as JSON array of strings or objects)"
        elif field_type == "number":
            type_hint = " (return as a number)"
        elif field_type == "image":
            type_hint = " (return a detailed image generation prompt describing the visual: subject, style, composition, colors, mood)"

        section_instructions.append(
            f'### {name}\nLabel: {label}\nType: {field_type}{type_hint}\nPrompt: {prompt}'
        )

    system_prompt = f"""You are a professional content creator generating a {content_type} using the "{template_name}" template.

Generate content for each requested section. Return valid JSON with section names as keys.

Rules:
- Follow each section's prompt instructions precisely
- Match the field type requirements (text = plain string, markdown = formatted markdown, tags = JSON array, list = JSON array, number = numeric value)
- Maintain consistency across sections
- Use the provided context and already-generated content for coherence
- Return ONLY valid JSON, no markdown code fences"""

    user_prompt = f"""{context_str}
{prior_str}

Generate content for these sections:

{chr(10).join(section_instructions)}

Return as JSON object with section names as keys. Example: {{"section_name": "content..."}}"""

    result_text = _llm_call(system_prompt, user_prompt, temperature=0.7)

    # Parse JSON from response
    try:
        # Strip markdown code fences if present
        cleaned = result_text.strip()
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            cleaned = "\n".join(lines[1:])
            if cleaned.endswith("```"):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()

        return json.loads(cleaned)
    except json.JSONDecodeError:
        # Fallback: try to extract JSON from the response
        import re
        json_match = re.search(r'\{[\s\S]*\}', result_text)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Last resort: return raw text for each section
        return {s.get("name", f"section_{i}"): result_text for i, s in enumerate(sections)}


def _create_content_record(
    generated: dict,
    template: dict,
    context: dict,
    project_id: str | None,
) -> str | None:
    """Create a ContentRecord + ContentBody in the local SQLite status DB."""
    try:
        from status.service import StatusService

        svc = StatusService()
        content_type = template.get("contentType", template.get("content_type", "article"))
        title = generated.get("title") or generated.get("subject_line") or context.get("topic", "Generated Content")

        # Build preview from available text fields
        preview_parts = []
        for key in ["introduction", "script_body", "sections", "body_sections"]:
            if key in generated and generated[key]:
                val = str(generated[key])[:500]
                preview_parts.append(val)
                break

        preview = preview_parts[0] if preview_parts else str(title)[:200]

        record = svc.create_content(
            title=str(title) if isinstance(title, str) else title[0] if isinstance(title, list) else str(title),
            content_type=content_type,
            source_robot="manual",
            status="generated",
            project_id=project_id,
            content_preview=preview[:500],
            metadata={
                "template_name": template.get("name", ""),
                "template_slug": template.get("slug", ""),
                "context": context,
            },
        )

        # Save the full generated content as body
        body_content = json.dumps(generated, indent=2, ensure_ascii=False)
        svc.save_content_body(
            content_id=record["id"],
            body=body_content,
            edited_by="template-generator",
            edit_note=f"Generated via {template.get('name', 'template')}",
        )

        # Transition to pending_review
        svc.transition(
            content_id=record["id"],
            to_status="pending_review",
            changed_by="template-generator",
        )

        return record["id"]

    except Exception as e:
        print(f"Warning: Content record creation failed: {e}")
        return None
