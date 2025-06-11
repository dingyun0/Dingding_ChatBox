import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_KEY=os.getenv("ANTHROPIC_API_KEY")

    CLAUDE_MODEL='claude-3-sonnet-20240229'
    MAX_TOKENS=1000
    TEMPERATURE=0.7
    
    
