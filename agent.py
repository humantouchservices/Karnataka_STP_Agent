import os
import json
import pandas as pd
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field
from crawl4ai import WebCrawler
from crawl4ai.chunking_strategy import RegexChunking
from crawl4ai.extraction_strategy import LLMExtractionStrategy
from serpapi import GoogleSearch

# Read the secure keys we saved in GitHub
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
SERPAPI_API_KEY = os.environ.get("SERPAPI_API_KEY")

class STPLeadSchema(BaseModel):
    company_or_project_name: Optional[str] = Field(None, description="Name of company/project in Karnataka.")
    project_address: Optional[str] = Field(None, description="Physical address in Karnataka.")
    office_address: Optional[str] = Field(None, description="Headquarters/Office address.")
    phone_number: Optional[str] = Field(None, description="Contact phone or mobile numbers.")
    stp_capacity: Optional[str] = Field(None, description="STP capacity metric (e.g., 50 KLD, 2 MLD).")

def discover_stp_urls(query: str) -> List[str]:
    search = GoogleSearch({"q": query, "api_key": SERPAPI_API_KEY, "num": 5})
    results = search.get_dict()
    return [r.get("link") for r in results.get("organic_results", []) if r.get("link")]

async def extract_stp_data(urls: List[str]):
    strategy = LLMExtractionStrategy(
        provider="openai/gpt-4o-mini",
        api_token=OPENAI_API_KEY,
        schema=STPLeadSchema.schema(),
        extraction_type="schema",
        instruction="Extract Karnataka Sewage Treatment Plant (STP) leads with addresses, phone numbers, and capacities.",
    )
    all_leads = []
    async with WebCrawler() as crawler:
        for url in urls:
            result = await crawler.arun(url=url, extraction_strategy=strategy, chunk_strategy=RegexChunking(), bypass_cache=True)
            if result.success and result.extracted_content:
                try:
                    data = json.loads(result.extracted_content)
                    if isinstance(data, list): all_leads.extend(data)
                    else: all_leads.append(data)
                except: continue
    return all_leads

async def main():
    # Tailored specifically for Karnataka, looking for recent directory/tender files
    query = "Sewage Treatment Plant STP contact directory capacity KLD Karnataka Bangalore"
    target_urls = discover_stp_urls(query)
    
    if not target_urls:
        print("No URLs found.")
        return
        
    leads = await extract_stp_data(target_urls)
    
    if leads:
        df = pd.DataFrame(leads)
        filename = "karnataka_stp_leads.csv"
        
        # If the file already exists, merge new data into it seamlessly
        if os.path.exists(filename):
            old_df = pd.read_csv(filename)
            df = pd.concat([old_df, df]).drop_duplicates().reset_index(drop=True)
            
        df.to_csv(filename, index=False)
        print(f"Successfully saved {len(leads)} leads to {filename}")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
