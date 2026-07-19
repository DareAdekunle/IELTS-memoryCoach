"""
seed_demo.py — Demo account seeding script for Qonda IELTS

Creates a realistic demo learner with:
  - 6 Writing attempts showing improvement over time
  - 2 Reading attempts across different passages
  - 1 Speaking attempt
  - 1 Listening attempt
  - Rich memory profile (weaknesses, strengths, archived)
  - Skill ranks at various levels (some progressing, one at rank 2)
  - One skill with clean_streak=2 (one essay away from rank-up live demo)

Usage:
  python seed_demo.py

  Optional flags:
  python seed_demo.py --reset    wipes existing demo data first
  python seed_demo.py --email demo@ieltscoach.com --password demo1234

The demo account credentials are printed at the end.
"""

import sys
import os
import uuid
import json
import argparse
from datetime import datetime, timedelta

sys.path.append(os.path.dirname(__file__))

from app.db.database import SessionLocal
from app.db.models import (
    LearnerMemory, PracticeAttempt, LearnerSkillRank, Learner
)
from api.auth.models import User
from api.auth.utils import hash_password, generate_user_id

# ─── Config ───────────────────────────────────────────────────────────────────

DEFAULT_EMAIL = "demo@ieltscoach.com"
DEFAULT_PASSWORD = "demo1234"
DEFAULT_NAME = "Dare Demo"

# ─── Helpers ──────────────────────────────────────────────────────────────────

def uid():
    return str(uuid.uuid4())[:12]

def days_ago(n):
    return datetime.utcnow() - timedelta(days=n)

# ─── Writing attempts data ────────────────────────────────────────────────────

