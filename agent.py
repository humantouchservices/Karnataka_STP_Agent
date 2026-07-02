import os
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field
import requests

# Define structured extraction schema for your lead data
class LeadExtractionSchema(BaseModel):
    company_name: str = Field(description="Name of the STP or environmental infrastructure firm.")
    contact_person: str = Field(default="N/A", description="Name of the key contact, engineer, or manager.")
    phone_number: str = Field(default="N/A", description="Contact phone numbers or mobile numbers.")
    email_address: str = Field(default="N/A", description="Professional email addresses found.")
    location: str = Field(default="Karnataka", description="City, district, or specific location in Karnataka.")

# 🟢 NEW FUNCTION: Automatically searches Google for genuine Karnataka STP pages using your API Key
def get_live_karnataka_stp_urls():
    print("[Agent] Querying SerpApi for fresh Karnataka STP data targets...")
    serpapi_key = os.getenv("SERPAPI_API_KEY")
    if not serpapi_key:
        print("[Error] No SERPAPI_API_KEY found. Defaulting to fallback list.")
        return ["https://karnataka.gov.in"] # Fallback to KSPCB official portal

    params = {
        "engine": "google",
        "q": "Sewage Treatment Plant STP operators consultants Karnataka contact list",
        "location": "Karnataka, India",
        "hl": "en",
        "gl": "in",
        "api_key": serpapi_key
    }
    
    try:
        response = requests.get("https://serpapi.com", params=params, timeout=15)
        results = response.json()
        urls = [item["link"] for item in results.get("organic_results", [])[:3]] # Take the top 3 live links
        print(f"[Agent] Target URLs discovered: {urls}")
        return urls
    except Exception as e:
        print(f"[Error] SerpApi query failed: {e}")
        return ["https://karnataka.gov.in"]

async def extract_stp_leads_from_url(url: str):
    print(f"[Agent] Target URL exploration initiated: {url}")
    
    # Configure the modern AsyncWebCrawler engine settings
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, # Force fresh data retrieval instead of cache
        word_count_threshold=10
    )
    
    # Asynchronously spin up the browser instance
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=run_config) #
        
        if not result.success:
            print(f"[Error] Failed to securely scrape target website: {url}")
            return None
            
        raw_markdown_data = result.markdown
        print(f"[Agent] Successfully retrieved {len(raw_markdown_data)} characters of unstructured data.")
        
    # Set up Structured Data Extraction using ChatOpenAI
    print("[Agent] Passing data to LLM processing engine for structuring...")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    # Force the LLM to strictly follow the target schema structure
    structured_llm = llm.with_structured_output(LeadExtractionSchema)
    
    try:
        # Prevent context overflows by truncating text safely
        prompt = f"Extract all Sewage Treatment Plant (STP) commercial leads, operators, or installation companies from this webpage:\n\n{raw_markdown_data[:12000]}"
        extracted_data = structured_llm.invoke(prompt)
        
        # Format properties neatly into a flat directory record
        lead_record = {
            "Company Name": extracted_data.company_name,
            "Contact Person": extracted_data.contact_person,
            "Phone Number": extracted_data.phone_number,
            "Email": extracted_data.email_address,
            "Location": extracted_data.location,
            "Source URL": url
        }
        return lead_record
        
    except Exception as e:
        print(f"[Error] LLM extraction interface processing failure: {e}")
        return None

async def main():
    # 🟢 DYNAMIC TARGETS: Leverages the live web search array instead of static examples
    target_urls = get_live_karnataka_stp_urls()
    
    all_leads = []
    for url in target_urls:
        lead = await extract_stp_leads_from_url(url)
        # Filter out clear invalid/blank matches from the execution loop
        if lead and lead["Company Name"].strip().upper() not in ["N/A", "NONE", ""]:
            all_leads.append(lead)
            
    output_file = "karnataka_stp_leads.csv"
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        # If file exists from yesterday, append new records; otherwise, create a new file
        if os.path.exists(output_file):
            df.to_csv(output_file, mode='a', header=False, index=False) #
        else:
            df.to_csv(output_file, index=False) #
        print(f"[Success] Data pipeline run finalized. Syncing rows to {output_file}.")
    else:
        # 🟢 FAILSAFE: Even if no leads are parsed today, create an empty sheet so Git can save it
        if not os.path.exists(output_file):
            df_empty = pd.DataFrame(columns=["Company Name", "Contact Person", "Phone Number", "Email", "Location", "Source URL"])
            df_empty.to_csv(output_file, index=False) #
        print(f"[Agent] Pipeline cycle completed. Workspace updated at {output_file}.")

if __name__ == "__main__":
    # Safely boots up the main asynchronous execution loop
    asyncio.run(main())
