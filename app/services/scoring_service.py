import os
import sys
import uuid
import base64

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from app.services.qwen_service import call_qwen_for_json, client, QWEN_MODEL
from app.services.practice_service import get_rubric_summary
from app.utils.json_utils import safe_parse_json, extract_json_from_text

OSS_ACCESS_KEY_ID     = os.getenv("OSS_ACCESS_KEY_ID")
OSS_ACCESS_KEY_SECRET = os.getenv("OSS_ACCESS_KEY_SECRET")
OSS_BUCKET            = os.getenv("OSS_BUCKET", "ielts-memorycoach-audio")
OSS_ENDPOINT          = os.getenv("OSS_ENDPOINT", "oss-ap-southeast-1.aliyuncs.com")


def _upload_image_to_oss(image_bytes: bytes, media_type: str) -> tuple[str, str]:
    """Upload image to OSS and return (public_url, object_key) for later deletion."""
    import oss2
    ext = media_type.split("/")[-1].replace("jpeg", "jpg")
    key = f"tmp-essay-images/{uuid.uuid4()}.{ext}"
    auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
    bucket = oss2.Bucket(auth, f"https://{OSS_ENDPOINT}", OSS_BUCKET)
    bucket.put_object(
        key, image_bytes,
        headers={"Content-Type": media_type, "x-oss-object-acl": "public-read"},
    )
    url = f"https://{OSS_BUCKET}.{OSS_ENDPOINT}/{key}"
    return url, key


def _delete_oss_object(key: str):
    """Delete a temporary OSS object after Qwen VL has processed it."""
    try:
        import oss2
        auth = oss2.Auth(OSS_ACCESS_KEY_ID, OSS_ACCESS_KEY_SECRET)
        bucket = oss2.Bucket(auth, f"https://{OSS_ENDPOINT}", OSS_BUCKET)
        bucket.delete_object(key)
    except Exception:
        pass

PROMPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts")


def load_prompt_template(filename: str) -> str:
    path = os.path.join(PROMPTS_DIR, filename)
    with open(path, "r") as f:
        return f.read()


def format_memories_for_prompt(memories: list) -> str:
    if not memories:
        return "No previous memories exist for this learner. This may be their first attempt."

    lines = []
    weaknesses = [m for m in memories if m["memory_type"] == "weakness"]
    strengths = [m for m in memories if m["memory_type"] == "strength"]

    if weaknesses:
        lines.append("Previously observed WEAKNESSES:")
        for mem in weaknesses:
            confidence_pct = int(mem["confidence"] * 100)
            evidence = mem["evidence_count"]
            lines.append(
                f"  - [{mem['skill']}] {mem['memory_text']} "
                f"(confidence: {confidence_pct}%, seen across {evidence} attempt(s))"
            )

    if strengths:
        lines.append("\nPreviously observed STRENGTHS:")
        for mem in strengths:
            lines.append(f"  - [{mem['skill']}] {mem['memory_text']}")

    return "\n".join(lines)


def evaluate_writing(prompt: str, essay: str, memories: list = None) -> dict:
    """
    Evaluates a learner's essay against an IELTS writing prompt.
    Text-only path — used by the standard submission flow.
    """
    if memories is None:
        memories = []

    rubric = get_rubric_summary("Writing")
    memory_context = format_memories_for_prompt(memories)

    template = load_prompt_template("writing_evaluator_prompt.txt")
    full_prompt = template.format(
        memory_context=memory_context,
        prompt=prompt,
        essay=essay,
        rubric=rubric
    )

    raw_response = call_qwen_for_json(full_prompt)

    try:
        result = safe_parse_json(raw_response)
    except ValueError:
        try:
            from app.services.qwen_service import fix_broken_json
            fixed_response = fix_broken_json(raw_response)
            result = safe_parse_json(fixed_response)
        except ValueError as e:
            raise Exception(f"Failed to parse scoring response: {e}")

    required_fields = ["overall_feedback", "scores", "strengths",
                       "weaknesses", "recommended_next_step"]
    for field in required_fields:
        if field not in result:
            raise Exception(f"Qwen response missing required field: '{field}'")

    return result


