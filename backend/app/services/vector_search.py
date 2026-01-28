"""
Vector Search Service using Pinecone for semantic candidate matching.
Stores profile embeddings and enables intelligent HR search.
"""
import json
from typing import List, Optional, Dict, Any
from pinecone import Pinecone, ServerlessSpec

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
                print("WARNING: GEMINI_API_KEY not set - embeddings disabled")
                return None
        except ImportError:
            print("WARNING: google-genai package not installed - embeddings disabled")
            return None
        except Exception as e:
            print(f"WARNING: Failed to initialize Gemini client: {e}")
            return None
    return _genai_client


class VectorSearchService:
    """
    Handles vector storage and semantic search for candidate profiles.
    Uses Gemini for embeddings and Pinecone for vector storage.
    """
    
    def __init__(self):
        self.pc = None
        self.index = None
        self._initialized = False
    
    async def initialize(self):
        """Initialize Pinecone connection (lazy initialization)."""
        if self._initialized:
            return
        
        if not settings.pinecone_api_key:
            print("Warning: Pinecone API key not configured. Vector search will be disabled.")
            return
        
        try:
            self.pc = Pinecone(api_key=settings.pinecone_api_key)
            
            # Check if index exists, create if not
            existing_indexes = [idx.name for idx in self.pc.list_indexes()]
            
            if settings.pinecone_index_name not in existing_indexes:
                print(f"Creating Pinecone index: {settings.pinecone_index_name}")
                self.pc.create_index(
                    name=settings.pinecone_index_name,
                    dimension=768,  # Gemini embedding dimension
                    metric="cosine",
                    spec=ServerlessSpec(
                        cloud="aws",
                        region=settings.pinecone_environment
                    )
                )
            
            self.index = self.pc.Index(settings.pinecone_index_name)
            self._initialized = True
            print(f"✅ Pinecone initialized: {settings.pinecone_index_name}")
            
        except Exception as e:
            print(f"Failed to initialize Pinecone: {e}")
            self._initialized = False
    
    async def get_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for text using Gemini.
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing the embedding vector
        """
        client = get_genai_client()
        if not client:
            return [0.0] * 768  # Return zero vector if client unavailable
        result = client.models.embed_content(
            model="embedding-001",
            contents=text,
        )
        return result.embeddings[0].values
    
    async def get_query_embedding(self, text: str) -> List[float]:
        """
        Generate embedding for search query using Gemini.
        """
        client = get_genai_client()
        if not client:
            return [0.0] * 768  # Return zero vector if client unavailable
        result = client.models.embed_content(
            model="embedding-001",
            contents=text,
        )
        return result.embeddings[0].values
    
    async def index_profile(
        self,
        profile_id: int,
        summary: str,
        skills: List[str],
        years_exp: Optional[float] = None,
        current_role: Optional[str] = None,
        current_company: Optional[str] = None
    ) -> Optional[str]:
        """
        Index a candidate profile for semantic search.
        
        Args:
            profile_id: Database profile ID
            summary: Professional summary text
            skills: List of skill names for filtering
            years_exp: Years of experience
            current_role: Current job title
            current_company: Current employer
            
        Returns:
            Vector ID if successful, None otherwise
        """
        await self.initialize()
        
        if not self.index:
            print("Pinecone not available, skipping indexing")
            return None
        
        try:
            # Generate embedding from summary
            embedding = await self.get_embedding(summary)
            
            # Prepare metadata for filtering
            metadata = {
                "skills": [s.lower() for s in skills],  # Normalize for filtering
                "years_exp": years_exp or 0,
                "current_role": current_role or "",
                "current_company": current_company or ""
            }
            
            vector_id = f"profile_{profile_id}"
            
            # Upsert to Pinecone
            self.index.upsert(
                vectors=[{
                    "id": vector_id,
                    "values": embedding,
                    "metadata": metadata
                }]
            )
            
            print(f"✅ Indexed profile {profile_id} with {len(skills)} skills")
            return vector_id
            
        except Exception as e:
            print(f"Failed to index profile: {e}")
            return None
    
    async def search_candidates(
        self,
        query: str,
        skill_filters: Optional[List[str]] = None,
        min_experience: Optional[float] = None,
        top_k: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Search for candidates matching a query with optional filters.
        
        Args:
            query: Natural language search query
            skill_filters: List of required skills (lowercase)
            min_experience: Minimum years of experience
            top_k: Number of results to return
            
        Returns:
            List of matching candidates with scores
        """
        await self.initialize()
        
        if not self.index:
            print("Pinecone not available, returning empty results")
            return []
        
        try:
            # Generate query embedding
            query_embedding = await self.get_query_embedding(query)
            
            # Build filter
            filter_dict = {}
            
            if skill_filters:
                # Match any of the required skills
                filter_dict["skills"] = {"$in": [s.lower() for s in skill_filters]}
            
            if min_experience is not None and min_experience > 0:
                filter_dict["years_exp"] = {"$gte": min_experience}
            
            # Execute search
            results = self.index.query(
                vector=query_embedding,
                top_k=top_k,
                filter=filter_dict if filter_dict else None,
                include_metadata=True
            )
            
            # Format results
            candidates = []
            for match in results.matches:
                candidates.append({
                    "profile_id": int(match.id.replace("profile_", "")),
                    "score": match.score,
                    "skills": match.metadata.get("skills", []),
                    "years_exp": match.metadata.get("years_exp"),
                    "current_role": match.metadata.get("current_role"),
                    "current_company": match.metadata.get("current_company")
                })
            
            return candidates
            
        except Exception as e:
            print(f"Search failed: {e}")
            return []
    
    async def delete_profile(self, profile_id: int) -> bool:
        """Delete a profile from the vector index."""
        await self.initialize()
        
        if not self.index:
            return False
        
        try:
            self.index.delete(ids=[f"profile_{profile_id}"])
            return True
        except Exception as e:
            print(f"Failed to delete profile from index: {e}")
            return False


# Singleton instance
vector_search_service = VectorSearchService()


async def extract_skills_from_query(query: str) -> Dict[str, Any]:
    """
    Use Gemini to extract skills and intent from an HR search query.
    
    Example:
        "Good Java backend developer with 3 years experience"
        → {"skills": ["Java", "Backend Development"], "min_years": 3}
    """
    prompt = f"""Extract search criteria from this HR job search query. Return ONLY valid JSON.

Query: "{query}"

Return format:
{{
    "skills": ["skill1", "skill2"],
    "min_years": number or null,
    "role": "string or null",
    "other_requirements": "string or null"
}}

Examples:
- "Good Java backend developer with 3 years experience" → {{"skills": ["Java", "Backend Development"], "min_years": 3, "role": "Backend Developer", "other_requirements": null}}
- "Python ML engineer who knows AWS" → {{"skills": ["Python", "Machine Learning", "AWS"], "min_years": null, "role": "ML Engineer", "other_requirements": null}}

Now extract:"""

    client = get_genai_client()
    if not client:
        return {"skills": [], "min_years": None, "role": None, "other_requirements": None}
    
    from google import genai
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            temperature=0.1,
        )
    )
    
    response_text = response.text.strip()
    
    # Clean markdown if present
    if response_text.startswith("```json"):
        response_text = response_text[7:]
    if response_text.startswith("```"):
        response_text = response_text[3:]
    if response_text.endswith("```"):
        response_text = response_text[:-3]
    
    try:
        return json.loads(response_text.strip())
    except:
        return {"skills": [], "min_years": None, "role": None, "other_requirements": None}