WRITING_ATTEMPTS = [
    {
        "days_ago": 14,
        "prompt": "Some people believe that universities should focus only on academic studies, while others think universities should also prepare students for employment. Discuss both views and give your own opinion.",
        "task_type": "Discuss Both Views",
        "learner_response": "University is important for studying. Some people think university only for academic. Other people think university should help with job. I think both are important. First, academic study is good because you learn things. Second, job skills also good because you need money. In conclusion university is good.",
        "scores": {"thesis_clarity": 2, "organization": 1, "grammar": 2, "vocabulary": 2, "idea_development": 1},
        "overall_feedback": "The essay is significantly underdeveloped. While it identifies both views, it fails to explain or support either with any reasoning or examples. The conclusion does not address the specific question asked."
    },
    {
        "days_ago": 12,
        "prompt": "In many cities, the number of cars is increasing, causing traffic congestion and pollution. What problems does this cause and what measures can be taken to address them?",
        "task_type": "Problem and Solution",
        "learner_response": "Traffic congestion is a big problem in many cities around the world today. The main causes are that too many people buy cars and the roads are not big enough. This causes pollution and also causes accidents. To solve this problem, the government should build more roads and also make public transport better. People should also use bicycles more. In conclusion, traffic is a serious problem but it can be solved with the right policies.",
        "scores": {"thesis_clarity": 3, "organization": 2, "grammar": 3, "vocabulary": 3, "idea_development": 2},
        "overall_feedback": "Some improvement in structure. The essay identifies problems and solutions but lacks specific examples and explanation. The body paragraphs need clearer central ideas and more development."
    },
    {
        "days_ago": 10,
        "prompt": "Technology has made it easier for people to work from home. Do you think this is a positive or negative development? Give reasons for your answer.",
        "task_type": "Agree or Disagree",
        "learner_response": "Working from home has become increasingly common due to advances in technology such as video conferencing and cloud computing. In my view, this is largely a positive development, although it does have some drawbacks. On the positive side, working from home saves commuting time and allows employees greater flexibility. For example, parents can better manage childcare responsibilities while maintaining their careers. Furthermore, companies can reduce office costs significantly. However, working from home can lead to isolation and make collaboration more difficult. Despite these disadvantages, I believe the benefits outweigh the drawbacks for most workers.",
        "scores": {"thesis_clarity": 4, "organization": 3, "grammar": 4, "vocabulary": 3, "idea_development": 3},
        "overall_feedback": "Good improvement in structure and argument development. The position is clear and supported with relevant reasoning. Vocabulary is improving but still relies on common expressions. Work on developing each paragraph more fully with specific evidence."
    },
    {
        "days_ago": 7,
        "prompt": "Some people think that children should begin formal education at a very early age, while others believe that they should not start school until they are older. Discuss both views and give your opinion.",
        "task_type": "Discuss Both Views",
        "learner_response": "The question of when children should begin formal education is widely debated among educators and parents alike. Those who advocate for early education argue that young children have remarkable capacity for language acquisition and cognitive development. For instance, research from Finland suggests that early structured play-based learning can establish strong foundational skills. On the other hand, opponents argue that formal schooling at too young an age may cause unnecessary stress and stifle creativity. Children who start later, they contend, often catch up quickly and demonstrate better social adjustment. In my view, a balanced approach is most effective — introducing structured learning gradually from age five, with an emphasis on play and discovery rather than rigid academic instruction.",
        "scores": {"thesis_clarity": 4, "organization": 4, "grammar": 4, "vocabulary": 4, "idea_development": 4},
        "overall_feedback": "Strong essay showing clear progression. Both views are discussed with supporting reasoning and the personal opinion is well-integrated. Vocabulary is varied and precise. Minor areas for improvement: the conclusion could synthesise the argument more specifically."
    },
    {
        "days_ago": 4,
        "prompt": "In some countries, people are choosing to have fewer children. What are the reasons for this trend and what effects will it have on society?",
        "task_type": "Cause and Effect",
        "learner_response": "Declining birth rates have become a significant demographic trend across many developed and developing nations. This essay will examine the primary reasons for this phenomenon and analyse its likely societal consequences. The most significant driver is economic pressure. Raising children has become increasingly costly, particularly in urban areas where housing, education and childcare expenses have risen substantially. Additionally, changing social attitudes towards gender roles have led more women to prioritise career development over early parenthood. The consequences of sustained low birth rates are considerable. An ageing population places greater strain on pension systems and healthcare infrastructure, as fewer working-age adults support a larger elderly cohort. Furthermore, labour shortages in key sectors may necessitate increased immigration, which itself carries complex social implications. In conclusion, while declining birth rates reflect individual choices made in response to economic and social realities, their collective impact on society demands proactive policy responses.",
        "scores": {"thesis_clarity": 5, "organization": 5, "grammar": 5, "vocabulary": 5, "idea_development": 4},
        "overall_feedback": "Excellent essay demonstrating strong command of academic writing. The argument is clearly structured, well-supported and uses sophisticated vocabulary appropriately. Idea development is thorough across most paragraphs. Minor refinement needed in the final body paragraph to fully develop the immigration point."
    },
    {
        "days_ago": 1,
        "prompt": "Many governments are now spending large amounts of money on improving digital infrastructure. Is this the best way to use public funds? Give your opinion with reasons and examples.",
        "task_type": "Agree or Disagree",
        "learner_response": "Government investment in digital infrastructure has accelerated significantly in recent years, driven by the recognition that connectivity is now as fundamental as roads and utilities. While I broadly support such investment, I argue that its effectiveness depends critically on equitable distribution and complementary investment in digital literacy. Proponents of digital infrastructure spending rightly point to its multiplier effects on economic productivity. High-speed internet access enables remote work, supports e-commerce and facilitates access to education — benefits that compound across sectors. Estonia's e-governance model, for instance, has demonstrably reduced administrative costs while improving service delivery. Nevertheless, infrastructure alone is insufficient if populations lack the skills to leverage it. Digital literacy programmes must accompany connectivity investment to ensure that underserved communities are not further marginalised. Public funds should therefore be allocated with equal attention to hardware and human capital. In conclusion, digital infrastructure investment represents sound public spending when implemented as part of a broader digital inclusion strategy rather than as an isolated technical project.",
        "scores": {"thesis_clarity": 5, "organization": 5, "grammar": 5, "vocabulary": 5, "idea_development": 5},
        "overall_feedback": "Outstanding essay. The argument is nuanced, well-evidenced and demonstrates sophisticated academic register throughout. Cohesive devices are used purposefully and the position is maintained consistently. This represents Band 8+ level writing."
    }
]