def extract_text_from_image(image_bytes: bytes, media_type: str = "image/jpeg") -> dict:
    """
    Uses qwen-vl-plus to extract handwritten essay text from an image.

    Accepts raw image bytes and returns the extracted text along with
    a confidence indicator. This is the first step in the image
    submission pipeline — the extracted text then flows through the
    normal evaluate_writing() path.

    Args:
        image_bytes: Raw image bytes (JPEG, PNG, WebP)
        media_type:  MIME type of the image

    Returns:
        {
            "success": bool,
            "extracted_text": str,   — the transcribed essay text
            "word_count": int,
            "confidence": str,       — "high", "medium", "low"
            "notes": str,            — any issues the model flagged
            "error": str | None
        }
    """
    oss_key = None
    try:
        # Upload to OSS so DashScope VL endpoint receives an https:// URL
        image_url, oss_key = _upload_image_to_oss(image_bytes, media_type)

        response = client.chat.completions.create(
            model="qwen-vl-plus",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {"url": image_url}
                        },
                        {
                            "type": "text",
                            "text": (
                                "This image contains a handwritten IELTS Writing Task 2 essay. "
                                "Please transcribe the full text exactly as written, preserving "
                                "all paragraphs and line breaks. "
                                "Do not correct spelling or grammar — transcribe exactly what is written. "
                                "After the transcription, on a new line write: "
                                "CONFIDENCE: high/medium/low "
                                "NOTES: [any issues with legibility or completeness]"
                            )
                        }
                    ]
                }
            ],
            max_tokens=2000,
            temperature=0.1
        )

        raw_text = response.choices[0].message.content or ""

        # Parse the structured response
        extracted_text = raw_text
        confidence = "medium"
        notes = ""

        if "CONFIDENCE:" in raw_text:
            parts = raw_text.split("CONFIDENCE:")
            extracted_text = parts[0].strip()
            meta = parts[1].strip()

            # Extract confidence level
            if meta.lower().startswith("high"):
                confidence = "high"
            elif meta.lower().startswith("low"):
                confidence = "low"
            else:
                confidence = "medium"

            # Extract notes
            if "NOTES:" in meta:
                notes = meta.split("NOTES:")[1].strip()

        word_count = len(extracted_text.split()) if extracted_text else 0

        return {
            "success": True,
            "extracted_text": extracted_text,
            "word_count": word_count,
            "confidence": confidence,
            "notes": notes,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "extracted_text": "",
            "word_count": 0,
            "confidence": "low",
            "notes": "",
            "error": str(e)
        }
    finally:
        if oss_key:
            _delete_oss_object(oss_key)


def evaluate_writing_from_image(
    image_bytes: bytes,
    media_type: str,
    prompt: str,
    memories: list = None
) -> dict:
    """
    Full pipeline for handwritten essay submission via image.

    Step 1: qwen-vl-plus extracts the essay text from the image
    Step 2: Extracted text flows through standard evaluate_writing()

    Returns the standard evaluation result dict plus:
        extracted_text: the text qwen-vl extracted
        extraction_confidence: high/medium/low
        extraction_notes: any legibility issues flagged
    """
    # Step 1 — extract text
    extraction = extract_text_from_image(image_bytes, media_type)

    if not extraction["success"] or not extraction["extracted_text"]:
        raise Exception(
            f"Could not extract text from image: "
            f"{extraction.get('error', 'No text found')}"
        )

    extracted_text = extraction["extracted_text"]

    if extraction["word_count"] < 50:
        raise Exception(
            f"Extracted text is too short ({extraction['word_count']} words). "
            f"Please ensure the image is clear and the full essay is visible."
        )

    # Step 2 — evaluate as normal
    result = evaluate_writing(
        prompt=prompt,
        essay=extracted_text,
        memories=memories or []
    )

    # Attach extraction metadata to result
    result["extracted_text"] = extracted_text
    result["extraction_confidence"] = extraction["confidence"]
    result["extraction_notes"] = extraction["notes"]
    result["word_count"] = extraction["word_count"]

    return result


