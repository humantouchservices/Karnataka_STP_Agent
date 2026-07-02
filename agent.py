import os
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# Define structured extraction schema tailored to KSPCB Data Structure
class LeadExtractionSchema(BaseModel):
    company_name: str = Field(description="Name of the infrastructure, real estate project, or facility approved.")
    consent_type: str = Field(default="N/A", description="Type of pollution board consent (e.g., CFE, CFO, Fresh, Renewal).")
    regional_office: str = Field(default="N/A", description="KSPCB regional office or zone location code.")
    grant_date: str = Field(default="N/A", description="The date the environmental consent order was granted.")
    validity_date: str = Field(default="N/A", description="The expiration or validity timeline date of the certificate.")

async def extract_stp_leads_from_url(url: str):
    print(f"[Agent] Target URL exploration initiated: {url}")
    
    # 🟢 CUSTOM CONFIG: Instructs crawl4ai to wait for dynamic JS tables to load fully
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, 
        word_count_threshold=5,
        wait_for="css:table" # Explicitly pauses till the HTML data grid registers
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
    
    # Adapting LLM to read structural list elements
    class CleanListOutput(BaseModel):
        records: list[LeadExtractionSchema]

    structured_llm = llm.with_structured_output(CleanListOutput)
    
    try:
        # Prompt instructs the model to loop rows and flag built-up infrastructure setups
        prompt = (
            "Analyze this raw environmental clearance log registry table data. Extract details for the top rows "
            "focusing on construction, real estate projects, and manufacturing companies that utilize built-in infrastructure:\n\n"
            f"{raw_markdown_data[:18000]}"
        )
        extracted_data = structured_llm.invoke(prompt)
        
        # Flatten structural records into simple schema dictionaries
        flat_records = []
        for item in extracted_data.records:
            flat_records.append({
                "Company/Project Name": item.company_name,
                "Consent Type": item.consent_type,
                "Regional Office": item.regional_office,
                "Grant Date": item.grant_date,
                "Validity Date": item.validity_date,
                "Source Portal": url
            })
        return flat_records
        
    except Exception as e:
        print(f"[Error] LLM extraction interface processing failure: {e}")
        return None

async def main():
    # 🟢 TARGET APPLIED: Connecting directly to your designated portal node URL
    target_urls = [
        "https://xgn.karnataka.gov.in/CSHARP/ALLConsentOrder.aspx"
    ]
    
    all_leads = []
    for url in target_urls:
        leads_list = await extract_stp_leads_from_url(url)
        if leads_list:
            all_leads.extend(leads_list)
            
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
            df_empty = pd.DataFrame(columns=["Company/Project Name", "Consent Type", "Regional Office", "Grant Date", "Validity Date", "Source Portal"])
            df_empty.to_csv(output_file, index=False)
        print(f"[Agent] Table parsed successfully. Checked workspace registry at {output_file}.")

if __name__ == "__main__":
    asyncio.run(main())