# ─── Reading attempts data ────────────────────────────────────────────────────

READING_ATTEMPTS = [
    {
        "days_ago": 18,
        "passage_title": "The Science of Sleep",
        "task_type": "Academic Reading",
        "learner_response": "Answers submitted for The Science of Sleep passage",
        "total_score": 9, "max_score": 14, "percentage": 64,
        "skill_accuracy": {
            "detail_retrieval": 67,
            "main_idea": 60,
            "inference": 33,
            "vocabulary_in_context": 75,
            "tfng": 50,
        },
        "overall_feedback": "Score: 9/14 (64%). Reasonable start. You located most explicit details but struggled with True/False/Not Given questions and inference — common early challenges. Focus on reading the question carefully before scanning."
    },
    {
        "days_ago": 11,
        "passage_title": "Urban Green Spaces and Mental Health",
        "task_type": "Academic Reading",
        "learner_response": "Answers submitted for Urban Green Spaces passage",
        "total_score": 11, "max_score": 14, "percentage": 79,
        "skill_accuracy": {
            "detail_retrieval": 100,
            "main_idea": 80,
            "inference": 50,
            "vocabulary_in_context": 75,
            "tfng": 67,
        },
        "overall_feedback": "Score: 11/14 (79%). Clear improvement — detail retrieval is now a strength. Inference and TFNG remain the weakest areas; you answered 'Not Given' on Q9 which was 'False'. Try underlining the key claim and finding direct evidence before selecting NG."
    },
    {
        "days_ago": 5,
        "passage_title": "The History of Public Libraries",
        "task_type": "Academic Reading",
        "learner_response": "Answers submitted for The History of Public Libraries passage",
        "total_score": 12, "max_score": 14, "percentage": 86,
        "skill_accuracy": {
            "detail_retrieval": 100,
            "main_idea": 100,
            "inference": 67,
            "vocabulary_in_context": 100,
            "tfng": 67,
        },
        "overall_feedback": "Score: 12/14 (86%). Strong performance. Detail retrieval and vocabulary in context are consistent strengths now. Inference accuracy is improving — Q11 and Q13 were the only misses. One more strong attempt on inference-heavy passages would consolidate this skill."
    },
    {
        "days_ago": 1,
        "passage_title": "The Economics of Renewable Energy",
        "task_type": "Academic Reading",
        "learner_response": "Answers submitted for The Economics of Renewable Energy passage",
        "total_score": 13, "max_score": 14, "percentage": 93,
        "skill_accuracy": {
            "detail_retrieval": 100,
            "main_idea": 100,
            "inference": 100,
            "vocabulary_in_context": 100,
            "tfng": 67,
        },
        "overall_feedback": "Score: 13/14 (93%). Excellent. Inference is now a consistent strength — a significant improvement from your first attempt. TFNG remains the only gap. One question misread 'Not Given' as 'False' — re-check whether the text directly contradicts the statement before selecting False."
    },
]

# ─── Memories data ────────────────────────────────────────────────────────────