def get_cross_section_insights(learner_id: str) -> dict:
    """
    Identifies skill patterns that appear across multiple IELTS sections.

    For example, if a learner struggles with inference in both Reading
    and Listening, that is a core comprehension gap — not section-specific.
    Surfacing this gives the learner and tutor a higher-level view of
    what to focus on.

    Returns:
        {
            "has_insights": bool,
            "cross_section_patterns": [
                {
                    "pattern": str,           — human-readable description
                    "sections_affected": list, — e.g. ["Reading", "Listening"]
                    "skill_theme": str,        — e.g. "inference"
                    "severity": str,           — "high", "medium", "low"
                    "recommendation": str
                }
            ],
            "section_bands": {
                "Writing": 6.0,
                "Reading": 5.5,
                "Speaking": None,
                "Listening": 6.5
            },
            "overall_band": float | None,
            "strongest_section": str | None,
            "weakest_section": str | None
        }
    """
    from app.services.memory_service import get_relevant_memories, get_all_skill_ranks
    from app.services.skill_taxonomy_service import get_band_estimate, format_band

    sections = ["Writing", "Reading", "Speaking", "Listening"]

    # ── Collect section bands ────────────────────────────────────────────────
    section_bands = {}
    for section in sections:
        try:
            ranks = get_all_skill_ranks(learner_id, section)
            assessed = [r for r in ranks if r.get("total_evidence", 0) > 0]
            if not assessed:
                section_bands[section] = None
                continue
            valid_bands = [r["band"] for r in assessed if r.get("band") is not None]
            if valid_bands:
                avg = sum(valid_bands) / len(valid_bands)
                section_bands[section] = round(avg * 2) / 2
            else:
                section_bands[section] = None
        except Exception:
            section_bands[section] = None

    # ── Overall band ─────────────────────────────────────────────────────────
    valid_section_bands = [b for b in section_bands.values() if b is not None]
    overall_band = None
    if valid_section_bands:
        overall_band = round((sum(valid_section_bands) / len(valid_section_bands)) * 2) / 2

    # ── Strongest / weakest section ──────────────────────────────────────────
    assessed_sections = {s: b for s, b in section_bands.items() if b is not None}
    strongest_section = max(assessed_sections, key=assessed_sections.get) if assessed_sections else None
    weakest_section = min(assessed_sections, key=assessed_sections.get) if assessed_sections else None

    # ── Cross-section patterns ───────────────────────────────────────────────
    # Collect weakness memories per section, grouped by skill theme
    theme_map = {}  # theme → {section: [memory_texts]}

    SKILL_THEMES = {
        "inference": ["inference", "implied", "infer", "deduce"],
        "main idea": ["main idea", "gist", "central", "purpose", "argument"],
        "vocabulary": ["vocabulary", "word choice", "lexical", "precision"],
        "grammar": ["grammar", "grammatical", "sentence structure", "accuracy"],
        "organization": ["organization", "coherence", "structure", "paragraphing"],
        "detail accuracy": ["detail", "accuracy", "specific", "facts", "numbers"],
        "fluency": ["fluency", "hesitation", "fluent", "pace"],
    }

    for section in sections:
        try:
            memories = get_relevant_memories(learner_id, section=section, limit=10)
            weaknesses = [m for m in memories if m["memory_type"] == "weakness"]

            for mem in weaknesses:
                text_lower = mem["memory_text"].lower()
                skill_lower = mem["skill"].lower()
                combined = text_lower + " " + skill_lower

                for theme, keywords in SKILL_THEMES.items():
                    if any(kw in combined for kw in keywords):
                        if theme not in theme_map:
                            theme_map[theme] = {}
                        if section not in theme_map[theme]:
                            theme_map[theme][section] = []
                        theme_map[theme][section].append(mem["memory_text"])
        except Exception:
            continue

    # ── Build patterns where theme appears in 2+ sections ────────────────────
    patterns = []
    for theme, section_data in theme_map.items():
        if len(section_data) < 2:
            continue  # single-section issue — not a cross-section pattern

        sections_affected = list(section_data.keys())
        severity = "high" if len(sections_affected) >= 3 else "medium"

        # Build a concise description
        section_list = " and ".join(sections_affected)
        pattern_desc = (
            f"Consistent weakness in {theme} across {section_list}. "
            f"This suggests a core skill gap rather than a section-specific issue."
        )

        recommendation = _get_cross_section_recommendation(theme, sections_affected)

        patterns.append({
            "pattern": pattern_desc,
            "sections_affected": sections_affected,
            "skill_theme": theme,
            "severity": severity,
            "recommendation": recommendation
        })

    # Sort by severity then number of sections affected
    patterns.sort(
        key=lambda p: (
            0 if p["severity"] == "high" else 1,
            -len(p["sections_affected"])
        )
    )

    return {
        "has_insights": len(patterns) > 0 or len(assessed_sections) > 0,
        "cross_section_patterns": patterns,
        "section_bands": section_bands,
        "overall_band": overall_band,
        "overall_band_display": format_band(overall_band),
        "strongest_section": strongest_section,
        "weakest_section": weakest_section,
        "sections_assessed": len(assessed_sections)
    }


def _get_cross_section_recommendation(theme: str, sections: list) -> str:
    """Returns a targeted recommendation for a cross-section pattern."""
    recommendations = {
        "inference": (
            "Focus on reading between the lines — practise identifying what is "
            "implied rather than stated. The IELTS Tutor can run targeted "
            "inference drills across both Reading and Listening contexts."
        ),
        "main idea": (
            "Practise summarising the central argument of any text or audio in "
            "one sentence before answering questions. This skill transfers across "
            "all four IELTS sections."
        ),
        "vocabulary": (
            "Build a topic-specific vocabulary bank. Focus on paraphrasing — "
            "the ability to express the same idea in different words is tested "
            "across Writing, Speaking, Reading and Listening."
        ),
        "grammar": (
            "Prioritise grammatical accuracy in both written and spoken output. "
            "Errors in grammar affect both Writing and Speaking band scores directly."
        ),
        "organization": (
            "Practise structuring responses with a clear beginning, middle and end. "
            "Coherence is assessed in both Writing (Coherence & Cohesion criterion) "
            "and Speaking (Fluency & Coherence criterion)."
        ),
        "detail accuracy": (
            "Train focused attention on specific details. In Listening, practise "
            "note-taking. In Reading, practise scanning for exact information "
            "rather than paraphrased meaning."
        ),
        "fluency": (
            "Practise extended speaking on unfamiliar topics to build fluency. "
            "Regular Speaking Coach sessions will help reduce hesitation and "
            "build confidence with complex topics."
        ),
    }
    return recommendations.get(
        theme,
        f"Work with your IELTS Tutor on {theme} — it appears across "
        f"{', '.join(sections)} and addressing it will improve multiple scores simultaneously."
    )
