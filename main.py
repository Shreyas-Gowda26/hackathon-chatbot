from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
from groq import Groq
import os
from datetime import datetime
from dotenv import load_dotenv
from database import db

load_dotenv()

app = FastAPI(
    title="Hackathon Support Chatbot API",
    description="AI-powered chatbot using Groq (FREE)",
    version="1.0.0"
)

# CORS Configuration
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
    hackathon_id: str  # Required, no more optional

class ChatResponse(BaseModel):
    answer: str  # Now contains proper markdown
    confidence: str
    timestamp: str

class HackathonDataRequest(BaseModel):
    hackathon_data: Dict[str, Any]

# System Prompt
SYSTEM_PROMPT = """You are an official Hackathon Support Assistant.
Your responsibility is to help participants, mentors, and organizers by answering questions
STRICTLY using the provided hackathon data.

Rules you MUST follow:
1. Use ONLY the information given in the context.
2. Do NOT assume, guess, or add any information outside the provided data.
3. If specific information is not found but related information exists, provide what IS available and mention what's missing.
4. Only say "I'm sorry, I couldn't find this information" if NOTHING relevant to the question is in the context.
5. Be helpful and provide all relevant information from the context.

CRITICAL FORMATTING RULES - YOU MUST FOLLOW EXACTLY:
Your response will be displayed in a markdown renderer, so format accordingly:

For lists of multiple items, use this EXACT format:

The hackathon has four problem statements:

**1. AI-Powered Smart Assistant** (AI Machine Learning)
- Build an intelligent assistant for daily tasks
- Features: NLP, task automation, voice interaction

**2. Digital Payment Solution** (Fintech)
- Create a secure payment platform  
- Features: Multi-platform support, real-time tracking

**3. Health Monitoring System** (Healthtech)
- Develop a health tracking solution
- Features: Real-time data, AI insights, wearable integration

**4. Green Energy Management** (Sustainability)
- Build an energy optimization solution
- Features: Energy tracking, renewable optimization

For short answers (1-2 items), write naturally without formatting.
For 3+ items, ALWAYS use the numbered format above.
Use proper markdown with ** for bold.
Add blank lines between sections for readability.

Your goal is to provide reliable, official answers that render beautifully in markdown."""

