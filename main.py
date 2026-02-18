from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from groq import Groq
import os
from datetime import datetime
from dotenv import load_dotenv
from database import db
from typing import Optional, Dict, Any, List

load_dotenv()

app = FastAPI(
    title="Hackathon Support Chatbot API",
    description="AI-powered chatbot for hackathon support using Groq",
    version="1.0.0"
)

# CORS Configuration - Allow all origins for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize Groq client
groq_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Request/Response Models
class ChatRequest(BaseModel):
    question: str
    hackathon_id: str
    conversation_history: Optional[List[Dict[str, str]]] = []

class ChatResponse(BaseModel):
    answer: str
    confidence: str
    timestamp: str
    conversation_history: List[Dict[str, str]]

class HackathonDataRequest(BaseModel):
    hackathon_data: Dict[str, Any]

# System Prompt
SYSTEM_PROMPT = """You are an official Hackathon Support Assistant.
Your responsibility is to help participants, mentors, and organizers by answering questions
STRICTLY using the provided hackathon data.

Rules you MUST follow:
1. Use ONLY the information given in the context.
2. Do NOT assume, guess, or add any information outside the provided data.
3. When given the CURRENT TIME and DATES, you MUST make definitive statements about status.
   - If current time is AFTER the end date, say "The hackathon/registration HAS CLOSED"
   - If current time is BEFORE the start date, say "The hackathon/registration HAS NOT STARTED YET"
   - If current time is BETWEEN start and end, say "The hackathon/registration IS CURRENTLY OPEN"
4. NEVER say "assuming the current date" or "we cannot definitively say" - the context includes current time!
5. Be helpful and provide all relevant information from the context.

CRITICAL FORMATTING RULES - YOU MUST FOLLOW EXACTLY:
Your response will be displayed in a markdown renderer, so format accordingly.

For lists of multiple items, use this EXACT format:

The hackathon has four problem statements:

**1. AI-Powered Smart Assistant** (AI Machine Learning)
- Build an intelligent assistant for daily tasks
- Features: NLP, task automation, voice interaction

**2. Digital Payment Solution** (Fintech)
- Create a secure payment platform  
- Features: Multi-platform support, real-time tracking

For short answers (1-2 items), write naturally without formatting.
For 3+ items, ALWAYS use the numbered format above.
Use proper markdown with ** for bold.
Add blank lines between sections for readability.

Your goal is to provide reliable, DEFINITIVE official answers that render beautifully in markdown."""
"""

---

## 🎯 Example of Improved Response

**Before (Vague):**
```
Since the end date is 2026-03-13T09:44:00Z, and assuming the current 
date is after this, the hackathon would be closed. However, without 
the current date for comparison, we cannot definitively say...
```

**After (Definitive):**
```
✅ The hackathon CodeCatalyst HAS ENDED.

Current Status: CLOSED
- Start Date: January 5, 2026 at 9:44 AM UTC
- End Date: March 13, 2026 at 9:44 AM UTC  
- Current Date: February 18, 2026 at 3:45 PM UTC

The hackathon is currently running and will end in 23 days.

"""
from datetime import datetime, timezone