MEMORIES = [
    # Writing weaknesses (active)
    {
        "section": "Writing", "skill": "Organization", "memory_type": "weakness",
        "memory_text": "Learner consistently omits essential structural components — no introduction with background and thesis, no body paragraphs, and no conclusion — resulting in fragmented responses in early attempts.",
        "confidence": 0.65, "evidence_count": 3, "status": "active",
        "days_ago": 12
    },
    {
        "section": "Writing", "skill": "Idea Development", "memory_type": "weakness",
        "memory_text": "Learner lists causes and solutions without explanation, elaboration, or real-world examples; ideas remain abstract and unsupported in mid-level attempts.",
        "confidence": 0.55, "evidence_count": 3, "status": "active",
        "days_ago": 9
    },
    # Writing strengths (active)
    {
        "section": "Writing", "skill": "Vocabulary", "memory_type": "strength",
        "memory_text": "Learner demonstrates expanding lexical range — from basic vocabulary in early essays to sophisticated academic register including 'multiplier effects', 'equitable distribution' and 'human capital' in recent attempts.",
        "confidence": 0.92, "evidence_count": 5, "status": "active",
        "days_ago": 3
    },
    {
        "section": "Writing", "skill": "Thesis Clarity", "memory_type": "strength",
        "memory_text": "Learner now consistently states a clear, explicit thesis in the introduction and maintains that position throughout the essay without deviation — a significant improvement from early attempts.",
        "confidence": 0.90, "evidence_count": 4, "status": "active",
        "days_ago": 5
    },
    {
        "section": "Writing", "skill": "Organization", "memory_type": "strength",
        "memory_text": "Recent essays show strong paragraph structure with clear topic sentences, supporting evidence and paragraph-level conclusions — a marked improvement from the fragmented early responses.",
        "confidence": 0.88, "evidence_count": 3, "status": "active",
        "days_ago": 2
    },
    # Writing archived (mastered)
    {
        "section": "Writing", "skill": "Grammar", "memory_type": "strength",
        "memory_text": "Learner has demonstrated consistent grammatical accuracy across five consecutive essays, including complex structures such as conditionals, relative clauses and passive constructions.",
        "confidence": 0.95, "evidence_count": 5, "status": "archived",
        "days_ago": 2
    },
    # Reading memories
    {
        "section": "Reading", "skill": "Inference", "memory_type": "weakness",
        "memory_text": "Learner failed the inference question (Q7) in the Sleep passage, selecting Not Given when the correct answer was True — suggesting difficulty drawing conclusions from implied information.",
        "confidence": 0.80, "evidence_count": 2, "status": "active",
        "days_ago": 8
    },
    {
        "section": "Reading", "skill": "Main Idea", "memory_type": "strength",
        "memory_text": "Learner consistently identifies the central theme of passages, achieving 100% accuracy on main idea questions across both reading attempts.",
        "confidence": 0.90, "evidence_count": 2, "status": "active",
        "days_ago": 4
    },
    {
        "section": "Reading", "skill": "Detail Retrieval", "memory_type": "strength",
        "memory_text": "Learner scored 89-100% on detail retrieval questions, correctly answering True/False/Not Given and multiple-choice detail questions with high accuracy.",
        "confidence": 0.85, "evidence_count": 2, "status": "active",
        "days_ago": 4
    },
    {
        "section": "Reading", "skill": "Vocabulary in Context", "memory_type": "strength",
        "memory_text": "Learner correctly interpreted vocabulary in context questions, demonstrating ability to deduce word meaning from surrounding text.",
        "confidence": 0.88, "evidence_count": 2, "status": "active",
        "days_ago": 4
    }
]

# ─── Skill ranks data ─────────────────────────────────────────────────────────
# Designed for demo impact:
# - Most skills at rank 1 (shows room to grow)
# - Key skills at rank 2 (shows progression)
# - One skill with clean_streak=2 (one essay from rank-up — live demo moment)