def extract_relevant_sections(hackathon_data: Dict[str, Any], question: str) -> str:
    """Extract relevant sections from hackathon data based on question keywords.
    Returns comprehensive context to ensure AI has enough information."""
    from datetime import datetime, timezone
    
    question_lower = question.lower()
    sections = []
    matched_categories = []
    
    # Helper function to check if registration is actually open
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
                return "upcoming"
            elif now > end:
                return "ended"
            else:
                return "ongoing"
        except:
            return "unknown"
    
    # Registration-related keywords (expanded)
    registration_keywords = ['register', 'registration', 'sign up', 'join', 'participate', 'enroll', 'apply']
    if any(word in question_lower for word in registration_keywords):
        matched_categories.append('registration')
        reg_phase = next((p for p in hackathon_data.get('phases', []) if p.get('type') == 'registration'), None)
        if reg_phase:
            sections.append("=== REGISTRATION INFORMATION ===")
            sections.append(f"Registration Period: {reg_phase.get('start_datetime')} to {reg_phase.get('end_datetime')}")
            
            # Real-time status
            is_open = is_registration_currently_open()
            sections.append(f"Current Status: {'✅ OPEN - You can register now!' if is_open else '❌ CLOSED - Registration has ended'}")
            sections.append(f"Description: {reg_phase.get('description', 'Registration period for the hackathon')}")
            
            # Add registration questions if available
            if hackathon_data.get('registration_questions'):
                sections.append("\nRegistration Questions Required:")
                for q in hackathon_data['registration_questions']:
                    req_text = "Required" if q.get('required') else "Optional"
                    sections.append(f"  - {q.get('label')} ({q.get('type')}) - {req_text}")
    
    # Team-related keywords (expanded)
    team_keywords = ['team', 'size', 'member', 'solo', 'group', 'individual', 'alone', 'partner', 'collaborate']
    if any(word in question_lower for word in team_keywords):
        matched_categories.append('team')
        sections.append("\n=== TEAM SIZE INFORMATION ===")
        min_size = hackathon_data.get('min_team_size', 'Not specified')
        max_size = hackathon_data.get('max_team_size', 'Not specified')
        sections.append(f"Minimum team size: {min_size}")
        sections.append(f"Maximum team size: {max_size}")
        
        # Add interpretation
        if min_size == 1 and max_size == 1:
            sections.append("This is a SOLO hackathon - only individual participation is allowed.")
        elif min_size == 1:
            sections.append(f"Solo participation is allowed. Teams can have up to {max_size} members.")
    
    # Themes & Problem Statements keywords (expanded)
    theme_keywords = ['theme', 'track', 'problem', 'challenge', 'topic', 'category', 'domain', 'statement']
    if any(word in question_lower for word in theme_keywords):
        matched_categories.append('themes')
        sections.append("\n=== THEMES AND PROBLEM STATEMENTS ===")
        themes = hackathon_data.get('themes', [])
        sections.append(f"Total number of themes: {len(themes)}")
        
        for idx, theme in enumerate(themes, 1):
            sections.append(f"\n{idx}. {theme['name']}")
            sections.append(f"   Description: {theme.get('description', 'No description available')}")
            
            # Problem statements for this theme
            problem_statements = theme.get('problem_statements', [])
            if problem_statements:
                sections.append(f"   Problem Statements ({len(problem_statements)}):")
                for ps in problem_statements:
                    sections.append(f"     • {ps['name']}")
                    sections.append(f"       {ps.get('description', '')}")
    
    # Timeline/Phases keywords (expanded)
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
            
            # Submission requirements
            if phase.get('submission_questions'):
                sections.append(f"   Submission Requirements:")
                for sq in phase['submission_questions']:
                    req = "Required" if sq.get('required') else "Optional"
                    sections.append(f"     - {sq.get('label')} (Type: {sq.get('type')}) - {req}")
            
            # Elimination info
            if phase.get('is_elimination_round'):
                sections.append(f"   ⚠️ This is an ELIMINATION ROUND")
            
            sections.append(f"   Evaluator: {phase.get('evaluator', 'Not specified')}")
    
    # Evaluation/Judging keywords (expanded)
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
    
    # Resources keywords (expanded)
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
    
    # Prizes keywords
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
    
    # Events keywords
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
    
    # Contact/Links keywords
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
    
    # Mentors keywords (NEW!)
    mentor_keywords = ['mentor', 'mentors', 'mentorship', 'guide', 'advisor', 'expert']
    if any(word in question_lower for word in mentor_keywords):
        matched_categories.append('mentors')
        mentors = hackathon_data.get('mentors', [])
        sections.append("\n=== MENTORS ===")
        if mentors and len(mentors) > 0:
            sections.append(f"Total mentors: {len(mentors)}")
            for mentor in mentors:
                # Handle different mentor data structures
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
    
    # Judges keywords (NEW!)
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
    
    # Partners/Sponsors keywords (NEW!)
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
    
    # FAQ keywords (NEW!)
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
    
    # Rules keywords (NEW!)
    rules_keywords = ['rule', 'rules', 'regulation', 'regulations', 'guideline', 'guidelines', 'policy']
    if any(word in question_lower for word in rules_keywords):
        matched_categories.append('rules')
        rules = hackathon_data.get('rules')
        sections.append("\n=== RULES & REGULATIONS ===")
        if rules:
            sections.append(rules)
        else:
            sections.append("Detailed rules will be published soon.")
    
    # Eligibility keywords (NEW!)
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
    
    # Location/Venue keywords (NEW!)
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
    
    # Announcements keywords (NEW!)
    announcement_keywords = ['announcement', 'announcements', 'update', 'updates', 'news', 'latest']
    if any(word in question_lower for word in announcement_keywords):
        matched_categories.append('announcements')
        announcements = hackathon_data.get('announcements')
        sections.append("\n=== ANNOUNCEMENTS ===")
        if announcements:
            sections.append(announcements)
        else:
            sections.append("No announcements at this time. Check back later for updates.")
    
    # Statistics keywords (NEW!)
    stats_keywords = ['how many', 'participants', 'registered', 'views', 'popular']
    if any(word in question_lower for word in stats_keywords):
        matched_categories.append('stats')
        sections.append("\n=== PARTICIPATION STATISTICS ===")
        total_participants = hackathon_data.get('total_participants', 0)
        total_views = hackathon_data.get('total_views', 0)
        sections.append(f"Total Registered Participants: {total_participants}")
        sections.append(f"Total Page Views: {total_views}")
    
    # Tags/Categories keywords (NEW!)
    tag_keywords = ['tag', 'tags', 'category', 'categories', 'industry', 'type']
    if any(word in question_lower for word in tag_keywords):
        matched_categories.append('tags')
        tags = hackathon_data.get('tags', [])
        industry = hackathon_data.get('industry')
        hackathon_type = hackathon_data.get('type')
        
        sections.append("\n=== HACKATHON CATEGORY ===")
        if hackathon_type:
            sections.append(f"Type: {hackathon_type.capitalize()}")
        if industry:
            sections.append(f"Industry: {industry.capitalize()}")
        if tags and len(tags) > 0:
            sections.append(f"Tags: {', '.join(tags)}")
    
    # Winners keywords (NEW!)
    winner_keywords = ['winner', 'winners', 'result', 'results', 'who won']
    if any(word in question_lower for word in winner_keywords):
        matched_categories.append('winners')
        sections.append("\n=== WINNERS ===")
        is_announced = hackathon_data.get('is_winners_announced', False)
        if is_announced:
            sections.append("Winners have been announced!")
            # You can add more winner details here if available in your data
        else:
            sections.append("Winners will be announced after the hackathon concludes.")
    
    # Contact details (separate from links) (NEW!)
    if any(word in question_lower for word in ['email', 'phone', 'call', 'contact number']):
        matched_categories.append('contact_details')
        contact_details = hackathon_data.get('contact_details', [])
        if contact_details and len(contact_details) > 0:
            sections.append("\n=== CONTACT DETAILS ===")
            for contact in contact_details:
                if isinstance(contact, dict):
                    name = contact.get('name', 'Contact')
                    email = contact.get('email', '')
                    phone = contact.get('phone', '')
                    sections.append(f"\n• {name}")
                    if email:
                        sections.append(f"  Email: {email}")
                    if phone:
                        sections.append(f"  Phone: {phone}")
                elif isinstance(contact, str):
                    sections.append(f"• {contact}")
    
    # If no specific category matched OR if question is general, provide overview
    if not matched_categories or any(word in question_lower for word in ['about', 'overview', 'general', 'info', 'tell me', 'what is', 'status', 'when']):
        hackathon_status = get_hackathon_status()
        status_emoji = {"upcoming": "🔜", "ongoing": "🚀", "ended": "✅", "unknown": "❓"}
        
        sections.insert(0, "=== HACKATHON OVERVIEW ===")
        sections.insert(1, f"Name: {hackathon_data.get('name')}")
        sections.insert(2, f"Status: {status_emoji.get(hackathon_status, '')} {hackathon_status.upper()}")
        sections.insert(3, f"Tagline: {hackathon_data.get('tagline')}")
        sections.insert(4, f"About: {hackathon_data.get('about')}")
        sections.insert(5, f"Organizer: {hackathon_data.get('organizer_name')}")
        sections.insert(6, f"Mode: {hackathon_data.get('mode')}")
        sections.insert(7, f"Duration: {hackathon_data.get('start_datetime')} to {hackathon_data.get('end_datetime')}")
        sections.insert(8, f"Total Participants: {hackathon_data.get('total_participants', 0)}")
        sections.insert(9, "")
    
    return "\n".join(sections)

