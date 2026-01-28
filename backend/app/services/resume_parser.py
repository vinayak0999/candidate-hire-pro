"""
Resume Parser Service using Gemini for intelligent OCR and data extraction.
Converts PDF resumes to images and extracts structured data with LLM.
"""
import io
import json
import base64
from typing import List, Optional
from pydantic import BaseModel, Field
import fitz  # PyMuPDF

from ..config import get_settings

settings = get_settings()

# Lazy initialization of Gemini client
_genai_client = None

def get_genai_client():
    """Get the Gemini client, initializing lazily if needed."""
    global _genai_client
    if _genai_client is None:
        try:
            from google import genai
            if settings.gemini_api_key:
                _genai_client = genai.Client(api_key=settings.gemini_api_key)
            else:
                print("WARNING: GEMINI_API_KEY not set - resume parsing disabled")
                return None
        except ImportError:
            print("WARNING: google-genai package not installed - resume parsing disabled")
            return None
        except Exception as e:
            print(f"WARNING: Failed to initialize Gemini client: {e}")
            return None
    return _genai_client


# ============================================================================
# Pydantic Schemas for Validated Output
# ============================================================================

class PersonalInfo(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    linkedin_url: Optional[str] = None
    github_url: Optional[str] = None
    portfolio_url: Optional[str] = None
    location: Optional[str] = None


class EducationEntry(BaseModel):
    school: str
    degree: Optional[str] = None
    field_of_study: Optional[str] = None
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    gpa: Optional[str] = None


class WorkExperienceEntry(BaseModel):
    company: str
    role: str
    city: Optional[str] = None
    country: Optional[str] = None
    start_date: Optional[str] = None  # YYYY-MM format
    end_date: Optional[str] = None
    is_current: bool = False
    description: Optional[str] = None


class ProjectEntry(BaseModel):
    name: str
    description: Optional[str] = None
    technologies: List[str] = Field(default_factory=list)
    start_year: Optional[int] = None
    end_year: Optional[int] = None
    url: Optional[str] = None


class SkillEntry(BaseModel):
    name: str
    category: Optional[str] = None  # language, framework, database, cloud, tool, soft_skill
    proficiency: Optional[str] = None  # expert, intermediate, beginner


class CertificationEntry(BaseModel):
    title: str
    issuer: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None


class PublicationEntry(BaseModel):
    title: str
    publisher: Optional[str] = None
    year: Optional[int] = None
    url: Optional[str] = None


class AwardEntry(BaseModel):
    title: str
    issuer: Optional[str] = None
    year: Optional[int] = None


class LanguageEntry(BaseModel):
    language: str
    proficiency: Optional[str] = None  # native, fluent, intermediate, basic


class CodingProfiles(BaseModel):
    leetcode: Optional[str] = None
    github: Optional[str] = None
    codechef: Optional[str] = None
    codeforces: Optional[str] = None


class ParsedResume(BaseModel):
    """Complete parsed resume schema"""
    personal_info: PersonalInfo = Field(default_factory=PersonalInfo)
    professional_summary: Optional[str] = None
    years_of_experience: Optional[float] = None
    current_role: Optional[str] = None
    current_company: Optional[str] = None
    education: List[EducationEntry] = Field(default_factory=list)
    work_experience: List[WorkExperienceEntry] = Field(default_factory=list)
    projects: List[ProjectEntry] = Field(default_factory=list)
    skills: List[SkillEntry] = Field(default_factory=list)
    certifications: List[CertificationEntry] = Field(default_factory=list)
    publications: List[PublicationEntry] = Field(default_factory=list)
    awards: List[AwardEntry] = Field(default_factory=list)
    languages: List[LanguageEntry] = Field(default_factory=list)
    coding_profiles: CodingProfiles = Field(default_factory=CodingProfiles)


# ============================================================================
# Resume Parsing Prompt
# ============================================================================

RESUME_PARSER_PROMPT = """
╔══════════════════════════════════════════════════════════════════════════════════════════════════════╗
║                           ENTERPRISE RESUME PARSER v3.0 - PRODUCTION GRADE                          ║
║                    Competitive with: Sovren, Textkernel, HireAbility, DaXtra, Affinda               ║
╚══════════════════════════════════════════════════════════════════════════════════════════════════════╝

You are an enterprise-grade Intelligent Document Processing (IDP) system specialized in resume/CV parsing.
Your parsing accuracy must meet or exceed industry standards (95%+ field-level accuracy).

══════════════════════════════════════════════════════════════════════════════════════════════════════
MODULE 1: DOCUMENT INTELLIGENCE & PRE-PROCESSING
══════════════════════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1.1 OCR ERROR CORRECTION MATRIX                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

CHARACTER SUBSTITUTION PATTERNS:
┌────────────┬────────────────────────────────────────────────────────────────────────────────────────┐
│ Pattern    │ Corrections                                                                            │
├────────────┼────────────────────────────────────────────────────────────────────────────────────────┤
│ Letters    │ 0↔O, 1↔l↔I↔|, rn↔m, cl↔d, vv↔w, ii↔u, fi↔fi, fl↔fl, ff↔ff, S↔5, B↔8, Z↔2, g↔q       │
│ Symbols    │ @↔©↔®, &↔8, #↔H, *↔×, "↔"↔", '↔'↔`, —↔-↔–, •↔·↔°↔*, ©↔(c), ®↔(R)                     │
│ Spaces     │ Collapsed spaces, missing spaces after periods, random line breaks mid-word           │
│ Unicode    │ Smart quotes→straight quotes, em-dash→hyphen, non-breaking spaces→regular spaces      │
│ Ligatures  │ ﬁ→fi, ﬂ→fl, ﬀ→ff, ﬃ→ffi, ﬄ→ffl, æ→ae, œ→oe                                           │
└────────────┴────────────────────────────────────────────────────────────────────────────────────────┘

EMAIL RECONSTRUCTION:
- Pattern: [word]@[word].[tld] or [word] @ [word] . [tld] or [word](at)[word](dot)[tld]
- Fix: "john.doe © gmail corn" → "john.doe@gmail.com"
- Fix: "contact (at) company (dot) io" → "contact@company.io"
- Validate TLDs: com, org, net, io, co, edu, gov, me, dev, ai, app, tech, xyz, info, biz

PHONE RECONSTRUCTION:
- Patterns: +1-xxx-xxx-xxxx, (xxx) xxx-xxxx, xxx.xxx.xxxx, +91 xxxxx xxxxx, +44 xxxx xxxxxx
- Fix spacing/OCR: "÷1 555 123 4567" → "+1 555 123 4567"
- Normalize to E.164 format internally but preserve original display format
- Detect country from prefix or location context

URL RECONSTRUCTION:
- Fix: "github corn/username" → "github.com/username"
- Fix: "linkedin corn/in/name" → "linkedin.com/in/name"
- Fix: "www ·company· corn" → "www.company.com"
- Reconstruct protocols: assume https:// if missing
- Validate domains: github.com, linkedin.com, gitlab.com, bitbucket.org, stackoverflow.com, medium.com, dev.to

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1.2 MULTI-LANGUAGE & INTERNATIONAL SUPPORT                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

SUPPORTED LANGUAGES: English, Spanish, French, German, Portuguese, Italian, Dutch, Polish, Russian,
Chinese (Simplified/Traditional), Japanese, Korean, Hindi, Arabic, Hebrew, Turkish, Vietnamese, Thai

LOCALE-SPECIFIC PARSING:
┌─────────────────┬───────────────────────────────────────────────────────────────────────────────────┐
│ Region          │ Handling Rules                                                                    │
├─────────────────┼───────────────────────────────────────────────────────────────────────────────────┤
│ US/Canada       │ Phone: +1, Resume term, GPA scale 4.0, MM/DD/YYYY dates, ZIP codes               │
│ UK/Ireland      │ Phone: +44/+353, CV term, Degree classification (First, 2:1, 2:2), DD/MM/YYYY    │
│ EU (DACH)       │ Phone: +49/+41/+43, Lebenslauf, grades 1.0-5.0 (1.0 best), DD.MM.YYYY            │
│ EU (France)     │ Phone: +33, CV, grades /20 scale, DD/MM/YYYY, photo common                       │
│ India           │ Phone: +91, CV/Resume, percentage/CGPA, DD/MM/YYYY, 10+2+3/4 education           │
│ China           │ Phone: +86, 简历, GPA 4.0/5.0, YYYY/MM/DD, age/DOB common                         │
│ Japan           │ Phone: +81, 履歴書, Japanese calendar years option, YYYY/MM/DD                   │
│ Middle East     │ Phone: +966/+971/+20, CV, may include nationality/religion, DD/MM/YYYY          │
│ LATAM           │ Phone: varies, CV/Currículo/Hoja de Vida, DD/MM/YYYY                            │
│ Australia/NZ    │ Phone: +61/+64, CV/Resume, DD/MM/YYYY                                           │
└─────────────────┴───────────────────────────────────────────────────────────────────────────────────┘

NAME PARSING BY CULTURE:
- Western: [First] [Middle?] [Last] - "John Michael Smith"
- Hispanic: [First] [Paternal Surname] [Maternal Surname] - "Carlos García López"
- Chinese: [Family] [Given] OR westernized [Given] [Family] - "Wang Wei" or "Wei Wang"
- Japanese: [Family] [Given] - "Tanaka Yuki" (detect by kanji/context)
- Korean: [Family] [Given] - "Kim Min-jun"
- Arabic: [Given] [Father's name] [Family] + honorifics - handle "bin", "ibn", "al-"
- Indian: [First] [Middle/Father's?] [Last/Caste?] - highly variable, preserve as-is

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 1.3 DOCUMENT STRUCTURE RECOGNITION                                                                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

SECTION HEADERS (Multi-language + variations):
{
  "contact": ["contact", "personal information", "personal details", "info", "reach me", "coordonnées", "kontakt", "contacto", "contato", "联系方式", "連絡先"],
  "summary": ["summary", "professional summary", "executive summary", "profile", "about", "about me", "objective", "career objective", "personal statement", "overview", "introduction", "résumé", "profil", "zusammenfassung", "resumen", "perfil", "简介", "概要"],
  "experience": ["experience", "work experience", "professional experience", "employment", "employment history", "work history", "career history", "professional background", "positions held", "expérience", "berufserfahrung", "experiencia", "经历", "職歴"],
  "education": ["education", "academic background", "academic history", "qualifications", "academic qualifications", "educational background", "studies", "formation", "ausbildung", "educación", "formação", "学历", "学歴"],
  "skills": ["skills", "technical skills", "core competencies", "competencies", "expertise", "proficiencies", "technologies", "tech stack", "tools", "abilities", "compétences", "fähigkeiten", "habilidades", "技能", "スキル"],
  "projects": ["projects", "personal projects", "side projects", "portfolio", "key projects", "selected projects", "academic projects", "projets", "projekte", "proyectos", "项目", "プロジェクト"],
  "certifications": ["certifications", "certificates", "credentials", "licenses", "professional certifications", "accreditations", "certifications professionnelles", "zertifikate", "certificaciones", "证书", "資格"],
  "publications": ["publications", "papers", "research", "research papers", "articles", "patents", "publications académiques", "veröffentlichungen", "publicaciones", "论文", "出版物"],
  "awards": ["awards", "honors", "achievements", "recognition", "accomplishments", "distinctions", "prix", "auszeichnungen", "premios", "荣誉", "受賞"],
  "languages": ["languages", "language skills", "language proficiency", "langues", "sprachen", "idiomas", "语言", "言語"],
  "interests": ["interests", "hobbies", "activities", "extracurricular", "volunteer", "volunteering", "intérêts", "interessen", "intereses", "兴趣", "趣味"],
  "references": ["references", "referees", "références", "referenzen", "referencias", "推荐人", "参照"]
}

LAYOUT DETECTION:
- Single column (traditional)
- Two column (modern - skills sidebar)
- Multi-section grid (creative/design)
- Chronological vs Functional vs Combination format
- Detect header/footer (ignore page numbers, "Page X of Y", repeated headers)

══════════════════════════════════════════════════════════════════════════════════════════════════════
MODULE 2: NAMED ENTITY RECOGNITION (NER) & EXTRACTION
══════════════════════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2.1 PERSONAL INFORMATION EXTRACTION                                                                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

ENTITY EXTRACTION RULES:
┌──────────────────┬──────────────────────────────────────────────────────────────────────────────────┐
│ Entity           │ Extraction Logic                                                                 │
├──────────────────┼──────────────────────────────────────────────────────────────────────────────────┤
│ Full Name        │ Usually largest font at top, or after "Name:" label. Preserve original casing.  │
│ Email            │ Regex: [\w\.-]+@[\w\.-]+\.\w+ - validate format, fix OCR errors                 │
│ Phone            │ Multiple allowed, detect mobile vs landline vs work, include country code       │
│ LinkedIn         │ linkedin.com/in/[handle] - extract handle, reconstruct full URL                 │
│ GitHub           │ github.com/[username] - extract username, validate exists pattern               │
│ Portfolio        │ Any other URL, personal domains, Behance, Dribbble, etc.                       │
│ Location         │ City, State/Province, Country - normalize to standard format                    │
│ Address          │ Full street address if provided (common in some regions)                        │
│ Nationality      │ If stated (common in EU/Middle East CVs)                                        │
│ Date of Birth    │ If stated (common in some regions) - YYYY-MM-DD format                          │
│ Visa Status      │ Work authorization, citizenship, visa type if mentioned                         │
│ Driving License  │ If mentioned (common for some roles/regions)                                    │
└──────────────────┴──────────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2.2 PROFESSIONAL SUMMARY GENERATION ENGINE                                                          │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

█▀▀ BANNED PHRASES - AUTOMATIC REJECTION █▀▀
These indicate low-quality, non-substantive summaries. NEVER use:

CATEGORY: Empty Enthusiasm
✗ "Highly motivated" | "Passionate about" | "Enthusiastic" | "Dedicated" | "Driven"
✗ "Eager to learn" | "Fast learner" | "Self-starter" | "Go-getter" | "Dynamic"
✗ "Hardworking" | "Diligent" | "Committed" | "Ambitious" | "Energetic"

CATEGORY: Generic Claims
✗ "Results-driven" | "Results-oriented" | "Detail-oriented" | "Goal-oriented"
✗ "Proven track record" | "Strong track record" | "Demonstrated ability"
✗ "Excellent communication skills" | "Strong interpersonal skills" | "Team player"
✗ "Problem solver" | "Critical thinker" | "Strategic thinker" | "Innovative thinker"

CATEGORY: Meaningless Phrases
✗ "Seeking opportunities" | "Looking to leverage" | "Seeking to contribute"
✗ "Bringing value" | "Adding value" | "Making an impact" | "Making a difference"
✗ "In a fast-paced environment" | "Cutting-edge" | "Best practices" | "Synergy"
✗ "Think outside the box" | "Hit the ground running" | "Wear many hats"

CATEGORY: Filler Language
✗ "Responsible for" | "Duties included" | "Worked on various" | "Involved in"
✗ "Assisted with" | "Helped with" | "Participated in" | "Contributed to" (vague usage)

█▀▀ SUMMARY CONSTRUCTION ALGORITHM █▀▀

STEP 1: Extract Core Identity
- Current/Most Recent Title: Extract exact job title
- Seniority Level: Junior/Mid/Senior/Staff/Principal/Director/VP/C-level (infer from titles/years)
- Primary Domain: What industry/vertical? (Fintech, Healthcare, E-commerce, SaaS, etc.)
- Company Type: Startup/Scale-up/Enterprise/Agency/Consulting/FAANG

STEP 2: Identify Differentiators
- Technical Specialization: Core technical stack or methodology
- Quantified Achievements: Numbers, metrics, scale, impact (prioritize these!)
- Domain Expertise: Specific business domain knowledge
- Leadership Scope: Team size, budget, cross-functional exposure

STEP 3: Construct Summary Using Template

TEMPLATE A - Technical Individual Contributor:
"[Seniority] [Role] specializing in [Technical Domain] with [X years/extensive] experience in [Industry]. [Specific Achievement with Metric]. Core stack: [Top 3-5 Technologies]. [Education if notable - Top school, PhD, etc.]"

TEMPLATE B - Engineering Leadership:
"[Title] with [X years] leading [Team Size] engineers at [Company Type/Industry]. [Scale Achievement - users/revenue/systems]. Expertise in [Technical + Leadership Domain]. Previously at [Notable Company if applicable]."

TEMPLATE C - Product/Business Roles:
"[Role] with [Industry] experience driving [Metric - revenue/growth/users]. [Specific Achievement]. Background in [Relevant Domain]. [Education/Certification if relevant]."

TEMPLATE D - Early Career/New Grad:
"[Degree] graduate from [University] specializing in [Field]. [Project/Internship highlight with specific tech/achievement]. Proficient in [Core Technologies]."

█▀▀ EXEMPLARY SUMMARIES (Study These) █▀▀

EXCELLENT - Senior Engineer:
"Staff Backend Engineer with 8 years building distributed systems at fintech scale. Architected event-driven payment platform processing $2B+ daily transactions at Stripe. Deep expertise in Go, Kafka, and PostgreSQL. Previously scaled search infrastructure at Yelp from 10M to 100M queries/day. MS CS Stanford."

EXCELLENT - Engineering Manager:
"Engineering Manager leading 12-person platform team at Series D healthtech startup. Reduced infrastructure costs by 40% ($1.2M annually) while improving system reliability to 99.95% uptime. Background in distributed systems at AWS. Built teams from 3→15 engineers across two organizations."

EXCELLENT - Data Scientist:
"Senior Data Scientist focused on NLP and recommendation systems with 6 years in e-commerce. Deployed personalization models serving 50M users, driving 15% increase in conversion. Expert in Python, PyTorch, and MLOps (SageMaker, MLflow). PhD Machine Learning, CMU."

EXCELLENT - New Grad:
"CS graduate from Georgia Tech (3.9 GPA) with distributed systems focus. Built open-source Raft consensus implementation in Rust with 2K+ GitHub stars. Internships at Google (Search Quality) and Databricks (Query Optimization). Proficient in Rust, Go, and C++."

EXCELLENT - Product Manager:
"Senior Product Manager with 7 years in B2B SaaS driving $50M+ ARR products. Led 0→1 launch of enterprise analytics platform at Mixpanel, achieving 200% YoY growth. Background in data engineering. MBA Wharton, BS CS Berkeley."

EXCELLENT - Career Changer:
"Software Engineer transitioning from 5 years in mechanical engineering. Completed Bradfield CS intensive and built production ML pipeline for predictive maintenance (Python, TensorFlow). Combining domain expertise in manufacturing with software skills."

BAD EXAMPLES (Never produce these):
✗ "Highly motivated software engineer passionate about technology seeking opportunities to leverage skills in a dynamic environment."
✗ "Results-driven professional with excellent communication skills and proven track record of success."
✗ "Dedicated team player with strong problem-solving abilities looking to make an impact."

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2.3 WORK EXPERIENCE EXTRACTION ENGINE                                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

COMPANY NAME NORMALIZATION:
- Expand abbreviations: "MSFT" → "Microsoft", "AMZN" → "Amazon", "FB" → "Meta (Facebook)"
- Standardize suffixes: "Inc.", "LLC", "Ltd.", "Corp.", "GmbH", "S.A.", "Pty Ltd" - preserve but normalize formatting
- Handle acquisitions: Note if company was acquired (e.g., "Tableau (acquired by Salesforce)")
- Detect subsidiaries: "AWS" → company: "Amazon Web Services (AWS)", parent: "Amazon"
- Stealth/Confidential: Preserve "Confidential" or "Stealth Startup" as-is

KNOWN COMPANY DATABASE (Normalize to these):
FAANG+: Google, Amazon, Apple, Meta (Facebook), Netflix, Microsoft, Nvidia, Tesla, OpenAI, Anthropic
Enterprise: IBM, Oracle, SAP, Salesforce, Adobe, VMware, Cisco, Intel, Dell, HP, ServiceNow
Unicorns: Stripe, Airbnb, DoorDash, Coinbase, Databricks, Snowflake, Figma, Notion, Canva, Klarna
Consulting: McKinsey, BCG, Bain, Deloitte, Accenture, PwC, EY, KPMG, Capgemini, Infosys, TCS, Wipro
Finance: Goldman Sachs, JP Morgan, Morgan Stanley, Citadel, Two Sigma, Jane Street, DE Shaw, Bridgewater
(Match common variations and abbreviations to canonical names)

JOB TITLE STANDARDIZATION:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Preserve original title but also provide normalized_title from this taxonomy:                       │
├─────────────────────────────────────────────────────────────────────────────────────────────────────┤
│ ENGINEERING TRACK:                                                                                  │
│ Junior/Associate Engineer → Software Engineer I → Software Engineer II → Senior Engineer →         │
│ Staff Engineer → Principal Engineer → Distinguished Engineer → Fellow                               │
│                                                                                                     │
│ MANAGEMENT TRACK:                                                                                   │
│ Tech Lead → Engineering Manager → Senior EM → Director of Engineering → VP Engineering →           │
│ SVP Engineering → CTO                                                                               │
│                                                                                                     │
│ PRODUCT TRACK:                                                                                      │
│ Associate PM → Product Manager → Senior PM → Group PM → Director of Product → VP Product → CPO     │
│                                                                                                     │
│ DATA TRACK:                                                                                         │
│ Data Analyst → Senior Analyst → Data Scientist → Senior DS → Staff DS → Principal DS →             │
│ Data Science Manager → Director of DS → VP Data/ML → Chief Data Officer                            │
│                                                                                                     │
│ DESIGN TRACK:                                                                                       │
│ Junior Designer → Designer → Senior Designer → Staff Designer → Principal Designer →                │
│ Design Manager → Director of Design → VP Design → CDO                                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

DATE PARSING COMPREHENSIVE:
┌─────────────────────────┬─────────────────────────────────────────────────────────────────────────┐
│ Input Format            │ Output                                                                  │
├─────────────────────────┼─────────────────────────────────────────────────────────────────────────┤
│ "Present", "Current"    │ end_date: null, is_current: true                                       │
│ "Now", "Ongoing"        │ end_date: null, is_current: true                                       │
│ "Jan 2020"              │ "2020-01"                                                               │
│ "January 2020"          │ "2020-01"                                                               │
│ "01/2020" (US)          │ "2020-01"                                                               │
│ "2020/01" (ISO)         │ "2020-01"                                                               │
│ "2020"                  │ "2020"                                                                  │
│ "Q1 2020"               │ "2020-01"                                                               │
│ "Q2 2020"               │ "2020-04"                                                               │
│ "Q3 2020"               │ "2020-07"                                                               │
│ "Q4 2020"               │ "2020-10"                                                               │
│ "Spring 2020"           │ "2020-03"                                                               │
│ "Summer 2020"           │ "2020-06"                                                               │
│ "Fall/Autumn 2020"      │ "2020-09"                                                               │
│ "Winter 2020"           │ "2020-12"                                                               │
│ "H1 2020"               │ "2020-01"                                                               │
│ "H2 2020"               │ "2020-07"                                                               │
│ "Since 2020"            │ start: "2020", is_current: true                                        │
│ "2020 - 2022"           │ start: "2020", end: "2022"                                             │
│ "20'" (abbreviated)     │ "2020"                                                                  │
│ "'20" (abbreviated)     │ "2020"                                                                  │
│ German: "März 2020"     │ "2020-03"                                                               │
│ French: "Janvier 2020"  │ "2020-01"                                                               │
│ Spanish: "Enero 2020"   │ "2020-01"                                                               │
└─────────────────────────┴─────────────────────────────────────────────────────────────────────────┘

DURATION CALCULATION:
- Calculate duration_months from dates
- Calculate total_experience_months across all roles
- Handle overlapping roles (flag, don't double-count for total)
- Handle gaps > 3 months (flag as potential concern)

DESCRIPTION EXTRACTION RULES:
1. Preserve EXACT wording - do not paraphrase or "improve"
2. Fix only obvious OCR errors (not grammar or style)
3. Extract ALL bullet points, not just first few
4. Preserve metrics exactly: "$1.2M" not "over a million dollars"
5. Maintain original action verbs: "Spearheaded" not changed to "Led"
6. Concatenate with " • " separator for structured storage
7. Flag achievements with metrics in separate array

ACHIEVEMENT METRICS EXTRACTION:
Identify and tag quantified achievements:
- Revenue/Cost: $X, Xk, XM, XB, X%
- Scale: X users, X requests/sec, X TB, X QPS
- Performance: X% improvement, Xms latency, X% uptime
- Team: X engineers, X reports, X cross-functional
- Time: X weeks, X% faster, X sprints

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 2.4 EDUCATION EXTRACTION ENGINE                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

INSTITUTION RECOGNITION DATABASE:
Tier 1 (Auto-flag as notable):
- US: MIT, Stanford, Berkeley, CMU, Caltech, Harvard, Princeton, Yale, Cornell, Columbia, UPenn, Georgia Tech, UIUC, Michigan, UT Austin, UCLA, UW
- UK: Oxford, Cambridge, Imperial, UCL, Edinburgh, LSE, Manchester
- Canada: Waterloo, Toronto, UBC, McGill
- Europe: ETH Zurich, EPFL, TU Munich, Delft, KTH, Aalto
- Asia: Tsinghua, Peking, NUS, NTU, HKUST, IIT (all), KAIST, Tokyo, Seoul National
- Online: Lambda School (now BloomTech), App Academy, Hack Reactor, Bradfield, OMSCS (Georgia Tech)

DEGREE NORMALIZATION:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Input                    │ normalized_degree  │ degree_level                                        │
├──────────────────────────┼────────────────────┼─────────────────────────────────────────────────────┤
│ Bachelor's, BS, BA, BSc  │ "Bachelor's"       │ "bachelors"                                         │
│ B.Tech, B.Eng, BE        │ "Bachelor's"       │ "bachelors"                                         │
│ Master's, MS, MA, MSc    │ "Master's"         │ "masters"                                           │
│ M.Tech, M.Eng, ME        │ "Master's"         │ "masters"                                           │
│ MBA                      │ "MBA"              │ "masters"                                           │
│ PhD, Ph.D., Doctorate    │ "PhD"              │ "doctorate"                                         │
│ Associate's, AA, AS      │ "Associate's"      │ "associates"                                        │
│ High School, HSC, GED    │ "High School"      │ "high_school"                                       │
│ Bootcamp, Certificate    │ "Certificate"      │ "certificate"                                       │
│ Diploma                  │ "Diploma"          │ "diploma"                                           │
│ JD, LLB, LLM             │ preserve           │ "professional"                                      │
│ MD, MBBS                 │ preserve           │ "professional"                                      │
└──────────────────────────┴────────────────────┴─────────────────────────────────────────────────────┘

FIELD OF STUDY NORMALIZATION:
- "CS", "Comp Sci" → "Computer Science"
- "EE", "Electrical Eng" → "Electrical Engineering"
- "Econ" → "Economics"
- "Math" → "Mathematics"
- Preserve specializations: "Computer Science (Machine Learning Focus)"
- Handle double majors: ["Computer Science", "Mathematics"]

GPA NORMALIZATION:
- Preserve original format in display_gpa
- Calculate normalized_gpa on 4.0 scale where possible
- Handle: X/4.0, X/5.0, X/10, X%, First/2:1/2:2, Distinction/Merit/Pass, Summa/Magna/Cum Laude
- Flag if GPA >= 3.5/4.0 equivalent as "high_achiever"

HONORS & DISTINCTIONS:
- Summa Cum Laude, Magna Cum Laude, Cum Laude
- First Class Honours, Upper Second (2:1), Lower Second (2:2), Third
- Dean's List, Honor Roll, Valedictorian, Salutatorian
- Scholarships (extract name and value if mentioned)
- Thesis/Dissertation title if mentioned

══════════════════════════════════════════════════════════════════════════════════════════════════════
MODULE 3: SKILLS INTELLIGENCE ENGINE
══════════════════════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3.1 COMPREHENSIVE SKILL TAXONOMY (Industry Standard)                                                │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

CATEGORY: "programming_language"
{
  "general_purpose": ["Python", "Java", "C++", "C", "C#", "Go", "Rust", "Ruby", "Kotlin", "Swift", "Scala", "Perl", "PHP", "Lua", "Dart", "Julia", "R", "MATLAB", "Haskell", "Erlang", "Elixir", "Clojure", "F#", "OCaml", "Groovy", "Visual Basic", "COBOL", "Fortran", "Assembly"],
  "web": ["JavaScript", "TypeScript", "HTML", "CSS", "SCSS", "Sass", "Less", "WebAssembly", "CoffeeScript"],
  "query_data": ["SQL", "PL/SQL", "T-SQL", "HiveQL", "SparkSQL", "GraphQL", "SPARQL", "Cypher"],
  "scripting": ["Bash", "Shell", "PowerShell", "Zsh", "Fish", "Awk", "Sed", "Vim Script"],
  "mobile": ["Swift", "Objective-C", "Kotlin", "Java (Android)", "Dart"],
  "systems": ["C", "C++", "Rust", "Go", "Zig", "Assembly"]
}

CATEGORY: "framework_library"
{
  "frontend": ["React", "React.js", "Angular", "Vue.js", "Vue", "Svelte", "Next.js", "Nuxt.js", "Gatsby", "Remix", "Astro", "SolidJS", "Qwik", "Ember.js", "Backbone.js", "jQuery", "Alpine.js", "HTMX", "Stimulus"],
  "css": ["Tailwind CSS", "Bootstrap", "Material UI", "Chakra UI", "Ant Design", "Styled Components", "Emotion", "Sass", "CSS Modules", "Bulma", "Foundation", "Semantic UI"],
  "backend": ["Node.js", "Express.js", "Express", "Fastify", "Koa", "NestJS", "Django", "Flask", "FastAPI", "Spring Boot", "Spring", "Ruby on Rails", "Rails", "Laravel", "Symfony", "ASP.NET", ".NET Core", "Phoenix", "Gin", "Echo", "Fiber", "Chi", "Actix", "Rocket", "Axum"],
  "mobile": ["React Native", "Flutter", "SwiftUI", "UIKit", "Jetpack Compose", "Xamarin", "Ionic", "Cordova", "NativeScript", "Expo"],
  "ml_ai": ["TensorFlow", "PyTorch", "Keras", "scikit-learn", "XGBoost", "LightGBM", "CatBoost", "Hugging Face Transformers", "JAX", "MLflow", "Kubeflow", "Ray", "OpenCV", "spaCy", "NLTK", "Gensim", "LangChain", "LlamaIndex", "AutoML", "H2O"],
  "data": ["Pandas", "NumPy", "SciPy", "Polars", "Dask", "Vaex", "PySpark", "Apache Beam", "dbt", "Airflow", "Prefect", "Dagster", "Great Expectations", "Feast"],
  "testing": ["Jest", "Mocha", "Cypress", "Playwright", "Selenium", "Puppeteer", "pytest", "unittest", "JUnit", "TestNG", "RSpec", "Capybara", "Detox", "Appium"],
  "api": ["REST", "GraphQL", "gRPC", "tRPC", "OpenAPI", "Swagger", "Postman", "Apollo", "Relay"],
  "orm": ["SQLAlchemy", "Django ORM", "Prisma", "TypeORM", "Sequelize", "Hibernate", "Entity Framework", "ActiveRecord", "Mongoose", "Drizzle"]
}

CATEGORY: "database"
{
  "relational": ["PostgreSQL", "MySQL", "MariaDB", "SQL Server", "Oracle", "SQLite", "CockroachDB", "YugabyteDB", "TiDB", "Vitess", "PlanetScale", "Neon", "Supabase"],
  "nosql_document": ["MongoDB", "Couchbase", "CouchDB", "Firebase Firestore", "Amazon DocumentDB", "Azure Cosmos DB"],
  "nosql_keyvalue": ["Redis", "Memcached", "DynamoDB", "Riak", "etcd", "Consul", "Valkey"],
  "nosql_columnar": ["Cassandra", "ScyllaDB", "HBase", "Google Bigtable"],
  "search": ["Elasticsearch", "OpenSearch", "Solr", "Algolia", "Meilisearch", "Typesense"],
  "timeseries": ["InfluxDB", "TimescaleDB", "Prometheus", "QuestDB", "ClickHouse", "Apache Druid"],
  "graph": ["Neo4j", "Amazon Neptune", "ArangoDB", "JanusGraph", "TigerGraph", "Dgraph"],
  "vector": ["Pinecone", "Milvus", "Weaviate", "Qdrant", "Chroma", "pgvector", "FAISS"],
  "warehouse": ["Snowflake", "BigQuery", "Redshift", "Databricks", "Azure Synapse", "Clickhouse", "Apache Hive", "Presto", "Trino", "Apache Spark", "dbt"]
}

CATEGORY: "cloud_platform"
{
  "major_providers": ["AWS", "Amazon Web Services", "GCP", "Google Cloud Platform", "Azure", "Microsoft Azure"],
  "alternative_cloud": ["DigitalOcean", "Linode", "Vultr", "OVH", "Hetzner", "Scaleway", "Oracle Cloud", "IBM Cloud", "Alibaba Cloud", "Tencent Cloud"],
  "serverless": ["AWS Lambda", "Google Cloud Functions", "Azure Functions", "Cloudflare Workers", "Vercel", "Netlify", "Railway", "Render", "Fly.io", "Deno Deploy"],
  "aws_services": ["EC2", "S3", "RDS", "DynamoDB", "Lambda", "ECS", "EKS", "Fargate", "SQS", "SNS", "Kinesis", "CloudFront", "Route53", "API Gateway", "CloudWatch", "IAM", "Cognito", "Amplify", "SageMaker", "Glue", "Athena", "Redshift", "EMR", "Step Functions", "EventBridge"],
  "gcp_services": ["Compute Engine", "Cloud Storage", "Cloud SQL", "Datastore", "Cloud Functions", "GKE", "Cloud Run", "Pub/Sub", "BigQuery", "Cloud Dataflow", "Cloud Dataproc", "Vertex AI", "Cloud Spanner", "Firestore"],
  "azure_services": ["Virtual Machines", "Blob Storage", "Azure SQL", "Cosmos DB", "Azure Functions", "AKS", "Service Bus", "Event Hubs", "Azure ML", "Synapse Analytics", "Data Factory"],
  "paas": ["Heroku", "Vercel", "Netlify", "Railway", "Render", "Platform.sh", "Fly.io", "Dokku", "Coolify"]
}

CATEGORY: "devops_infrastructure"
{
  "containers": ["Docker", "Podman", "containerd", "LXC", "Buildah", "Kaniko"],
  "orchestration": ["Kubernetes", "K8s", "Docker Swarm", "ECS", "EKS", "GKE", "AKS", "OpenShift", "Rancher", "Nomad"],
  "iac": ["Terraform", "CloudFormation", "Pulumi", "Ansible", "Chef", "Puppet", "SaltStack", "CDK", "Crossplane"],
  "ci_cd": ["GitHub Actions", "GitLab CI", "Jenkins", "CircleCI", "Travis CI", "Azure DevOps", "Bitbucket Pipelines", "Argo CD", "Flux", "Spinnaker", "TeamCity", "Bamboo", "Drone", "Tekton"],
  "monitoring_observability": ["Prometheus", "Grafana", "Datadog", "New Relic", "Splunk", "ELK Stack", "Elasticsearch", "Logstash", "Kibana", "Jaeger", "Zipkin", "OpenTelemetry", "Sentry", "PagerDuty", "VictorOps", "Honeycomb", "Lightstep"],
  "networking": ["Nginx", "Apache", "HAProxy", "Traefik", "Envoy", "Istio", "Linkerd", "Consul", "Kong", "AWS ALB/ELB", "Cloudflare"],
  "security": ["Vault", "AWS Secrets Manager", "Azure Key Vault", "SOPS", "cert-manager", "Let's Encrypt", "Trivy", "Snyk", "SonarQube", "OWASP ZAP", "Burp Suite"]
}

CATEGORY: "tools_platforms"
{
  "version_control": ["Git", "GitHub", "GitLab", "Bitbucket", "Azure Repos", "Perforce", "SVN", "Mercurial"],
  "ide_editors": ["VS Code", "IntelliJ IDEA", "PyCharm", "WebStorm", "Android Studio", "Xcode", "Eclipse", "Vim", "Neovim", "Emacs", "Sublime Text", "Cursor", "Zed"],
  "project_management": ["Jira", "Linear", "Asana", "Monday.com", "Trello", "Notion", "Confluence", "Shortcut (Clubhouse)", "ClickUp", "Azure Boards", "GitHub Projects"],
  "communication": ["Slack", "Microsoft Teams", "Discord", "Zoom", "Google Meet"],
  "design": ["Figma", "Sketch", "Adobe XD", "InVision", "Zeplin", "Framer", "Canva", "Adobe Creative Suite", "Photoshop", "Illustrator"],
  "documentation": ["Notion", "Confluence", "GitBook", "ReadTheDocs", "Docusaurus", "MkDocs", "Swagger", "Postman"],
  "api_testing": ["Postman", "Insomnia", "Hoppscotch", "curl", "HTTPie", "Bruno"],
  "data_tools": ["Jupyter", "JupyterLab", "Google Colab", "Databricks Notebooks", "Hex", "Observable", "Mode", "Looker", "Tableau", "Power BI", "Metabase", "Redash", "Apache Superset"]
}

CATEGORY: "methodology_practice"
{
  "development": ["Agile", "Scrum", "Kanban", "XP", "Waterfall", "SAFe", "Lean", "TDD", "BDD", "DDD", "Pair Programming", "Mob Programming", "Code Review"],
  "architecture": ["Microservices", "Monolith", "Serverless", "Event-Driven", "CQRS", "Event Sourcing", "Hexagonal Architecture", "Clean Architecture", "Domain-Driven Design", "SOA", "API-First", "REST", "GraphQL"],
  "data": ["ETL", "ELT", "Data Modeling", "Data Warehousing", "Data Lake", "Data Mesh", "Data Governance", "Data Quality", "Stream Processing", "Batch Processing"],
  "ml_ops": ["MLOps", "Model Deployment", "Feature Engineering", "Model Monitoring", "A/B Testing", "Experimentation", "Feature Stores", "Model Registry"],
  "security": ["DevSecOps", "OWASP", "Security Auditing", "Penetration Testing", "Vulnerability Assessment", "SOC2", "GDPR", "HIPAA", "PCI-DSS", "Zero Trust"]
}

CATEGORY: "domain_knowledge"
{
  "technical_domains": ["Distributed Systems", "System Design", "High Availability", "Scalability", "Performance Optimization", "Caching", "Load Balancing", "API Design", "Database Design", "Security", "Cryptography", "Networking", "Operating Systems", "Compilers", "Computer Graphics", "Game Development", "Embedded Systems", "IoT", "Blockchain", "Web3"],
  "ai_ml_domains": ["Machine Learning", "Deep Learning", "NLP", "Natural Language Processing", "Computer Vision", "Reinforcement Learning", "Recommendation Systems", "Time Series", "Anomaly Detection", "Generative AI", "LLMs", "Transformers", "Neural Networks", "Classification", "Regression", "Clustering"],
  "business_domains": ["Fintech", "Healthcare", "E-commerce", "SaaS", "AdTech", "MarTech", "EdTech", "PropTech", "InsurTech", "Cybersecurity", "Gaming", "Media", "Logistics", "Supply Chain", "Retail", "Banking", "Payments", "Trading", "Risk Management"]
}

CATEGORY: "soft_skill"
["Leadership", "Team Leadership", "People Management", "Mentoring", "Coaching", "Cross-functional Collaboration", "Stakeholder Management", "Executive Communication", "Technical Writing", "Documentation", "Public Speaking", "Presentation", "Project Management", "Program Management", "Product Thinking", "Strategic Planning", "Decision Making", "Conflict Resolution", "Negotiation", "Hiring", "Interviewing", "Performance Management", "OKRs", "Roadmapping"]

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 3.2 SKILL EXTRACTION INTELLIGENCE                                                                   │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

EXTRACTION SOURCES (Priority Order):
1. Dedicated Skills section - highest confidence
2. Job descriptions - extract from context ("Built microservices using Go" → Go)
3. Project descriptions - extract technologies used
4. Education - relevant coursework, thesis topics
5. Certifications - implied skills (AWS Certified → AWS)

PROFICIENCY INFERENCE RULES:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Signal                                  │ Inferred Proficiency                                     │
├─────────────────────────────────────────┼──────────────────────────────────────────────────────────┤
│ "Expert in X", "X expert"               │ expert                                                   │
│ "Advanced X", "Strong X"                │ advanced                                                 │
│ "Proficient in X"                       │ advanced                                                 │
│ "X (5+ years)", primary stack           │ advanced                                                 │
│ "Familiar with X", "Basic X"            │ beginner                                                 │
│ "Exposure to X", "Some X"               │ beginner                                                 │
│ "Learning X", "Currently studying X"    │ learning                                                 │
│ Listed without qualifier                │ null (do not assume)                                     │
│ Used in current/recent role (1-2 yrs)   │ intermediate (infer from context)                       │
│ Used extensively across multiple roles  │ advanced (infer from context)                           │
└─────────────────────────────────────────┴──────────────────────────────────────────────────────────┘

SKILL ALIASING (Normalize variants):
- "React.js", "ReactJS", "React" → "React"
- "Node", "NodeJS", "Node.js" → "Node.js"
- "K8s", "kube", "kubernetes" → "Kubernetes"
- "Postgres", "PostgresSQL", "psql" → "PostgreSQL"
- "ES", "ElasticSearch" → "Elasticsearch"
- "TF", "tf" → "Terraform" or "TensorFlow" (disambiguate from context)
- "AWS" should remain "AWS", but also extract specific services used

SKILL RELATIONSHIP MAPPING:
{
  "implies": {
    "React": ["JavaScript", "HTML", "CSS"],
    "Next.js": ["React", "JavaScript"],
    "Django": ["Python"],
    "Spring Boot": ["Java"],
    "Rails": ["Ruby"],
    "Flutter": ["Dart"],
    "SwiftUI": ["Swift"],
    "Kubernetes": ["Docker", "Containers"],
    "Terraform": ["Infrastructure as Code"]
  }
}
NOTE: Do NOT auto-add implied skills unless explicitly mentioned - just note the relationship exists.

══════════════════════════════════════════════════════════════════════════════════════════════════════
MODULE 4: PROJECT, CERTIFICATION & ADDITIONAL EXTRACTION
══════════════════════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4.1 PROJECT EXTRACTION                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

CLASSIFICATION:
- type: "personal" | "professional" | "academic" | "open_source" | "hackathon" | "freelance"
- is_notable: true if has significant metrics, stars, users, or recognition

METRICS TO EXTRACT:
- GitHub stars, forks, contributors
- Users/downloads/installs
- Revenue generated
- Performance metrics
- Awards/recognition received

URL VALIDATION:
- GitHub: github.com/[user]/[repo]
- GitLab: gitlab.com/[user]/[repo]
- Live demo: Validate domain format
- App stores: Play Store, App Store links
- npm/PyPI packages

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4.2 CERTIFICATION RECOGNITION                                                                       │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

KNOWN CERTIFICATIONS DATABASE:
{
  "aws": [
    {"name": "AWS Certified Solutions Architect - Associate", "code": "SAA-C03", "level": "associate"},
    {"name": "AWS Certified Solutions Architect - Professional", "code": "SAP-C02", "level": "professional"},
    {"name": "AWS Certified Developer - Associate", "code": "DVA-C02", "level": "associate"},
    {"name": "AWS Certified SysOps Administrator - Associate", "code": "SOA-C02", "level": "associate"},
    {"name": "AWS Certified DevOps Engineer - Professional", "code": "DOP-C02", "level": "professional"},
    {"name": "AWS Certified Machine Learning - Specialty", "code": "MLS-C01", "level": "specialty"},
    {"name": "AWS Certified Data Engineer - Associate", "code": "DEA-C01", "level": "associate"},
    {"name": "AWS Certified Cloud Practitioner", "code": "CLF-C02", "level": "foundational"}
  ],
  "gcp": [
    {"name": "Google Cloud Professional Cloud Architect", "level": "professional"},
    {"name": "Google Cloud Professional Data Engineer", "level": "professional"},
    {"name": "Google Cloud Professional Machine Learning Engineer", "level": "professional"},
    {"name": "Google Cloud Associate Cloud Engineer", "level": "associate"}
  ],
  "azure": [
    {"name": "Azure Solutions Architect Expert", "code": "AZ-305", "level": "expert"},
    {"name": "Azure Developer Associate", "code": "AZ-204", "level": "associate"},
    {"name": "Azure Administrator Associate", "code": "AZ-104", "level": "associate"},
    {"name": "Azure DevOps Engineer Expert", "code": "AZ-400", "level": "expert"},
    {"name": "Azure Data Engineer Associate", "code": "DP-203", "level": "associate"},
    {"name": "Azure AI Engineer Associate", "code": "AI-102", "level": "associate"}
  ],
  "kubernetes": [
    {"name": "Certified Kubernetes Administrator", "code": "CKA", "issuer": "CNCF"},
    {"name": "Certified Kubernetes Application Developer", "code": "CKAD", "issuer": "CNCF"},
    {"name": "Certified Kubernetes Security Specialist", "code": "CKS", "issuer": "CNCF"}
  ],
  "security": [
    {"name": "CISSP", "issuer": "ISC2"},
    {"name": "CISM", "issuer": "ISACA"},
    {"name": "CEH", "issuer": "EC-Council"},
    {"name": "CompTIA Security+", "issuer": "CompTIA"},
    {"name": "OSCP", "issuer": "Offensive Security"}
  ],
  "data": [
    {"name": "Databricks Certified Data Engineer", "issuer": "Databricks"},
    {"name": "Snowflake SnowPro Core", "issuer": "Snowflake"},
    {"name": "dbt Analytics Engineering Certification", "issuer": "dbt Labs"}
  ],
  "agile": [
    {"name": "Certified Scrum Master", "code": "CSM", "issuer": "Scrum Alliance"},
    {"name": "Professional Scrum Master", "code": "PSM", "issuer": "Scrum.org"},
    {"name": "PMI Agile Certified Practitioner", "code": "PMI-ACP", "issuer": "PMI"},
    {"name": "SAFe Agilist", "issuer": "Scaled Agile"}
  ]
}

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 4.3 LANGUAGE PROFICIENCY STANDARDIZATION                                                            │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

MAP TO CEFR + Common Terms:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Input Terms                                  │ Output                                               │
├──────────────────────────────────────────────┼──────────────────────────────────────────────────────┤
│ Native, Mother tongue, First language        │ proficiency: "native", cefr: null                   │
│ Bilingual                                    │ proficiency: "bilingual", cefr: null                │
│ Fluent, Full professional proficiency        │ proficiency: "fluent", cefr: "C2"                   │
│ Advanced, Professional working proficiency   │ proficiency: "advanced", cefr: "C1"                 │
│ Upper intermediate                           │ proficiency: "upper_intermediate", cefr: "B2"       │
│ Intermediate, Limited working proficiency    │ proficiency: "intermediate", cefr: "B1"             │
│ Elementary, Basic                            │ proficiency: "basic", cefr: "A2"                    │
│ Beginner                                     │ proficiency: "beginner", cefr: "A1"                 │
│ A1, A2, B1, B2, C1, C2                       │ Map directly to cefr, infer proficiency             │
│ TOEFL/IELTS/JLPT scores                      │ Include in score field, map to cefr                 │
└──────────────────────────────────────────────┴──────────────────────────────────────────────────────┘

══════════════════════════════════════════════════════════════════════════════════════════════════════
MODULE 5: QUALITY ASSURANCE & VALIDATION
══════════════════════════════════════════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 5.1 DATA QUALITY RULES                                                                              │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

VALIDATION RULES (flag violations):
1. Email format: Must contain @ and valid TLD
2. Phone: Must have 7-15 digits
3. URLs: Must have valid domain pattern
4. Dates: Cannot be in future (except education end dates), cannot be before 1950
5. Years of experience: Must match career span (flag if mismatch > 2 years)
6. Education dates: End year should be >= start year
7. Work dates: Should be roughly chronological (flag significant overlaps)
8. GPA: Should be within valid range for scale
9. Skills: Should appear in taxonomy or be flagged as unrecognized

COMPLETENESS SCORING:
┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Field                    │ Weight │ Notes                                                          │
├──────────────────────────┼────────┼────────────────────────────────────────────────────────────────┤
│ Name                     │ 10     │ Required                                                       │
│ Email                    │ 10     │ Required for contact                                           │
│ Phone                    │ 5      │ Important                                                      │
│ Location                 │ 5      │ Important for matching                                         │
│ Work Experience          │ 25     │ Critical - at least 1 entry with dates                       │
│ Education                │ 15     │ Important - at least 1 entry                                  │
│ Skills                   │ 15     │ Important - at least 3 skills                                 │
│ Professional Summary     │ 5      │ Nice to have                                                   │
│ LinkedIn                 │ 5      │ Verification                                                   │
│ Projects/Certifications  │ 5      │ Additional signal                                              │
└──────────────────────────┴────────┴────────────────────────────────────────────────────────────────┘

CONFIDENCE SCORING:
- HIGH (90-100%): All major sections found, clean OCR, dates parseable, skills recognizable
- MEDIUM (70-89%): Most sections found, some OCR issues fixed, some ambiguities
- LOW (50-69%): Missing sections, significant OCR issues, many ambiguities
- VERY LOW (<50%): Major parsing issues, recommend manual review

┌─────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ 5.2 ATS COMPATIBILITY FLAGS                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────────────────┘

FLAG ISSUES THAT AFFECT ATS PARSING:
- Missing contact information
- Non-standard section headers
- Tables/columns (may parse incorrectly)
- Graphics/images with text
- Headers/footers with critical info
- Non-standard date formats
- Abbreviations that may not be recognized
- Missing job titles or company names
- Gaps > 6 months without explanation

══════════════════════════════════════════════════════════════════════════════════════════════════════
MODULE 6: OUTPUT SCHEMA (JSON)
══════════════════════════════════════════════════════════════════════════════════════════════════════

{
  "meta": {
    "parser_version": "3.0",
    "parse_timestamp": "ISO 8601 timestamp",
    "source_format": "pdf | docx | txt | image | html",
    "detected_language": "ISO 639-1 code",
    "detected_locale": "region code if determinable"
  },
  
  "confidence": {
    "overall_score": "0-100 integer",
    "confidence_level": "high | medium | low | very_low",
    "completeness_score": "0-100 integer",
    "sections_found": ["list of detected sections"],
    "sections_missing": ["list of expected but not found sections"],
    "parsing_issues": [
      {
        "type": "ocr_error | missing_data | ambiguous | validation_failed",
        "field": "affected field path",
        "message": "description of issue",
        "severity": "info | warning | error"
      }
    ],
    "ats_compatibility": {
      "score": "0-100",
      "issues": ["list of ATS compatibility concerns"]
    }
  },
  
  "personal_info": {
    "full_name": "string | null",
    "first_name": "string | null",
    "middle_name": "string | null",
    "last_name": "string | null",
    "preferred_name": "string | null (nickname if different)",
    "pronouns": "string | null (if stated)",
    "email": {
      "primary": "string | null",
      "secondary": "string | null"
    },
    "phone": {
      "primary": {
        "raw": "original format",
        "normalized": "E.164 format",
        "type": "mobile | landline | work | null"
      },
      "secondary": "same structure | null"
    },
    "location": {
      "raw": "original text",
      "city": "string | null",
      "state_province": "string | null",
      "country": "string | null",
      "postal_code": "string | null",
      "is_remote": "boolean - true if 'Remote' mentioned",
      "willing_to_relocate": "boolean | null"
    },
    "links": {
      "linkedin": {
        "url": "full URL | null",
        "handle": "username | null"
      },
      "github": {
        "url": "full URL | null",
        "username": "string | null"
      },
      "portfolio": "string | null",
      "twitter": "string | null",
      "other": [{"platform": "string", "url": "string"}]
    },
    "demographics": {
      "nationality": "string | null (if stated)",
      "visa_status": "string | null (if stated)",
      "work_authorization": "string | null",
      "date_of_birth": "YYYY-MM-DD | null (if stated)",
      "driving_license": "string | null (if stated)"
    }
  },
  
  "professional_summary": {
    "original": "string | null - exact text from resume if summary section exists",
    "generated": "string - AI-generated following the template rules above",
    "keywords": ["extracted keywords relevant for search/matching"]
  },
  
  "career_metrics": {
    "years_of_experience": {
      "stated": "number | null - ONLY if explicitly stated in resume",
      "calculated": "number | null - calculated from work history",
      "calculation_note": "string explaining calculation if applicable"
    },
    "current_role": "string | null",
    "current_company": "string | null",
    "seniority_level": "intern | entry | junior | mid | senior | staff | principal | director | vp | c_level | null",
    "career_track": "ic | management | hybrid | null",
    "employment_status": "employed | unemployed | student | freelance | null",
    "notice_period": "string | null (if stated)",
    "expected_salary": {
      "raw": "string | null",
      "min": "number | null",
      "max": "number | null",
      "currency": "string | null",
      "period": "hourly | daily | monthly | annual | null"
    }
  },
  
  "work_experience": [
    {
      "company": {
        "name": "string - exact as written",
        "normalized_name": "string | null - standardized name",
        "type": "startup | scaleup | enterprise | agency | consulting | nonprofit | government | null",
        "industry": "string | null",
        "size": "string | null (if mentioned)",
        "url": "string | null"
      },
      "role": {
        "title": "string - exact as written",
        "normalized_title": "string | null - standardized title",
        "seniority": "intern | entry | junior | mid | senior | staff | principal | director | vp | c_level | null",
        "function": "engineering | product | design | data | devops | qa | security | management | other"
      },
      "location": {
        "raw": "string | null",
        "city": "string | null",
        "country": "string | null",
        "is_remote": "boolean"
      },
      "dates": {
        "start": {
          "raw": "string - original text",
          "parsed": "YYYY-MM | YYYY | null"
        },
        "end": {
          "raw": "string | null",
          "parsed": "YYYY-MM | YYYY | null"
        },
        "is_current": "boolean",
        "duration_months": "number | null"
      },
      "employment_type": "full_time | part_time | contract | freelance | internship | apprenticeship | null",
      "description": {
        "raw": "string - exact bullet points, separated by ' • '",
        "bullet_points": ["array of individual bullets"],
        "achievements_with_metrics": [
          {
            "text": "achievement text",
            "metrics": [
              {
                "type": "revenue | cost_savings | users | performance | team_size | time | percentage | scale",
                "value": "string",
                "context": "string"
              }
            ]
          }
        ]
      },
      "technologies_used": ["extracted from description"],
      "team_size": "number | null (if mentioned)",
      "reports_to": "string | null (if mentioned)",
      "direct_reports": "number | null (if mentioned)"
    }
  ],
  
  "education": [
    {
      "institution": {
        "name": "string - full name",
        "normalized_name": "string | null",
        "type": "university | college | bootcamp | high_school | online | other",
        "location": {
          "city": "string | null",
          "country": "string | null"
        },
        "is_notable": "boolean - true if top-tier"
      },
      "degree": {
        "raw": "string - exact as written",
        "normalized": "Bachelor's | Master's | PhD | MBA | Associate's | Certificate | Diploma | High School | null",
        "level": "high_school | associates | bachelors | masters | doctorate | professional | certificate | null"
      },
      "field_of_study": {
        "raw": "string | null",
        "normalized": "string | null",
        "is_stem": "boolean | null"
      },
      "dates": {
        "start_year": "number | null",
        "end_year": "number | null",
        "is_current": "boolean"
      },
      "gpa": {
        "raw": "string | null - exact as written",
        "value": "number | null",
        "scale": "string | null (e.g., '4.0', '10', '100%')",
        "normalized_4_0": "number | null - converted to 4.0 scale"
      },
      "honors": ["Dean's List", "Summa Cum Laude", etc.],
      "relevant_coursework": ["if listed"],
      "thesis_title": "string | null",
      "activities": ["extracurriculars, clubs, sports if listed"]
    }
  ],
  
  "skills": {
    "all": [
      {
        "name": "string - exact as written",
        "normalized_name": "string - standardized",
        "category": "programming_language | framework_library | database | cloud_platform | devops_infrastructure | tools_platforms | methodology_practice | domain_knowledge | soft_skill | other",
        "subcategory": "string | null - from taxonomy",
        "proficiency": {
          "stated": "expert | advanced | intermediate | beginner | learning | null",
          "inferred": "expert | advanced | intermediate | beginner | null",
          "inference_reason": "string | null"
        },
        "years_used": "number | null (if explicitly stated)",
        "last_used": "YYYY | null (if determinable from experience)",
        "context": "work | project | education | certification - where skill was mentioned"
      }
    ],
    "by_category": {
      "programming_language": ["names"],
      "framework_library": ["names"],
      "database": ["names"],
      "cloud_platform": ["names"],
      "devops_infrastructure": ["names"],
      "tools_platforms": ["names"],
      "methodology_practice": ["names"],
      "domain_knowledge": ["names"],
      "soft_skill": ["names"]
    },
    "primary_stack": ["top 5-7 most prominent technologies"],
    "unrecognized": ["skills not in taxonomy - may need review"]
  },
  
  "projects": [
    {
      "name": "string",
      "type": "personal | professional | academic | open_source | hackathon | freelance",
      "description": {
        "raw": "string - exact text, max 300 chars",
        "summary": "string - 1 sentence"
      },
      "technologies": ["list"],
      "role": "string | null - Solo, Lead, Contributor, etc.",
      "team_size": "number | null",
      "dates": {
        "start_year": "number | null",
        "end_year": "number | null"
      },
      "urls": {
        "repo": "string | null",
        "demo": "string | null",
        "documentation": "string | null"
      },
      "metrics": {
        "github_stars": "number | null",
        "users": "string | null",
        "downloads": "string | null",
        "other": "string | null"
      },
      "is_notable": "boolean"
    }
  ],
  
  "certifications": [
    {
      "name": {
        "raw": "string",
        "normalized": "string | null - from known database"
      },
      "issuer": "string | null",
      "code": "string | null (e.g., AWS SAA-C03)",
      "level": "foundational | associate | professional | specialty | expert | null",
      "date_obtained": {
        "raw": "string | null",
        "parsed": "YYYY-MM | YYYY | null"
      },
      "expiration_date": "YYYY-MM | null",
      "is_expired": "boolean | null",
      "credential_id": "string | null",
      "verification_url": "string | null",
      "skills_implied": ["list of skills this cert implies"]
    }
  ],
  
  "publications": [
    {
      "title": "string",
      "type": "journal_article | conference_paper | book | book_chapter | patent | blog_post | whitepaper | thesis | other",
      "publication_venue": "string | null - journal/conference name",
      "date": {
        "raw": "string | null",
        "year": "number | null"
      },
      "url": "string | null - DOI or direct link",
      "authors": {
        "raw": "string | null",
        "list": ["array of names"],
        "position": "first | last | middle | null - candidate's position"
      },
      "citations": "number | null (if mentioned)"
    }
  ],
  
  "awards": [
    {
      "title": "string",
      "issuer": "string | null",
      "date": {
        "raw": "string | null",
        "year": "number | null"
      },
      "description": "string | null",
      "is_notable": "boolean - true if from major organization"
    }
  ],
  
  "languages": [
    {
      "language": "string",
      "proficiency": {
        "raw": "string | null",
        "normalized": "native | bilingual | fluent | advanced | upper_intermediate | intermediate | basic | beginner | null",
        "cefr": "A1 | A2 | B1 | B2 | C1 | C2 | null"
      },
      "certifications": ["TOEFL", "IELTS", etc. if mentioned],
      "test_scores": {"test": "score"} | null
    }
  ],
  
  "coding_profiles": {
    "github": {
      "url": "string | null",
      "username": "string | null"
    },
    "leetcode": {"url": "string | null", "username": "string | null"},
    "hackerrank": {"url": "string | null", "username": "string | null"},
    "codeforces": {"url": "string | null", "username": "string | null"},
    "codechef": {"url": "string | null", "username": "string | null"},
    "kaggle": {"url": "string | null", "username": "string | null"},
    "stackoverflow": {"url": "string | null", "user_id": "string | null"},
    "toptal": {"url": "string | null"},
    "upwork": {"url": "string | null"},
    "other": [{"platform": "string", "url": "string"}]
  },
  
  "volunteer_experience": [
    {
      "organization": "string",
      "role": "string",
      "dates": {
        "start": "string | null",
        "end": "string | null"
      },
      "description": "string | null"
    }
  ],
  
  "interests": ["hobbies and interests if listed"],
  
  "references": {
    "available_upon_request": "boolean",
    "listed": [
      {
        "name": "string | null",
        "title": "string | null",
        "company": "string | null",
        "relationship": "string | null",
        "contact": "string | null - email or phone"
      }
    ]
  },
  
  "additional_sections": [
    {
      "header": "string - section name",
      "content": "string - raw content"
    }
  ],
  
  "search_index": {
    "full_text": "string - concatenated searchable text",
    "keywords": ["extracted keywords for search"],
    "job_titles_normalized": ["all normalized job titles"],
    "companies_normalized": ["all normalized company names"],
    "skills_normalized": ["all normalized skills"],
    "locations": ["all locations mentioned"]
  }
}

══════════════════════════════════════════════════════════════════════════════════════════════════════
FINAL INSTRUCTIONS
══════════════════════════════════════════════════════════════════════════════════════════════════════

1. OUTPUT ONLY VALID JSON - No markdown, no explanations, no code blocks
2. USE null FOR MISSING DATA - Never fabricate or assume
3. PRESERVE ORIGINAL TEXT - Fix only clear OCR errors
4. DO NOT CALCULATE years_of_experience.stated - Only use if explicitly written
5. GENERATE HIGH-QUALITY SUMMARY - Follow templates, avoid banned phrases
6. CATEGORIZE ALL SKILLS - Use taxonomy, flag unknown
7. NORMALIZE COMPANY/SCHOOL NAMES - Use known databases
8. EXTRACT ALL METRICS - Numbers are gold for matching
9. FLAG QUALITY ISSUES - Help downstream systems
10. MAINTAIN INTERNATIONAL SUPPORT - Handle all locales and languages

NOW PARSE THE FOLLOWING RESUME:
"""


# ============================================================================
# Core Functions
# ============================================================================

def pdf_to_images(pdf_bytes: bytes, dpi: int = 150) -> List[bytes]:
    """
    Convert PDF to list of PNG images using PyMuPDF (no poppler dependency).
    
    Args:
        pdf_bytes: Raw PDF file bytes
        dpi: Resolution for conversion (default 150 for good quality without huge size)
    
    Returns:
        List of PNG image bytes, one per page
    """
    images = []
    pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")
    
    # Scale factor for DPI (default PDF is 72 DPI)
    zoom = dpi / 72.0
    matrix = fitz.Matrix(zoom, zoom)
    
    for page_num in range(len(pdf_document)):
        page = pdf_document[page_num]
        pix = page.get_pixmap(matrix=matrix)
        img_bytes = pix.tobytes("png")
        images.append(img_bytes)
    
    pdf_document.close()
    return images


def _safe_get(obj, *keys, default=None):
    """Safely traverse nested dict/object."""
    for key in keys:
        if isinstance(obj, dict):
            obj = obj.get(key)
        else:
            return default
        if obj is None:
            return default
    return obj if obj is not None else default


def normalize_gemini_output(data: dict) -> dict:
    """
    Transform complex Gemini output to match simple Pydantic schemas.
    Handles the schema mismatch between elaborate prompt and existing models.
    """
    result = {}
    
    # Normalize personal_info
    pi = data.get("personal_info", {})
    result["personal_info"] = {
        "name": _safe_get(pi, "full_name") or _safe_get(pi, "name"),
        "email": _safe_get(pi, "email", "primary") or (pi.get("email") if isinstance(pi.get("email"), str) else None),
        "phone": _safe_get(pi, "phone", "primary", "raw") or _safe_get(pi, "phone", "raw") or (pi.get("phone") if isinstance(pi.get("phone"), str) else None),
        "linkedin_url": _safe_get(pi, "links", "linkedin", "url") or _safe_get(pi, "linkedin_url"),
        "github_url": _safe_get(pi, "links", "github", "url") or _safe_get(pi, "github_url"),
        "portfolio_url": _safe_get(pi, "links", "portfolio") or _safe_get(pi, "portfolio_url"),
        "location": _safe_get(pi, "location", "raw") or (pi.get("location") if isinstance(pi.get("location"), str) else None),
    }
    
    # Normalize professional_summary
    ps = data.get("professional_summary", "")
    if isinstance(ps, dict):
        result["professional_summary"] = _safe_get(ps, "generated") or _safe_get(ps, "original") or ""
    else:
        result["professional_summary"] = ps
    
    # Normalize years_of_experience - ONLY use if explicitly stated in resume
    # Never use calculated values to prevent wrong experience being shown
    yoe = data.get("years_of_experience") or data.get("career_metrics", {}).get("years_of_experience", {})
    if isinstance(yoe, dict):
        # Only use 'stated' experience, never 'calculated'
        result["years_of_experience"] = _safe_get(yoe, "stated")
    elif isinstance(yoe, (int, float)) and yoe > 0:
        # If it's a direct number, only use if it seems explicitly stated (whole numbers or .5)
        # Calculated values are often odd decimals like 0.33
        if yoe == int(yoe) or (yoe * 2) == int(yoe * 2):  # whole or .5
            result["years_of_experience"] = yoe
        else:
            result["years_of_experience"] = None  # Likely calculated, ignore
    else:
        result["years_of_experience"] = None
    
    # Get current role/company
    cm = data.get("career_metrics", {})
    result["current_role"] = cm.get("current_role") or data.get("current_role")
    result["current_company"] = cm.get("current_company") or data.get("current_company")
    
    # Normalize education
    education_list = []
    for edu in data.get("education", []):
        normalized_edu = {
            "school": _safe_get(edu, "institution", "name") or edu.get("school", "Unknown"),
            "degree": _safe_get(edu, "degree", "raw") or _safe_get(edu, "degree", "normalized") or (edu.get("degree") if isinstance(edu.get("degree"), str) else None),
            "field_of_study": _safe_get(edu, "field_of_study", "raw") or (edu.get("field_of_study") if isinstance(edu.get("field_of_study"), str) else None),
            "start_year": _safe_get(edu, "dates", "start_year") or edu.get("start_year"),
            "end_year": _safe_get(edu, "dates", "end_year") or edu.get("end_year"),
            "gpa": _safe_get(edu, "gpa", "raw") or (edu.get("gpa") if isinstance(edu.get("gpa"), str) else None),
        }
        education_list.append(normalized_edu)
    result["education"] = education_list
    
    # Normalize work_experience
    work_list = []
    for exp in data.get("work_experience", []):
        normalized_exp = {
            "company": _safe_get(exp, "company", "name") or (exp.get("company") if isinstance(exp.get("company"), str) else "Unknown"),
            "role": _safe_get(exp, "role", "title") or (exp.get("role") if isinstance(exp.get("role"), str) else "Unknown"),
            "city": _safe_get(exp, "location", "city") or exp.get("city"),
            "country": _safe_get(exp, "location", "country") or exp.get("country"),
            "start_date": _safe_get(exp, "dates", "start", "parsed") or exp.get("start_date"),
            "end_date": _safe_get(exp, "dates", "end", "parsed") or exp.get("end_date"),
            "is_current": _safe_get(exp, "dates", "is_current") or exp.get("is_current", False),
            "description": _safe_get(exp, "description", "raw") or (exp.get("description") if isinstance(exp.get("description"), str) else None),
        }
        work_list.append(normalized_exp)
    result["work_experience"] = work_list
    
    # Normalize projects
    project_list = []
    for proj in data.get("projects", []):
        normalized_proj = {
            "name": proj.get("name", "Unknown"),
            "description": _safe_get(proj, "description", "raw") or _safe_get(proj, "description", "summary") or (proj.get("description") if isinstance(proj.get("description"), str) else None),
            "technologies": proj.get("technologies", []),
            "start_year": _safe_get(proj, "dates", "start_year") or proj.get("start_year"),
            "end_year": _safe_get(proj, "dates", "end_year") or proj.get("end_year"),
            "url": _safe_get(proj, "urls", "repo") or _safe_get(proj, "urls", "demo") or proj.get("url"),
        }
        project_list.append(normalized_proj)
    result["projects"] = project_list
    
    # Normalize skills
    skills_data = data.get("skills", [])
    skill_list = []
    
    if isinstance(skills_data, dict):
        # Complex format with "all" key
        raw_skills = skills_data.get("all", [])
    else:
        raw_skills = skills_data
    
    for skill in raw_skills:
        if isinstance(skill, dict):
            prof = skill.get("proficiency", {})
            normalized_skill = {
                "name": skill.get("normalized_name") or skill.get("name", ""),
                "category": skill.get("category"),
                "proficiency": (prof.get("stated") or prof.get("inferred") if isinstance(prof, dict) else prof),
            }
            skill_list.append(normalized_skill)
        elif isinstance(skill, str):
            skill_list.append({"name": skill, "category": None, "proficiency": None})
    result["skills"] = skill_list
    
    # Normalize certifications
    cert_list = []
    for cert in data.get("certifications", []):
        normalized_cert = {
            "title": _safe_get(cert, "name", "raw") or _safe_get(cert, "name", "normalized") or cert.get("title", "Unknown"),
            "issuer": cert.get("issuer"),
            "year": _safe_get(cert, "date_obtained", "parsed")[:4] if _safe_get(cert, "date_obtained", "parsed") else cert.get("year"),
            "url": cert.get("verification_url") or cert.get("url"),
        }
        if isinstance(normalized_cert["year"], str):
            try:
                normalized_cert["year"] = int(normalized_cert["year"][:4])
            except:
                normalized_cert["year"] = None
        cert_list.append(normalized_cert)
    result["certifications"] = cert_list
    
    # Normalize publications
    pub_list = []
    for pub in data.get("publications", []):
        normalized_pub = {
            "title": pub.get("title", "Unknown"),
            "publisher": pub.get("publication_venue") or pub.get("publisher"),
            "year": _safe_get(pub, "date", "year") or pub.get("year"),
            "url": pub.get("url"),
        }
        pub_list.append(normalized_pub)
    result["publications"] = pub_list
    
    # Normalize awards
    award_list = []
    for award in data.get("awards", []):
        normalized_award = {
            "title": award.get("title", "Unknown"),
            "issuer": award.get("issuer"),
            "year": _safe_get(award, "date", "year") or award.get("year"),
        }
        award_list.append(normalized_award)
    result["awards"] = award_list
    
    # Normalize languages
    lang_list = []
    for lang in data.get("languages", []):
        normalized_lang = {
            "language": lang.get("language", "Unknown"),
            "proficiency": _safe_get(lang, "proficiency", "normalized") or (lang.get("proficiency") if isinstance(lang.get("proficiency"), str) else None),
        }
        lang_list.append(normalized_lang)
    result["languages"] = lang_list
    
    # Normalize coding_profiles
    cp = data.get("coding_profiles", {})
    result["coding_profiles"] = {
        "leetcode": _safe_get(cp, "leetcode", "username") or (cp.get("leetcode") if isinstance(cp.get("leetcode"), str) else None),
        "github": _safe_get(cp, "github", "username") or (cp.get("github") if isinstance(cp.get("github"), str) else None),
        "codechef": _safe_get(cp, "codechef", "username") or (cp.get("codechef") if isinstance(cp.get("codechef"), str) else None),
        "codeforces": _safe_get(cp, "codeforces", "username") or (cp.get("codeforces") if isinstance(cp.get("codeforces"), str) else None),
    }
    
    return result


async def parse_resume_with_gemini(pdf_bytes: bytes) -> ParsedResume:
    """
    Parse resume PDF using Gemini vision model.
    
    Args:
        pdf_bytes: Raw PDF file bytes
    
    Returns:
        ParsedResume object with all extracted data
    """
    # Convert PDF to images
    images = pdf_to_images(pdf_bytes)
    
    if not images:
        raise ValueError("Could not extract any pages from PDF")
    
    # Prepare content parts for Gemini
    client = get_genai_client()
    if not client:
        raise ValueError("Gemini API not configured. Please set GEMINI_API_KEY.")
    
    from google import genai
    contents = [RESUME_PARSER_PROMPT]
    
    for img_bytes in images:
        # Add image as Part
        contents.append(
            genai.types.Part.from_bytes(
                data=img_bytes,
                mime_type="image/png"
            )
        )
    
    # Generate response using new SDK
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=contents,
        config=genai.types.GenerateContentConfig(
            temperature=0.1,
            max_output_tokens=32768,
        )
    )
    
    # Extract and parse JSON
    response_text = response.text.strip()
    
    # Clean up response if it has markdown code blocks
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    response_text = response_text.strip()
    
    try:
        parsed_data = json.loads(response_text)
        # Normalize the complex Gemini output to match our simple Pydantic schemas
        normalized_data = normalize_gemini_output(parsed_data)
        return ParsedResume(**normalized_data)
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON response: {e}")
        print(f"Raw response: {response_text[:500]}...")
        # Return empty parsed resume on failure
        return ParsedResume()
    except Exception as e:
        print(f"Failed to parse resume: {e}")
        # Return empty parsed resume on failure
        return ParsedResume()


