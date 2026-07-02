import os
import asyncio
import pandas as pd
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig, CacheMode
from bs4 import BeautifulSoup

def clean_and_parse_html_table(html_content):
    print("[Pipeline Engine] Parsing raw HTML grid via BeautifulSoup structure...")
    soup = BeautifulSoup(html_content, 'html.parser')
    
    # Target the KSPCB data table container
    table = soup.find('table')
    if not table:
        return []
        
    records = []
    rows = table.find_all('tr')
    
    print(f"[Pipeline Engine] Scanning {len(rows)} raw elements discovered inside the frame...")
    
    # Loop across rows skipping the header line
    for row in rows[1:]:
        cols = row.find_all('td')
        if len(cols) >= 8:
            # Extract basic cells securely
            inward_no = cols[0].text.strip()
            industry_info = cols[1].text.strip()
            regional_office = cols[3].text.strip()
            grant_date = cols[7].text.strip()
            
            # Extract the specific Consent Number/Document reference element
            consent_cell = cols[8]
            consent_no = consent_cell.text.strip()
            
            # Clean up the Industry Name (Extract ID if attached)
            industry_name = industry_info
            industry_id = "N/A"
            if "-" in industry_info:
                parts = industry_info.split("-", 1)
                industry_id = parts[0].strip()
                industry_name = parts[1].strip()

            # Generate an actionable manual tracking verification link for lookup
            search_tracking_url = f"https://karnataka.gov.in{industry_id}"

            records.append({
                "PCB Industry ID": industry_id,
                "Company/Project Name": industry_name,
                "Consent Number": consent_no,
                "Regional KSPCB Office": regional_office,
                "Approval Grant Date": grant_date,
                "Actionable Document Lookup": search_tracking_url,
                "Status": "Lead Captured - Review Required"
            })
            
    return records

async def main():
    dashboard_url = "https://xgn.karnataka.gov.in/CSHARP/ALLConsentOrder.aspx"
    output_file = "karnataka_stp_leads.csv"
    
    # Use a longer delay buffer to let all 50-100 table rows download from the state server
    run_config = CrawlerRunConfig(
        cache_mode=CacheMode.BYPASS, 
        wait_for="css:table",
        delay_before_return_html=8.0, 
        word_count_threshold=1
    )
    
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=dashboard_url, config=run_config)
        if not result.success:
            print("[Critical Error] Server baseline unreachable.")
            return
            
        html_payload = result.html
        
    # Run the core high-capacity parser
    scraped_leads = clean_and_parse_html_table(html_payload)
    
    if scraped_leads:
        df = pd.DataFrame(scraped_leads)
        
        # Ensure duplicate rows are removed to keep the sheet clean
        df.drop_duplicates(subset=["Consent Number"], keep="first", inplace=True)
        
        df.to_csv(output_file, mode='w', index=False)
        print(f"[Success] Extracted {len(df)} distinct rows into {output_file} successfully.")
    else:
        # Fallback tracking indicator if the portal experiences an outage during the run
        print("[System Note] Data stream empty. Verifying portal node parameters.")
        if not os.path.exists(output_file):
            df_empty = pd.DataFrame(columns=["PCB Industry ID", "Company/Project Name", "Consent Number", "Regional KSPCB Office", "Approval Grant Date", "Actionable Document Lookup", "Status"])
            df_empty.to_csv(output_file, index=False)

if __name__ == "__main__":
    asyncio.run(main())