@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Main chat endpoint - processes user questions"""
    try:
        # Get hackathon data
        if not request.hackathon_id:
            raise HTTPException(status_code=400, detail="hackathon_id is required")
        
        hackathon_data = db.get_hackathon_by_id(request.hackathon_id)
        
        if not hackathon_data:
            raise HTTPException(status_code=404, detail="Hackathon not found")
        
        # Extract relevant context
        context = extract_relevant_sections(hackathon_data, request.question)
        
        # Build prompt
        user_prompt = f"""Context:
{context}

User Question: {request.question}

Answer (use proper markdown formatting):"""
        
        # Call Groq API (GPT-compatible)
        chat_completion = groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # FREE and FAST
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=800  # Increased for better formatted responses
        )
        
        answer = chat_completion.choices[0].message.content.strip()
        confidence = "low" if "couldn't find" in answer.lower() else "high"
        
        return ChatResponse(
            answer=answer,
            confidence=confidence,
            timestamp=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/admin/import-hackathon")
async def import_hackathon(data: HackathonDataRequest):
    """Import a single hackathon data into database"""
    try:
        # Clean the data before inserting
        import re
        
        def clean_string(text):
            """Remove invalid control characters"""
            if not isinstance(text, str):
                return text
            # Remove problematic control characters
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
        
        cleaned_data = clean_data(data.hackathon_data)
        
        success = db.insert_hackathon(cleaned_data)
        if success:
            return {
                "status": "success",
                "message": "Hackathon data imported successfully",
                "hackathon_id": cleaned_data.get("_id"),
                "hackathon_name": cleaned_data.get("name")
            }
        raise HTTPException(status_code=500, detail="Failed to import data")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin/import-multiple-hackathons")
async def import_multiple_hackathons(hackathons: List[Dict[str, Any]]):
    """Import multiple hackathons at once"""
    try:
        imported = []
        failed = []
        
        for hackathon_data in hackathons:
            try:
                success = db.insert_hackathon(hackathon_data)
                if success:
                    imported.append({
                        "id": hackathon_data.get("_id"),
                        "name": hackathon_data.get("name")
                    })
                else:
                    failed.append({
                        "id": hackathon_data.get("_id"),
                        "name": hackathon_data.get("name"),
                        "error": "Insert failed"
                    })
            except Exception as e:
                failed.append({
                    "id": hackathon_data.get("_id"),
                    "name": hackathon_data.get("name"),
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
    """List all hackathons with chatbot support"""
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
        # Try to fetch by ID first, then by slug
        hackathon = db.get_hackathon_by_id(identifier)
        if not hackathon:
            hackathon = db.get_hackathon_by_slug(identifier)
        
        if not hackathon:
            raise HTTPException(status_code=404, detail="Hackathon not found")
        
        # Return sanitized version (remove internal fields if needed)
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
        "provider": "Groq",
        "model": "llama-3.3-70b-versatile"
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