def extract_relevant_sections(hackathon_data: Dict[str, Any], question: str) -> str:
    """Extract relevant sections from hackathon data based on question keywords.
    Returns comprehensive context to ensure AI has enough information."""
    
    question_lower = question.lower()
    sections = []
    matched_categories = []
    
    # Helper function to check if registration is currently open
    def is_registration_currently_open():
        try:
            reg_phase = next((p for p in hackathon_data.get('phases', []) if p.get('type') == 'registration'), None)
            if not reg_phase:
                return hackathon_data.get('is_registration_open', False)
            
            now = datetime.now(timezone.utc)
            start = datetime.fromisoformat(reg_phase.get('start_datetime', '').replace('Z', '+00:00'))
            end = datetime.fromisoformat(reg_phase.get('end_datetime', '').replace('Z', '+00:00'))
            
            return start <= now <= end
        except:
            # Fallback to database value if date parsing fails
            return hackathon_data.get('is_registration_open', False)
    
    # Helper function to get hackathon status
    def get_hackathon_status():
        try:
            now = datetime.now(timezone.utc)
            start = datetime.fromisoformat(hackathon_data.get('start_datetime', '').replace('Z', '+00:00'))
            end = datetime.fromisoformat(hackathon_data.get('end_datetime', '').replace('Z', '+00:00'))
            
            if now < start:
                return "upcoming", f"Starts in {(start - now).days} days"
            elif now > end:
                return "ended", f"Ended {(now - end).days} days ago"
            else:
                return "ongoing", f"Ends in {(end - now).days} days"
        except:
            return "unknown", "Status unavailable"
    
    # Registration-related keywords
    registration_keywords = ['register', 'registration', 'sign up', 'join', 'participate', 'enroll', 'apply', 'closed', 'open']
    if any(word in question_lower for word in registration_keywords):
        matched_categories.append('registration')
        reg_phase = next((p for p in hackathon_data.get('phases', []) if p.get('type') == 'registration'), None)
        if reg_phase:
            sections.append("=== REGISTRATION INFORMATION ===")
            sections.append(f"Registration Period: {reg_phase.get('start_datetime')} to {reg_phase.get('end_datetime')}")
            
            # Real-time status - VERY IMPORTANT
            is_open = is_registration_currently_open()
            current_time = datetime.now(timezone.utc).isoformat()
            sections.append(f"\nCurrent Time: {current_time}")
            sections.append(f"Current Status: {'✅ REGISTRATION IS OPEN - You can register now!' if is_open else '❌ REGISTRATION IS CLOSED - Registration period has ended'}")
            sections.append(f"Description: {reg_phase.get('description', 'Registration period for the hackathon')}")
            
            if hackathon_data.get('registration_questions'):
                sections.append("\nRegistration Questions Required:")
                for q in hackathon_data['registration_questions']:
                    req_text = "Required" if q.get('required') else "Optional"
                    sections.append(f"  - {q.get('label')} ({q.get('type')}) - {req_text}")
    
    # Check hackathon status if asked about "closed", "ended", "finished"
    status_keywords = ['closed', 'ended', 'finished', 'over', 'status', 'ongoing', 'running']
    if any(word in question_lower for word in status_keywords):
        if 'registration' not in matched_categories:  # Don't duplicate if already covered
            matched_categories.append('status')
            status, status_detail = get_hackathon_status()
            sections.append("\n=== HACKATHON STATUS ===")
            sections.append(f"Current Time: {datetime.now(timezone.utc).isoformat()}")
            sections.append(f"Hackathon Period: {hackathon_data.get('start_datetime')} to {hackathon_data.get('end_datetime')}")
            
            if status == "upcoming":
                sections.append(f"Status: 🔜 UPCOMING - {status_detail}")
            elif status == "ongoing":
                sections.append(f"Status: 🚀 CURRENTLY RUNNING - {status_detail}")
            elif status == "ended":
                sections.append(f"Status: ✅ ENDED - {status_detail}")
            else:
                sections.append(f"Status: ❓ {status}")
    
    # ... rest of your extract_relevant_sections function stays the same ...
    
    # Team-related
    team_keywords = ['team', 'size', 'member', 'solo', 'group', 'individual', 'alone', 'partner']
    if any(word in question_lower for word in team_keywords):
        matched_categories.append('team')
        sections.append("\n=== TEAM SIZE INFORMATION ===")
        min_size = hackathon_data.get('min_team_size', 'Not specified')
        max_size = hackathon_data.get('max_team_size', 'Not specified')
        sections.append(f"Minimum team size: {min_size}")
        sections.append(f"Maximum team size: {max_size}")
        
        if min_size == 1 and max_size == 1:
            sections.append("This is a SOLO hackathon - only individual participation is allowed.")
        elif min_size == 1:
            sections.append(f"Solo participation is allowed. Teams can have up to {max_size} members.")
    
    # Themes & Problem Statements
    theme_keywords = ['theme', 'track', 'problem', 'challenge', 'topic', 'category', 'domain', 'statement']
    if any(word in question_lower for word in theme_keywords):
        matched_categories.append('themes')
        sections.append("\n=== THEMES AND PROBLEM STATEMENTS ===")
        themes = hackathon_data.get('themes', [])
        sections.append(f"Total number of themes: {len(themes)}")
        
        for idx, theme in enumerate(themes, 1):
            sections.append(f"\n{idx}. {theme['name']}")
            sections.append(f"   Description: {theme.get('description', 'No description available')}")
            
            problem_statements = theme.get('problem_statements', [])
            if problem_statements:
                sections.append(f"   Problem Statements ({len(problem_statements)}):")
                for ps in problem_statements:
                    sections.append(f"     • {ps['name']}")
                    sections.append(f"       {ps.get('description', '')}")
    
    # Timeline/Phases
    timeline_keywords = ['phase', 'timeline', 'deadline', 'when', 'date', 'schedule', 'duration', 'time', 'start', 'end', 'submission']
    if any(word in question_lower for word in timeline_keywords):
        matched_categories.append('timeline')
        sections.append("\n=== HACKATHON TIMELINE AND PHASES ===")
        sections.append(f"Overall Duration: {hackathon_data.get('start_datetime')} to {hackathon_data.get('end_datetime')}")
        
        phases = hackathon_data.get('phases', [])
        sections.append(f"\nTotal Phases: {len(phases)}")
        
        for idx, phase in enumerate(phases, 1):
            sections.append(f"\n{idx}. {phase.get('name')}")
            sections.append(f"   Period: {phase.get('start_datetime')} to {phase.get('end_datetime')}")
            sections.append(f"   Type: {phase.get('type')}")
            if phase.get('description'):
                sections.append(f"   Description: {phase.get('description')}")
            
            if phase.get('submission_questions'):
                sections.append(f"   Submission Requirements:")
                for sq in phase['submission_questions']:
                    req = "Required" if sq.get('required') else "Optional"
                    sections.append(f"     - {sq.get('label')} (Type: {sq.get('type')}) - {req}")
            
            if phase.get('is_elimination_round'):
                sections.append(f"   ⚠️ This is an ELIMINATION ROUND")
            
            sections.append(f"   Evaluator: {phase.get('evaluator', 'Not specified')}")
    
    # Evaluation/Judging
    eval_keywords = ['judg', 'evaluat', 'criteria', 'score', 'point', 'metric', 'assess', 'grade', 'marking']
    if any(word in question_lower for word in eval_keywords):
        matched_categories.append('evaluation')
        sections.append("\n=== EVALUATION CRITERIA ===")
        
        for phase in hackathon_data.get('phases', []):
            if phase.get('evaluation_metrics'):
                sections.append(f"\n{phase.get('name')} Phase:")
                sections.append(f"Evaluator: {phase.get('evaluator', 'Not specified')}")
                sections.append(f"Elimination Round: {'Yes' if phase.get('is_elimination_round') else 'No'}")
                
                sections.append("\nScoring Breakdown:")
                for metric_group in phase['evaluation_metrics']:
                    if metric_group.get('metrics'):
                        total_points = sum(metric_group['metrics'].values())
                        sections.append(f"\nTotal Points: {total_points}")
                        for criterion, points in metric_group['metrics'].items():
                            percentage = (points / total_points * 100) if total_points > 0 else 0
                            sections.append(f"  • {criterion}: {points} points ({percentage:.0f}%)")
    
    # Resources
    resource_keywords = ['resource', 'template', 'material', 'help', 'guide', 'document', 'link', 'tool']
    if any(word in question_lower for word in resource_keywords):
        matched_categories.append('resources')
        resources = hackathon_data.get('resources')
        if resources:
            sections.append("\n=== AVAILABLE RESOURCES ===")
            sections.append(resources)
        else:
            sections.append("\n=== AVAILABLE RESOURCES ===")
            sections.append("No specific resources have been provided yet.")
    
    # Prizes
    prize_keywords = ['prize', 'reward', 'win', 'award', 'bounty', 'incentive']
    if any(word in question_lower for word in prize_keywords):
        matched_categories.append('prizes')
        prizes = hackathon_data.get('prizes', [])
        sections.append("\n=== PRIZES ===")
        if prizes and len(prizes) > 0:
            for prize in prizes:
                sections.append(f"  • {prize}")
        else:
            sections.append("Prize information has not been announced yet.")
    
    # Events
    event_keywords = ['event', 'workshop', 'session', 'webinar', 'meeting', 'ceremony']
    if any(word in question_lower for word in event_keywords):
        matched_categories.append('events')
        events = hackathon_data.get('events', [])
        sections.append("\n=== SCHEDULED EVENTS ===")
        if events and len(events) > 0:
            for event in events:
                sections.append(f"\n• {event.get('title')}")
                sections.append(f"  Date/Time: {event.get('datetime')}")
                if event.get('description'):
                    sections.append(f"  Description: {event.get('description')}")
        else:
            sections.append("No specific events have been scheduled yet.")
    
    # Contact/Links
    contact_keywords = ['contact', 'reach', 'support', 'link', 'social', 'discord', 'slack', 'email']
    if any(word in question_lower for word in contact_keywords):
        matched_categories.append('contact')
        links = hackathon_data.get('links', {})
        sections.append("\n=== CONTACT & LINKS ===")
        has_links = False
        for platform, url in links.items():
            if url:
                has_links = True
                sections.append(f"  • {platform.capitalize()}: {url}")
        if not has_links:
            sections.append("Contact information will be provided soon.")
    
    # Mentors
    mentor_keywords = ['mentor', 'mentors', 'mentorship', 'guide', 'advisor', 'expert']
    if any(word in question_lower for word in mentor_keywords):
        matched_categories.append('mentors')
        mentors = hackathon_data.get('mentors', [])
        sections.append("\n=== MENTORS ===")
        if mentors and len(mentors) > 0:
            sections.append(f"Total mentors: {len(mentors)}")
            for mentor in mentors:
                if isinstance(mentor, dict):
                    name = mentor.get('name', 'Unknown')
                    expertise = mentor.get('expertise', mentor.get('role', 'Mentor'))
                    bio = mentor.get('bio', mentor.get('description', ''))
                    sections.append(f"\n• **{name}**")
                    sections.append(f"  Expertise: {expertise}")
                    if bio:
                        sections.append(f"  Bio: {bio}")
                elif isinstance(mentor, str):
                    sections.append(f"• {mentor}")
        else:
            sections.append("No mentors have been assigned yet.")
    
    # Judges
    judge_keywords = ['judge', 'judges', 'judging', 'jury', 'evaluator']
    if any(word in question_lower for word in judge_keywords):
        matched_categories.append('judges')
        judges = hackathon_data.get('judges', [])
        sections.append("\n=== JUDGES ===")
        if judges and len(judges) > 0:
            sections.append(f"Total judges: {len(judges)}")
            for judge in judges:
                if isinstance(judge, dict):
                    name = judge.get('name', 'Unknown')
                    title = judge.get('title', judge.get('role', 'Judge'))
                    company = judge.get('company', judge.get('organization', ''))
                    sections.append(f"\n• **{name}**")
                    sections.append(f"  Title: {title}")
                    if company:
                        sections.append(f"  Company: {company}")
                elif isinstance(judge, str):
                    sections.append(f"• {judge}")
        else:
            sections.append("Judges will be announced soon.")
    
    # Partners/Sponsors
    partner_keywords = ['partner', 'partners', 'sponsor', 'sponsors', 'supporter', 'collaboration']
    if any(word in question_lower for word in partner_keywords):
        matched_categories.append('partners')
        partners = hackathon_data.get('partners', [])
        sections.append("\n=== PARTNERS & SPONSORS ===")
        if partners and len(partners) > 0:
            for partner in partners:
                if isinstance(partner, dict):
                    name = partner.get('name', 'Unknown')
                    sections.append(f"• {name}")
                elif isinstance(partner, str):
                    sections.append(f"• {partner}")
        else:
            sections.append("Partner and sponsor information will be announced soon.")
    
    # FAQ
    faq_keywords = ['faq', 'frequently', 'question', 'questions', 'common', 'ask']
    if any(word in question_lower for word in faq_keywords):
        matched_categories.append('faq')
        faqs = hackathon_data.get('faq', [])
        sections.append("\n=== FREQUENTLY ASKED QUESTIONS ===")
        if faqs and len(faqs) > 0:
            for idx, faq in enumerate(faqs, 1):
                if isinstance(faq, dict):
                    q = faq.get('question', '')
                    a = faq.get('answer', '')
                    sections.append(f"\n**Q{idx}: {q}**")
                    sections.append(f"A: {a}")
        else:
            sections.append("No FAQs available yet.")
    
    # Rules
    rules_keywords = ['rule', 'rules', 'regulation', 'regulations', 'guideline', 'guidelines', 'policy']
    if any(word in question_lower for word in rules_keywords):
        matched_categories.append('rules')
        rules = hackathon_data.get('rules')
        sections.append("\n=== RULES & REGULATIONS ===")
        if rules:
            sections.append(rules)
        else:
            sections.append("Detailed rules will be published soon.")
    
    # Eligibility
    eligibility_keywords = ['eligib', 'can i join', 'can i participate', 'who can', 'requirement', 'qualify']
    if any(word in question_lower for word in eligibility_keywords):
        matched_categories.append('eligibility')
        eligibility = hackathon_data.get('eligibility', {})
        sections.append("\n=== ELIGIBILITY ===")
        
        profile_type = eligibility.get('profile_type', 'any')
        if profile_type != 'any':
            sections.append(f"Profile Type: {profile_type}")
        else:
            sections.append("Open to all participants")
        
        details = eligibility.get('details', '')
        if details:
            sections.append(f"Details: {details}")
        
        gender = eligibility.get('gender', 'any')
        if gender != 'any':
            sections.append(f"Gender: {gender}")
    
    # Location/Venue
    location_keywords = ['location', 'venue', 'where', 'address', 'place']
    if any(word in question_lower for word in location_keywords):
        matched_categories.append('location')
        location = hackathon_data.get('location')
        mode = hackathon_data.get('mode', 'Not specified')
        sections.append("\n=== LOCATION & VENUE ===")
        sections.append(f"Mode: {mode.capitalize()}")
        if location:
            sections.append(f"Location: {location}")
        elif mode.lower() == 'online':
            sections.append("This is an online hackathon - no physical location")
        else:
            sections.append("Venue details will be announced soon.")
    
    # General info if no specific match
    if not matched_categories or any(word in question_lower for word in ['about', 'overview', 'general', 'info', 'tell me', 'what is']):
        sections.insert(0, "=== HACKATHON OVERVIEW ===")
        sections.insert(1, f"Name: {hackathon_data.get('name')}")
        sections.insert(2, f"Tagline: {hackathon_data.get('tagline')}")
        sections.insert(3, f"About: {hackathon_data.get('about')}")
        sections.insert(4, f"Organizer: {hackathon_data.get('organizer_name')}")
        sections.insert(5, f"Mode: {hackathon_data.get('mode')}")
        sections.insert(6, f"Duration: {hackathon_data.get('start_datetime')} to {hackathon_data.get('end_datetime')}")
        sections.insert(7, f"Total Participants: {hackathon_data.get('total_participants', 0)}")
        sections.insert(8, "")
    
    return "\n".join(sections)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint - processes user questions with conversation context"""
    try:
        # Get hackathon data by ID
        hackathon_data = db.get_hackathon_by_id(request.hackathon_id)
        
        if not hackathon_data:
            raise HTTPException(
                status_code=404, 
                detail=f"Hackathon with ID '{request.hackathon_id}' not found"
            )
        
        # Extract relevant context from hackathon data
        context = extract_relevant_sections(hackathon_data, request.question)
        
        # Build conversation messages for Groq API
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT}
        ]
        
        # Add conversation history (last 5 exchanges to keep context manageable)
        if request.conversation_history:
            # Take only last 5 exchanges (10 messages)
            recent_history = request.conversation_history[-10:]
            for msg in recent_history:
                messages.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", "")
                })
        
        # Add current user question with hackathon context
        user_prompt = f"""Context about the hackathon:
{context}