def normalize_skill_name(skill_name: str) -> str:
    """Normalize skill name for consistent storage and matching."""
    # Common aliases mapping
    aliases = {
        "js": "javascript",
        "ts": "typescript",
        "py": "python",
        "cpp": "c++",
        "c#": "csharp",
        "node": "nodejs",
        "node.js": "nodejs",
        "react.js": "react",
        "vue.js": "vue",
        "angular.js": "angular",
        "mongo": "mongodb",
        "postgres": "postgresql",
        "k8s": "kubernetes",
        "tf": "terraform",
        "aws lambda": "aws",
        "gcp": "google cloud",
        "ml": "machine learning",
        "ai": "artificial intelligence",
        "dl": "deep learning",
    }
    
    normalized = skill_name.lower().strip()
    return aliases.get(normalized, normalized)


def deduplicate_skills(skills: List[SkillEntry]) -> List[SkillEntry]:
    """Remove duplicate skills, keeping the one with highest proficiency."""
    proficiency_order = {"expert": 3, "intermediate": 2, "beginner": 1, None: 0}
    
    skill_map = {}
    for skill in skills:
        normalized = normalize_skill_name(skill.name)
        current = skill_map.get(normalized)
        
        if current is None:
            skill_map[normalized] = skill
        else:
            # Keep the one with higher proficiency
            if proficiency_order.get(skill.proficiency, 0) > proficiency_order.get(current.proficiency, 0):
                skill_map[normalized] = skill
    
    return list(skill_map.values())
