import os
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Define structured extraction schema for your lead data
class LeadExtractionSchema(BaseModel):
    company_name: str = Field(description="Name of the STP, plant facility, or environmental contractor.")
    contact_person: str = Field(default="N/A", description="Name of the key contact, engineer, or supervisor.")
    phone_number: str = Field(default="N/A", description="Contact phone numbers or mobile numbers.")
    email_address: str = Field(default="N/A", description="Professional email addresses found.")
    location: str = Field(default="Karnataka", description="City, district, or specific neighborhood in Karnataka (e.g., Jakkur, Hebbal, Bengaluru).")

async def extract_stp_leads_from_url(url: str):
    print(f"[Agent] Target URL exploration initiated: {url}")
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, 
        word_count_threshold=5 # Reduced threshold to catch dense table layouts
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url, config=run_config)
        
        if not result.success:
            print(f"[Error] Failed to securely scrape target website: {url}")
            return None
            
        raw_markdown_data = result.markdown
        print(f"[Agent] Successfully retrieved {len(raw_markdown_data)} characters of unstructured data.")
        
    print("[Agent] Passing data to LLM processing engine for structuring...")
    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0.1,
        openai_api_key=os.getenv("OPENAI_API_KEY")
    )
    
    structured_llm = llm.with_structured_output(LeadExtractionSchema)
    
    try:
        # Prompt instructs the LLM to scrape dense infrastructure directories
        prompt = f"Extract all Sewage Treatment Plant (STP) profiles, operators, locations, or contractor contacts listed here:\n\n{raw_markdown_data[:15000]}"
        extracted_data = structured_llm.invoke(prompt)
        
        lead_record = {
            "Company/Plant Name": extracted_data.company_name,
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
    # 🟢 STEP 1: PASTE YOUR WEBSITES HERE
    # You can add or replace any URLs inside this bracketed list
    target_urls = [
        "https://bwssb.karnataka.gov.in/98/waste-water-management/en",
        "https://tpro.telsys.in/tpportal/bwssb",
        "https://www.indiawaterportal.org/water-quality-and-pollution/waste-water-/bengalurus-stp-monitoring-challenge"
    ]
    
    all_leads = []
    for url in target_urls:
        lead = await extract_stp_leads_from_url(url)
        if lead and lead["Company/Plant Name"].strip().upper() not in ["N/A", "NONE", ""]:
            all_leads.append(lead)
            
    output_file = "karnataka_stp_leads.csv"
    
    if all_leads:
        df = pd.DataFrame(all_leads)
        if os.path.exists(output_file):
            df.to_csv(output_file, mode='a', header=False, index=False)
        else:
            df.to_csv(output_file, index=False)
        print(f"[Success] Data pipeline run finalized. Syncing rows to {output_file}.")
    else:
        if not os.path.exists(output_file):
            df_empty = pd.DataFrame(columns=["Company/Plant Name", "Contact Person", "Phone Number", "Email", "Location", "Source URL"])
            df_empty.to_csv(output_file, index=False)
        print(f"[Agent] Scraping process ran but returned no new data objects for {output_file}.")

if __name__ == "__main__":
    asyncio.run(main())