SKILL_RANKS = [
    # ── Writing: Task Response ─────────────────────────────────────────────────
    {"section": "Writing", "skill_id": "tr_full_coverage",        "current_rank": 2, "clean_streak": 1, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "tr_position_clarity",     "current_rank": 2, "clean_streak": 2, "total_evidence": 6, "last_classification": "demonstrated_strength"},  # ← one away from rank 3!
    {"section": "Writing", "skill_id": "tr_idea_development",     "current_rank": 2, "clean_streak": 1, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "tr_conclusion_synthesis", "current_rank": 1, "clean_streak": 2, "total_evidence": 5, "last_classification": "demonstrated_strength"},
    # ── Writing: Coherence & Cohesion ─────────────────────────────────────────
    {"section": "Writing", "skill_id": "cc_logical_progression",  "current_rank": 2, "clean_streak": 0, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "cc_paragraphing",         "current_rank": 2, "clean_streak": 1, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "cc_cohesive_devices",     "current_rank": 1, "clean_streak": 1, "total_evidence": 5, "last_classification": "demonstrated_weakness"},
    # ── Writing: Lexical Resource ──────────────────────────────────────────────
    {"section": "Writing", "skill_id": "lr_range",                "current_rank": 3, "clean_streak": 0, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "lr_precision",            "current_rank": 2, "clean_streak": 2, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "lr_spelling_word_formation", "current_rank": 2, "clean_streak": 1, "total_evidence": 5, "last_classification": "demonstrated_strength"},
    # ── Writing: Grammatical Range & Accuracy ─────────────────────────────────
    {"section": "Writing", "skill_id": "gra_sentence_variety",    "current_rank": 3, "clean_streak": 1, "total_evidence": 6, "last_classification": "demonstrated_strength"},
    {"section": "Writing", "skill_id": "gra_accuracy",            "current_rank": 3, "clean_streak": 2, "total_evidence": 6, "last_classification": "demonstrated_strength"},  # ← one away from rank 4!
    {"section": "Writing", "skill_id": "gra_punctuation",         "current_rank": 2, "clean_streak": 0, "total_evidence": 5, "last_classification": "demonstrated_strength"},
    # ── Reading: Information Retrieval ────────────────────────────────────────
    {"section": "Reading", "skill_id": "ri_detail_retrieval",     "current_rank": 2, "clean_streak": 1, "total_evidence": 2, "last_classification": "demonstrated_strength"},
    {"section": "Reading", "skill_id": "ri_skimming",             "current_rank": 1, "clean_streak": 1, "total_evidence": 2, "last_classification": "demonstrated_strength"},
    {"section": "Reading", "skill_id": "ri_scanning",             "current_rank": 1, "clean_streak": 0, "total_evidence": 2, "last_classification": "demonstrated_weakness"},
    # ── Reading: Reading Comprehension ────────────────────────────────────────
    {"section": "Reading", "skill_id": "rc_main_idea",            "current_rank": 2, "clean_streak": 1, "total_evidence": 2, "last_classification": "demonstrated_strength"},
    {"section": "Reading", "skill_id": "rc_inference",            "current_rank": 1, "clean_streak": 0, "total_evidence": 2, "last_classification": "demonstrated_weakness"},
    {"section": "Reading", "skill_id": "rc_tfng",                 "current_rank": 1, "clean_streak": 1, "total_evidence": 2, "last_classification": "demonstrated_strength"},
    {"section": "Reading", "skill_id": "rc_writer_intent",        "current_rank": 1, "clean_streak": 0, "total_evidence": 2, "last_classification": "demonstrated_weakness"},
    # ── Reading: Vocabulary ───────────────────────────────────────────────────
    {"section": "Reading", "skill_id": "rv_context_meaning",      "current_rank": 2, "clean_streak": 1, "total_evidence": 2, "last_classification": "demonstrated_strength"},
    {"section": "Reading", "skill_id": "rv_paraphrase",           "current_rank": 1, "clean_streak": 1, "total_evidence": 2, "last_classification": "demonstrated_strength"},
    # ── Reading: Text Structure ───────────────────────────────────────────────
    {"section": "Reading", "skill_id": "rt_paragraph_purpose",    "current_rank": 1, "clean_streak": 0, "total_evidence": 2, "last_classification": "demonstrated_weakness"},
]


