import os
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

# 🟢 STAGE 1 SCHEMA: For extracting document urls from the main dashboard grid
class ConsentRowSchema(BaseModel):
    company_name: str = Field(description="Name of the applicant company or project.")
    consent_number: str = Field(description="The unique Consent Number.")
    document_url: str = Field(description="The absolute link or URL attached to the consent number text.")

# 🟢 STAGE 2 SCHEMA: Deep data extracted from inside the individual document pages
class DeepSTPDetailsSchema(BaseModel):
    client_name: str = Field(description="Official name of the client, developer, or industry operator.")
    stp_required: str = Field(description="Yes or No indicator if an STP/ETP facility installation is mandated.")
    stp_capacity: str = Field(default="N/A", description="Capacity of the Sewage Treatment Plant mentioned (e.g., 50 KLD, 1 MLD).")
    discharge_standards: str = Field(default="N/A", description="Treated water disposal or reuse requirements (e.g., flushing, gardening).")
    contact_details: str = Field(default="N/A", description="Any phone numbers, emails, or office addresses located inside the document text.")

async def get_consent_rows_from_dashboard(dashboard_url: str):
    print(f"[Agent Step 1] Extracting rows and link objects from: {dashboard_url}")
    
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, 
        wait_for="css:table",
        word_count_threshold=2
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=dashboard_url, config=run_config)
        if not result.success:
            return []
            
        raw_markdown = result.markdown
        
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=os.getenv("OPENAI_API_KEY"))
    
    class RowList(BaseModel):
        rows: list[ConsentRowSchema]
        
    structured_llm = llm.with_structured_output(RowList)
    
    try:
        prompt = (
            "Analyze this KSPCB XGN environmental portal data table. "
            "Extract the Company Name, Consent Number, and the exact destination URL/Link attached to that consent number text. "
            "Ensure the URL is a complete link:\n\n" + raw_markdown[:15000]
        )
        extracted = structured_llm.invoke(prompt)
        return extracted.rows
    except Exception as e:
        print(f"[Error Stage 1] Link indexing parsing failure: {e}")
        return []

async def extract_deep_stp_data(document_url: str):
    print(f"[Agent Step 2] Deep scanning target order document: {document_url}")
    
    run_config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS, word_count_threshold=5)
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=document_url, config=run_config)
        if not result.success:
            return None
        document_text = result.markdown
        
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.1, openai_api_key=os.getenv("OPENAI_API_KEY"))
    structured_llm = llm.with_structured_output(DeepSTPDetailsSchema)
    
    try:
        prompt = (
            "Read this specific environmental consent order approval text carefully. "
            "Extract deep metrics regarding client identifiers and wastewater engineering configurations:\n\n" + document_text[:15000]
        )
        return structured_llm.invoke(prompt)
    except Exception as e:
        print(f"[Error Stage 2] Document synthesis issue: {e}")
        return None

async def main():
    dashboard_url = "https://xgn.karnataka.gov.in/CSHARP/ALLConsentOrder.aspx"
    output_file = "karnataka_stp_leads.csv"
    
    # Stage 1: Get top rows and their document links
    consent_rows = await get_consent_rows_from_dashboard(dashboard_url)
    
    all_deep_leads = []
    
    # Stage 2: Deep crawl the top 3 documents to avoid rate limits/timeouts
    for row in consent_rows[:3]:
        # Skip if the link didn't extract cleanly
        if not row.document_url or "http" not in row.document_url:
            continue
            
        deep_data = await extract_deep_stp_data(row.document_url)
        
        if deep_data:
            all_deep_leads.append({
                "Consent Number": row.consent_number,
                "Client Name": deep_data.client_name,
                "STP Required": deep_data.stp_required,
                "STP Capacity": deep_data.stp_capacity,
                "Discharge Standards": deep_data.discharge_standards,
                "Contact Info": deep_data.contact_details,
                "Document Link": row.document_url
            })
            
    if all_deep_leads:
        df = pd.DataFrame(all_deep_leads)
        if os.path.exists(output_file):
            df.to_csv(output_file, mode='a', header=False, index=False)
        else:
            df.to_csv(output_file, index=False)
        print(f"[Success] Data pipeline run finalized. Deep data saved to {output_file}.")
    else:
        if not os.path.exists(output_file):
            df_empty = pd.DataFrame(columns=["Consent Number", "Client Name", "STP Required", "STP Capacity", "Discharge Standards", "Contact Info", "Document Link"])
            df_empty.to_csv(output_file, index=False)
        print("[Agent] Deep crawl iteration finished without harvesting new data blocks.")

if __name__ == "__main__":
    asyncio.run(main())
