import os
import json
import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict
from dotenv import load_dotenv
from collections import Counter

load_dotenv()
app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Load Questions from JSON file at startup ---
try:
    with open("data/questions.json", "r") as f:
        all_questions = json.load(f)["questions"]
except FileNotFoundError:
    all_questions = []
    print("WARNING: data/questions.json not found.")

# --- Pydantic Models ---
class GeneralAnswer(BaseModel):
    questionId: str
    selectedCategory: str

class NextPhaseRequest(BaseModel):
    answers: List[GeneralAnswer]

class FullQuizSubmission(BaseModel):
    all_answers: List[Dict[str, str]] # A list of dictionaries with question and answer text

# --- AI Prompt Engineering ---
system_prompt = """
You are an expert career counselor for Indian students. Your task is to analyze a student's responses from a two-phase quiz (general aptitude and specific interests) and recommend a primary and secondary academic stream (Arts, Science, Commerce).

You will receive a list of all questions and the student's selected answers.

Your response MUST be a single, clean JSON object and nothing else.
The JSON object must have the following structure:
{
  "recommended_stream": "The single best stream for the student (e.g., 'Science')",
  "secondary_stream": "The second best stream (e.g., 'Commerce')",
  "reason": "A short, encouraging, one-sentence explanation in English for your recommendation. Start with 'Based on your answers...'",
  "suitable_careers": [
    "A suitable career path (e.g., 'Software Developer')",
    "Another suitable career path (e.g., 'Data Scientist')",
    "A third career path (e.g., 'Researcher')"
  ]
}
"""

# --- API Endpoints ---

@app.get("/api/quiz/start")
def get_general_questions():
    """Returns the first set of general questions."""
    general_q = [q for q in all_questions if q.get("phase") == "general"]
    return {"questions": general_q}

@app.post("/api/quiz/next")
def get_specific_questions(request: NextPhaseRequest):
    """Determines the dominant category and returns specific questions for it."""
    if not request.answers:
        raise HTTPException(status_code=400, detail="No answers provided.")
    
    # Find the most selected category
    category_counts = Counter(ans.selectedCategory for ans in request.answers)
    dominant_category = category_counts.most_common(1)[0][0]
    
    # Get specific questions for that category
    specific_q = [q for q in all_questions if q.get("phase") == "specific" and q.get("category") == dominant_category]
    return {"dominant_category": dominant_category, "questions": specific_q}

@app.post("/api/quiz/submit")
async def submit_full_quiz(submission: FullQuizSubmission):
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="API key not configured")

    user_prompt_content = "Here is the student's full quiz transcript:\n\n"
    for ans in submission.all_answers:
        user_prompt_content += f"- Q: \"{ans.get('question')}\"\n  - A: \"{ans.get('answer')}\"\n"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json={
                    "model": "mistralai/mistral-7b-instruct:free",
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt_content}
                    ]
                }
            )
            response.raise_for_status()
            
            ai_response = response.json()

            # --- START OF DEBUGGING CODE ---
            print("----- AI RAW RESPONSE -----")
            print(ai_response)
            print("--------------------------")
            # --- END OF DEBUGGING CODE ---

            json_result = ai_response['choices'][0]['message']['content']
            
            return {"status": "success", "data": json_result}

    except httpx.HTTPStatusError as e:
        print(f"API Error: {e.response.text}")
        raise HTTPException(status_code=500, detail="Error communicating with AI service.")
    except Exception as e:
        # --- MORE DETAILED ERROR LOGGING ---
        print(f"An unexpected error occurred in submit_full_quiz: {type(e).__name__} - {e}")
        import traceback
        traceback.print_exc() # This will print the exact line where the error happened
        # --- END DETAILED LOGGING ---
        raise HTTPException(status_code=500, detail="An internal error occurred.")