def seed_demo(email=DEFAULT_EMAIL, password=DEFAULT_PASSWORD, reset=False):
    db = SessionLocal()

    try:
        print(f"\n{'='*60}")
        print("Qonda IELTS — Demo Account Seeder")
        print(f"{'='*60}\n")

        # ── Check for existing demo account ──────────────────────────
        existing_user = db.query(User).filter(User.email == email).first()

        if existing_user and reset:
            print(f"Resetting existing demo account: {email}")
            learner_id = existing_user.learner_id

            if learner_id:
                db.query(LearnerMemory).filter(
                    LearnerMemory.learner_id == learner_id
                ).delete()
                db.query(PracticeAttempt).filter(
                    PracticeAttempt.learner_id == learner_id
                ).delete()
                db.query(LearnerSkillRank).filter(
                    LearnerSkillRank.learner_id == learner_id
                ).delete()
                db.query(Learner).filter(
                    Learner.learner_id == learner_id
                ).delete()

            db.query(User).filter(User.email == email).delete()
            db.commit()
            existing_user = None
            print("✅ Existing data cleared\n")

        elif existing_user and not reset:
            print(f"Demo account already exists: {email}")
            print("Run with --reset to recreate it\n")
            print(f"Email:    {email}")
            print(f"Password: {password}")
            return

        # ── Create learner profile ────────────────────────────────────
        learner_id = uid()
        learner = Learner(
            learner_id=learner_id,
            name=DEFAULT_NAME,
            target_score=7.5,
            test_date="2026-09-15",
            current_focus="Writing"
        )
        db.add(learner)
        print(f"✅ Learner profile created: {DEFAULT_NAME} (ID: {learner_id})")

        # ── Create user account ───────────────────────────────────────
        user_id = generate_user_id()
        user = User(
            user_id=user_id,
            email=email,
            username="alex_chen_demo",
            full_name=DEFAULT_NAME,
            password_hash=hash_password(password),
            auth_provider="local",
            learner_id=learner_id,
            is_active=True
        )
        db.add(user)
        print(f"✅ User account created: {email}")

        # ── Create Writing attempts ───────────────────────────────────
        print(f"\nCreating {len(WRITING_ATTEMPTS)} Writing attempts...")
        for i, attempt_data in enumerate(WRITING_ATTEMPTS):
            attempt = PracticeAttempt(
                attempt_id=uid(),
                learner_id=learner_id,
                section="Writing",
                task_type=attempt_data["task_type"],
                prompt=attempt_data["prompt"],
                learner_response=attempt_data["learner_response"],
                score_json=json.dumps({
                    "scores": attempt_data["scores"],
                    "overall_feedback": attempt_data["overall_feedback"],
                    "strengths": [],
                    "weaknesses": []
                }),
                feedback=attempt_data["overall_feedback"],
                created_at=days_ago(attempt_data["days_ago"])
            )
            db.add(attempt)
            scores = attempt_data["scores"]
            avg = sum(scores.values()) / len(scores)
            print(f"  ✅ Writing #{i+1} — avg score {avg:.1f}/5 ({attempt_data['days_ago']} days ago)")

        # ── Create Reading attempts ───────────────────────────────────
        print(f"\nCreating {len(READING_ATTEMPTS)} Reading attempts...")
        for i, attempt_data in enumerate(READING_ATTEMPTS):
            attempt = PracticeAttempt(
                attempt_id=uid(),
                learner_id=learner_id,
                section="Reading",
                task_type=attempt_data["task_type"],
                prompt=attempt_data["passage_title"],
                learner_response=attempt_data["learner_response"],
                score_json=json.dumps({
                    "passage_title":  attempt_data["passage_title"],
                    "total_score":    attempt_data["total_score"],
                    "max_score":      attempt_data["max_score"],
                    "percentage":     attempt_data["percentage"],
                    "skill_accuracy": attempt_data["skill_accuracy"],
                    "overall_feedback": attempt_data["overall_feedback"],
                }),
                feedback=(
                    f"Score: {attempt_data['total_score']}/{attempt_data['max_score']} "
                    f"({attempt_data['percentage']}%)"
                ),
                created_at=days_ago(attempt_data["days_ago"])
            )
            db.add(attempt)
            print(f"  ✅ Reading #{i+1} — {attempt_data['percentage']}% ({attempt_data['days_ago']} days ago)")

        # ── Create memories ───────────────────────────────────────────
        print(f"\nCreating {len(MEMORIES)} coaching memories...")
        weakness_count = 0
        strength_count = 0
        archived_count = 0

        for mem_data in MEMORIES:
            memory = LearnerMemory(
                memory_id=uid(),
                learner_id=learner_id,
                section=mem_data["section"],
                skill=mem_data["skill"],
                memory_type=mem_data["memory_type"],
                memory_text=mem_data["memory_text"],
                confidence=mem_data["confidence"],
                evidence_count=mem_data["evidence_count"],
                status=mem_data["status"],
                created_at=days_ago(mem_data["days_ago"] + 1),
                updated_at=days_ago(mem_data["days_ago"])
            )
            db.add(memory)

            if mem_data["status"] == "archived":
                archived_count += 1
            elif mem_data["memory_type"] == "weakness":
                weakness_count += 1
            else:
                strength_count += 1

        print(f"  ✅ {weakness_count} weaknesses, {strength_count} strengths, {archived_count} archived")

        # ── Create skill ranks ────────────────────────────────────────
        print(f"\nCreating {len(SKILL_RANKS)} skill rank records...")
        for rank_data in SKILL_RANKS:
            rank = LearnerSkillRank(
                rank_id=uid(),
                learner_id=learner_id,
                section=rank_data["section"],
                skill_id=rank_data["skill_id"],
                current_rank=rank_data["current_rank"],
                clean_streak=rank_data["clean_streak"],
                total_evidence=rank_data["total_evidence"],
                last_classification=rank_data["last_classification"]
            )
            db.add(rank)

        writing_ranks = [r for r in SKILL_RANKS if r["section"] == "Writing"]
        reading_ranks = [r for r in SKILL_RANKS if r["section"] == "Reading"]
        near_rankup = len([r for r in SKILL_RANKS if r["clean_streak"] == 2])
        print(f"  ✅ {len(writing_ranks)} Writing skill ranks, {len(reading_ranks)} Reading skill ranks")
        print(f"  ⭐ {near_rankup} skills with streak=2 (one attempt from rank-up!)")

        db.commit()

        # ── Summary ───────────────────────────────────────────────────
        print(f"\n{'='*60}")
        print("✅ DEMO ACCOUNT READY")
        print(f"{'='*60}")
        print(f"\nLogin credentials:")
        print(f"  Email:    {email}")
        print(f"  Password: {password}")
        print(f"\nLearner ID: {learner_id}")
        print(f"\nDemo highlights for judges:")
        print(f"  📈 6 Writing essays showing clear improvement over 14 days")
        print(f"  📖 4 Reading attempts showing 64% → 79% → 86% → 93% progression")
        print(f"  🧠 {len(MEMORIES)} coaching memories across Writing and Reading")
        print(f"  🎯 2 skills with streak=2 — submit one good essay live for rank-up!")
        print(f"  🏆 Grammar skill archived (mastered)")
        print(f"  💬 Chat Coach will open with Writing Tutor targeting Cohesive Devices")
        print(f"\nSuggested demo flow:")
        print(f"  1. Log in → Dashboard (shows 6 writing, 2 reading, rich memory stats)")
        print(f"  2. Memory Dashboard → Timeline tab (shows memory evolution)")
        print(f"  3. Skill Mastery page (shows rank progression, 2 skills near rank-up)")
        print(f"  4. Chat Coach → Writing Tutor (opens with personalised Cohesive Devices lesson)")
        print(f"  5. Writing Coach → submit one essay live → watch rank-up fire")
        print(f"  6. MCP demo: show get_coaching_context tool returning live data")
        print(f"\n{'='*60}\n")

    except Exception as e:
        db.rollback()
        print(f"\n❌ Error during seeding: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Seed the Qonda IELTS demo account"
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="Wipe existing demo data and recreate from scratch"
    )
    parser.add_argument(
        "--email", default=DEFAULT_EMAIL,
        help=f"Demo account email (default: {DEFAULT_EMAIL})"
    )
    parser.add_argument(
        "--password", default=DEFAULT_PASSWORD,
        help=f"Demo account password (default: {DEFAULT_PASSWORD})"
    )
    args = parser.parse_args()

    seed_demo(
        email=args.email,
        password=args.password,
        reset=args.reset
    )