User Question: {request.question}

Answer (use proper markdown formatting):"""
        
        messages.append({
            "role": "user",
            "content": user_prompt
        })
        
        # Call Groq API with conversation history
        chat_completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
            temperature=0.3,
            max_tokens=800
        )
        
        answer = chat_completion.choices[0].message.content.strip()
        confidence = "low" if "couldn't find" in answer.lower() else "high"
        
        # Update conversation history
        updated_history = request.conversation_history.copy() if request.conversation_history else []
        updated_history.append({"role": "user", "content": request.question})
        updated_history.append({"role": "assistant", "content": answer})
        
        # Keep only last 10 messages (5 exchanges) to prevent context overflow
        if len(updated_history) > 10:
            updated_history = updated_history[-10:]
        
        return ChatResponse(
            answer=answer,
            confidence=confidence,
            timestamp=datetime.utcnow().isoformat(),
            conversation_history=updated_history
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/admin/import-hackathon")
async def import_hackathon(data: HackathonDataRequest):
    """Import a single hackathon data into database"""
    try:
        success = db.insert_hackathon(data.hackathon_data)
        if success:
            return {
                "status": "success",
                "message": "Hackathon data imported successfully",
                "hackathon_id": data.hackathon_data.get("_id"),
                "hackathon_name": data.hackathon_data.get("name")
            }
        raise HTTPException(status_code=500, detail="Failed to import data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/import-multiple-hackathons")
async def import_multiple_hackathons(data: List[HackathonDataRequest]):
    """Import multiple hackathons at once - same format as single import"""
    try:
        imported = []
        failed = []
        
        for item in data:
            try:
                hackathon_data = item.hackathon_data
                
                # Clean the data before inserting
                import re
                
                def clean_string(text):
                    """Remove invalid control characters"""
                    if not isinstance(text, str):
                        return text
                    text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]', '', text)
                    return text
                
                def clean_data(obj):
                    """Recursively clean all strings"""
                    if isinstance(obj, dict):
                        return {k: clean_data(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [clean_data(item) for item in obj]
                    elif isinstance(obj, str):
                        return clean_string(obj)
                    else:
                        return obj
                
                cleaned_data = clean_data(hackathon_data)
                
                success = db.insert_hackathon(cleaned_data)
                if success:
                    imported.append({
                        "id": cleaned_data.get("_id"),
                        "name": cleaned_data.get("name")
                    })
                else:
                    failed.append({
                        "id": hackathon_data.get("_id"),
                        "name": hackathon_data.get("name"),
                        "error": "Insert failed"
                    })
            except Exception as e:
                failed.append({
                    "id": hackathon_data.get("_id") if 'hackathon_data' in locals() else "unknown",
                    "name": hackathon_data.get("name") if 'hackathon_data' in locals() else "unknown",
                    "error": str(e)
                })
        
        return {
            "status": "completed",
            "imported_count": len(imported),
            "failed_count": len(failed),
            "imported": imported,
            "failed": failed
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


        
@app.get("/hackathons")
async def list_hackathons():
    """List all available hackathons"""
    try:
        hackathons = db.list_all_hackathons()
        return {
            "total": len(hackathons),
            "hackathons": [
                {
                    "id": h.get("_id"),
                    "name": h.get("name"),
                    "slug": h.get("slug"),
                    "status": h.get("status"),
                    "mode": h.get("mode"),
                    "start_date": h.get("start_datetime"),
                    "end_date": h.get("end_datetime"),
                    "registration_open": h.get("is_registration_open", False),
                    "organizer": h.get("organizer_name")
                }
                for h in hackathons
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/hackathons/{identifier}")
async def get_hackathon_details(identifier: str):
    """Get details of a specific hackathon by ID or slug"""
    try:
        hackathon = db.get_hackathon_by_id(identifier)
        if not hackathon:
            hackathon = db.get_hackathon_by_slug(identifier)
        
        if not hackathon:
            raise HTTPException(status_code=404, detail="Hackathon not found")
        
        return {
            "id": hackathon.get("_id"),
            "name": hackathon.get("name"),
            "slug": hackathon.get("slug"),
            "tagline": hackathon.get("tagline"),
            "about": hackathon.get("about"),
            "organizer": hackathon.get("organizer_name"),
            "mode": hackathon.get("mode"),
            "start_datetime": hackathon.get("start_datetime"),
            "end_datetime": hackathon.get("end_datetime"),
            "registration_open": hackathon.get("is_registration_open"),
            "team_size": {
                "min": hackathon.get("min_team_size"),
                "max": hackathon.get("max_team_size")
            },
            "themes_count": len(hackathon.get("themes", [])),
            "phases_count": len(hackathon.get("phases", [])),
            "total_participants": hackathon.get("total_participants", 0)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "api_version": "1.0.0"
    }

@app.get("/")
async def root():
    """API information"""
    return {
        "name": "Hackathon Support Chatbot API",
        "version": "1.0.0",
        "provider": "Groq (FREE)",
        "model": "llama-3.3-70b-versatile",
        "documentation": "/docs"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)