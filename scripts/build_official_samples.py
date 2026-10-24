"""
Build an examiner-marked sanity set from the official IELTS Writing sample PDFs.

Source PDFs (download from ielts.org into <data>/download/):
  https://ielts.org/cdn/Sample-tests/ielts-academic-writing-sample-tasks-2023.pdf
  https://ielts.org/cdn/Sample-tests/ielts-general-training-writing-sample-tasks-2023.pdf

For each Task 2 sample script this finds the pages, the published examiner
band and the task prompt from the PDF text layer, crops each handwritten page
to the candidate's writing, and transcribes it with the app's own handwriting
path (qwen-vl-plus via a private OSS pre-signed URL). Crops are saved to
<data>/crops/ so transcriptions can be spot-checked.

IELTS copyright material: internal evaluation only, kept in the git-ignored
data folder. Examiner bands are overall only (no criterion bands are published),
and these scripts may be in the model's training data — treat results as a
sanity check, not a measure of accuracy.

    docker exec ielts-api-dev python scripts/build_official_samples.py evaluation/writing/data/official
"""
import csv
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import pymupdf as fitz  # noqa: E402  (from requirements-dev.txt)

SCRIPT_TITLE = re.compile(r"Sample Task\s*[–-]?\s*2([AB])\s*[–-]\s*Sample\s*Script\s*([A-D])")
PROMPT_PAGE = re.compile(r"Sample Task\s*[–-]?\s*2([AB])\s+WRITING TASK 2")
EXAMINER_BAND = re.compile(r"Examiner comment\s*Band\s*([0-9](?:\.5)?)")
# Instruction boilerplate around the question; its position differs between the PDFs
BOILERPLATE = re.compile(
    r"Give reasons for your answer and include any relevant examples from your own knowledge or experience\.?"
    r"|Write at least 250 words\.?"
)
MIN_REGION_HEIGHT = 100  # blank top margins on comment-only pages are ~70pt
RENDER_DPI = 150


def _norm(text: str) -> str:
    return " ".join(text.split())


def find_task2_scripts(doc) -> tuple[dict, dict]:
    """Returns ({task_letter: prompt}, {(task, script): {"pages": [...], "band": float}})."""
    prompts, scripts, current = {}, {}, None
    for pno, page in enumerate(doc):
        text = _norm(page.get_text())
        prompt_match = PROMPT_PAGE.search(text)
        if prompt_match and "Sample Script" not in text:
            body = text.split("Write about the following topic:")[-1]
            prompts[prompt_match.group(1)] = _norm(BOILERPLATE.sub(" ", body))
            continue
        title = SCRIPT_TITLE.search(text)
        if title:
            current = (title.group(1), title.group(2))
            scripts[current] = {"pages": [pno], "band": None}
        elif current:
            scripts[current]["pages"].append(pno)
        band = EXAMINER_BAND.search(text)
        if band and current:
            scripts[current]["band"] = float(band.group(1))
            current = None
    return prompts, {k: v for k, v in scripts.items() if v["band"] is not None}


def candidate_region(page) -> "fitz.Rect | None":
    """
    The handwritten area: below the page title, above the examiner comment and
    footer. None when nothing is left (a page holding only the examiner comment).
    """
    rect = page.rect
    top, bottom = rect.y0, rect.y1
    for hit in page.search_for("Sample Script") + page.search_for("Script"):
        if hit.y1 < rect.height * 0.25:
            top = max(top, hit.y1 + 4)
    for hit in page.search_for("Examiner comment"):  # wherever it is on the page
        bottom = min(bottom, hit.y0 - 4)
    for marker in ("IELTS.org", "Page "):
        for hit in page.search_for(marker):
            if hit.y0 > rect.height * 0.5:
                bottom = min(bottom, hit.y0 - 4)
    if bottom - top < MIN_REGION_HEIGHT:
        return None
    return fitz.Rect(rect.x0, top, rect.x1, bottom)


def main(data_dir: str) -> None:
    from app.services.scoring_service import extract_text_from_image

    download = os.path.join(data_dir, "download")
    crops_dir = os.path.join(data_dir, "crops")
    os.makedirs(crops_dir, exist_ok=True)
    essays, ratings = [], []

    for name in sorted(os.listdir(download)):
        if not name.endswith("-writing-sample-tasks-2023.pdf"):
            continue
        module = "AC" if "academic" in name else "GT"
        doc = fitz.open(os.path.join(download, name))
        prompts, scripts = find_task2_scripts(doc)
        for (task, script), info in sorted(scripts.items()):
            essay_id = f"OFF-{module}-2{task}-{script}"
            parts, confidences = [], []
            regions = [(doc[p], candidate_region(doc[p])) for p in info["pages"]]
            for i, (page, region) in enumerate((pg, r) for pg, r in regions if r is not None):
                png = page.get_pixmap(dpi=RENDER_DPI, clip=region).tobytes("png")
                with open(os.path.join(crops_dir, f"{essay_id}-p{i + 1}.png"), "wb") as f:
                    f.write(png)
                result = extract_text_from_image(png, "image/png")
                if not result.get("success"):
                    raise RuntimeError(f"{essay_id} page {i + 1}: {result.get('error')}")
                parts.append(result["extracted_text"].strip())
                confidences.append(result.get("confidence", "?"))
            print(f"{essay_id}: band {info['band']}, {len(parts)} page(s), confidence {confidences}")
            essays.append({
                "essay_id": essay_id, "split": "test", "task": "task2",
                "task_type": "Academic" if module == "AC" else "General Training",
                "prompt": prompts.get(task, ""), "essay": "\n".join(parts),
                "source": "official-ielts", "writer_consent": "n/a",
                "notes": f"IELTS {module} sample script; transcribed by qwen-vl ({'/'.join(confidences)})",
            })
            ratings.append({
                "essay_id": essay_id, "rater_id": "IELTS-examiner",
                "task_response": "", "coherence_cohesion": "", "lexical_resource": "",
                "grammatical_range_accuracy": "", "overall": info["band"],
                "justification": "published examiner band (overall only)",
            })

    for filename, rows in (("essays.csv", essays), ("ratings.csv", ratings)):
        with open(os.path.join(data_dir, filename), "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    missing = [e["essay_id"] for e in essays if not e["prompt"]]
    print(f"Wrote {len(essays)} scripts to {data_dir}" + (f"; MISSING PROMPT: {missing}" if missing else ""))


if __name__ == "__main__":
    main(sys.argv[1])
