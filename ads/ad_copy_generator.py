"""
Ad copy generator for Google Responsive Search Ads and Meta ads.

Provides production-ready ad copy for all supported sub-verticals
across home services, real estate, and B2B verticals.
"""

from __future__ import annotations

from ads.targeting_config import TargetingConfig

# ---------------------------------------------------------------------------
# Vertical → category mapping
# ---------------------------------------------------------------------------
_VERTICAL_CATEGORY: dict[str, str] = {
    "hvac": "home_services",
    "roofing": "home_services",
    "solar": "home_services",
    "plumbing": "home_services",
    "electrical": "home_services",
    "water_damage": "home_services",
    "windows": "home_services",
    "pest_control": "home_services",
    "dscr_loan": "real_estate",
    "hard_money": "real_estate",
    "fix_and_flip": "real_estate",
    "bridge_loan": "real_estate",
    "commercial_re": "real_estate",
    "wholesale_buyer": "real_estate",
    "smb": "b2b",
    "mid_market": "b2b",
    "enterprise": "b2b",
}

# ---------------------------------------------------------------------------
# Google RSA ad copy — all sub-verticals
# ALL headlines MUST be ≤ 30 characters.
# ---------------------------------------------------------------------------
_GOOGLE_RSA_COPY: dict[str, dict] = {
    "hvac": {
        "headlines": [
            "AC Broke? Same Day Fix",
            "Licensed HVAC – Florida",
            "Free AC Estimate Today",
            "Beat the Florida Heat",
            "24/7 Emergency AC Repair",
            "Top Rated HVAC Company",
            "AC Repair Near You",
            "Fast HVAC Service",
            "Trusted Local HVAC Tech",
            "New AC Units Installed",
            "Cut Your Electric Bill",
            "Certified HVAC Experts",
            "AC Tune-Up Special",
            "Same Day AC Service",
            "Florida HVAC Pros",
        ],
        "descriptions": [
            "Licensed & insured HVAC technicians ready 24/7. Same-day service available across Florida.",
            "Free estimates on all AC repairs and replacements. Beat the heat with our certified techs.",
            "Top-rated HVAC company serving Florida homeowners. Call now for fast, affordable service.",
            "AC tune-ups, repairs & new installs. Financing available. Certified HVAC pros near you.",
        ],
        "display_path": ["hvac", "florida"],
        "final_url": "https://example.com/hvac",
    },
    "roofing": {
        "headlines": [
            "Storm Damage? Free Inspect",
            "Licensed Roofer – Florida",
            "Free Roof Estimate Today",
            "Hurricane Ready Roofing",
            "Roof Leak? Call Us Now",
            "Top Rated Roofing Co",
            "Shingle & Metal Roofs",
            "Insurance Claims Expert",
            "New Roof Financing Avail",
            "30-Year Roof Warranty",
            "Roof Repair Same Day",
            "Free Drone Roof Inspect",
            "Certified Roofing Pros",
            "Flat & Tile Roofs",
            "Florida's Best Roofers",
        ],
        "descriptions": [
            "Licensed Florida roofer specializing in storm damage claims. Free drone inspection included.",
            "Shingle, metal, tile & flat roofs. 30-year warranty. Insurance claims handled for you.",
            "Hurricane-ready roofing solutions for Florida homes. Financing available. Call today.",
            "Free estimates on all roof repairs and replacements. Certified, insured roofing pros.",
        ],
        "display_path": ["roofing", "florida"],
        "final_url": "https://example.com/roofing",
    },
    "solar": {
        "headlines": [
            "Cut Power Bill by 90%",
            "Free Solar Estimate FL",
            "Go Solar – $0 Down",
            "Florida Solar Pros",
            "Solar Install This Month",
            "25-Year Panel Warranty",
            "Own Your Energy Today",
            "Solar Tax Credit 2024",
            "No Electric Bill Ever",
            "Florida Solar Leaders",
            "Get Solar Quote Now",
            "Top Solar Company FL",
            "Battery Backup Included",
            "Best Solar Deal FL",
            "Solar Savings Start Now",
        ],
        "descriptions": [
            "$0 down solar installations in Florida. Lock in your power rate and stop paying FPL.",
            "Federal tax credit + state incentives available. Cut your electric bill by up to 90%.",
            "Top-rated solar company serving all of Florida. 25-year panel warranty. Battery add-ons.",
            "Get a free solar quote today. Most homeowners save $150+/month after going solar.",
        ],
        "display_path": ["solar", "florida"],
        "final_url": "https://example.com/solar",
    },
    "plumbing": {
        "headlines": [
            "Plumber – Same Day Fix",
            "24/7 Emergency Plumber",
            "Licensed Plumber FL",
            "Drain Clog? Fixed Fast",
            "Free Plumbing Estimate",
            "Water Heater Experts",
            "Pipe Leak? Call Now",
            "Trusted Local Plumber",
            "Fast Plumbing Service",
            "Plumbing Pros Near You",
            "Sewer Line Specialists",
            "Affordable Plumber FL",
            "Same Day Drain Cleaning",
            "Top Rated Plumber",
            "Florida Plumbing Pros",
        ],
        "descriptions": [
            "Licensed & insured plumbers available 24/7. Same-day service for emergencies across FL.",
            "From clogged drains to water heater replacements — we fix it fast at fair prices.",
            "Top-rated local plumbers serving Florida. Free estimates. Financing on larger jobs.",
            "Emergency plumbing service available now. Pipe leaks, sewer lines, water heaters & more.",
        ],
        "display_path": ["plumbing", "florida"],
        "final_url": "https://example.com/plumbing",
    },
    "electrical": {
        "headlines": [
            "Licensed Electrician FL",
            "Panel Upgrades – Fast",
            "24/7 Electrical Service",
            "Free Electrical Estimate",
            "Certified Electrician",
            "EV Charger Install FL",
            "Rewiring Specialists",
            "Electrical Repair Fast",
            "Trusted Electrician FL",
            "Generator Install Pros",
            "Code Compliance Experts",
            "Same Day Electric Fix",
            "Top Rated Electrician",
            "Smart Home Wiring FL",
            "Florida Electric Pros",
        ],
        "descriptions": [
            "Licensed electricians serving all of Florida. Panel upgrades, rewiring, EV charger installs.",
            "24/7 electrical repairs, generator installs & panel upgrades. Free estimates available.",
            "Certified, insured electricians ready today. Code compliance and safety inspections done.",
            "From simple repairs to full rewires — trusted electricians with 5-star reviews statewide.",
        ],
        "display_path": ["electrical", "florida"],
        "final_url": "https://example.com/electrical",
    },
    "water_damage": {
        "headlines": [
            "Water Damage? Call Now",
            "24/7 Flood Cleanup FL",
            "Mold Removal Experts",
            "Insurance Claims Help",
            "Fast Water Restoration",
            "Certified Restoration Co",
            "Free Damage Assessment",
            "Flood Cleanup Today",
            "Mold Remediation Fast",
            "Water Damage Pros FL",
            "Storm Damage Cleanup",
            "Drying in 72 Hours",
            "Burst Pipe Restoration",
            "Top Rated Restoration",
            "Florida Water Damage",
        ],
        "descriptions": [
            "24/7 water damage restoration across Florida. We work directly with your insurance carrier.",
            "Certified mold remediation & flood cleanup. Most jobs dried in 72 hours or less.",
            "Storm, flood or burst pipe damage? Call now for a free assessment and immediate response.",
            "Top-rated restoration company. Direct insurance billing. Licensed, bonded & certified.",
        ],
        "display_path": ["water-damage", "florida"],
        "final_url": "https://example.com/water-damage",
    },
    "windows": {
        "headlines": [
            "Impact Windows – FL",
            "Free Window Estimate",
            "Hurricane Windows FL",
            "New Windows Installed",
            "Window Replacement FL",
            "Impact Glass Experts",
            "Save on Energy Bills",
            "Financing Available",
            "Top Rated Window Co",
            "Windows & Doors FL",
            "Same Week Install",
            "Cut Noise & Heat",
            "Certified Window Pros",
            "Storm Proof Windows",
            "Florida Window Experts",
        ],
        "descriptions": [
            "Hurricane-rated impact windows & doors for Florida homes. Free estimates. Financing avail.",
            "Energy-efficient window replacements that lower your electric bill and block storm damage.",
            "Top-rated window company serving all of Florida. Same-week installation available now.",
            "Impact windows cut noise, heat & hurricane damage. Licensed installers. Get quote today.",
        ],
        "display_path": ["windows", "florida"],
        "final_url": "https://example.com/windows",
    },
    "pest_control": {
        "headlines": [
            "Pest Control – FL",
            "Termite Treatment Fast",
            "Bug-Free Guarantee",
            "Free Pest Inspection",
            "Same Day Exterminator",
            "Licensed Pest Control",
            "Mosquito Treatment FL",
            "Rodent Removal Fast",
            "Affordable Pest Control",
            "Termite Bond Service",
            "Ant & Roach Experts",
            "Year Round Protection",
            "Top Rated Exterminator",
            "Eco-Friendly Pest Fix",
            "Florida Pest Pros",
        ],
        "descriptions": [
            "Licensed pest control specialists serving all of Florida. Same-day service available.",
            "Termite bonds, mosquito treatments, rodent removal & more. Bug-free guarantee included.",
            "Eco-friendly pest control solutions for Florida homes. Free inspection with every call.",
            "Affordable year-round pest protection plans starting at $49/month. Call for quote today.",
        ],
        "display_path": ["pest-control", "florida"],
        "final_url": "https://example.com/pest-control",
    },
    "dscr_loan": {
        "headlines": [
            "DSCR Loans – No W2s",
            "Investor Loans – Fast",
            "DSCR – Close in 21 Days",
            "No Tax Returns Needed",
            "Rental Income Qualifies",
            "DSCR from 100K-3M",
            "75% LTV All Prop Types",
            "Real Estate Invest Loans",
            "Fast DSCR Pre-Approval",
            "Investment Prop Experts",
            "DSCR Loans – FL Experts",
            "No Income Docs Required",
            "DSCR Refi Available",
            "All Property Types OK",
            "Get DSCR Quote Now",
        ],
        "descriptions": [
            "DSCR loans close in 21 days. No W2s, no tax returns — qualify on rental income alone.",
            "$100K to $3M. 75% LTV. All property types. Fast pre-approval for FL investors.",
            "Investment property experts. DSCR purchase and refi available. Get your quote today.",
            "Stop letting deals slip — our DSCR loans move fast. Direct lender. No broker fees.",
        ],
        "display_path": ["dscr-loans", "florida"],
        "final_url": "https://example.com/dscr-loans",
    },
    "hard_money": {
        "headlines": [
            "Hard Money – Fast Close",
            "Fix & Flip Funding Fast",
            "Hard Money 24hr Approval",
            "Rehab Loans FL Expert",
            "Close in 7 Days",
            "No Credit Score Min",
            "Hard Money Up to 90% LTV",
            "Bridge Loans Available",
            "Fast Real Estate Funding",
            "Direct Hard Money Lender",
            "Hard Money – No BS",
            "Flip Financing Expert",
            "Fund Your Next Deal Now",
            "Investor Friendly Terms",
            "Hard Money FL Pros",
        ],
        "descriptions": [
            "Hard money loans approved in 24 hours. Close in 7 days. Up to 90% LTV. No min credit.",
            "Fix & flip financing from a direct lender. No broker fees. Fast funding for FL investors.",
            "Rehab loans, bridge loans & hard money for Florida real estate. Apply online in minutes.",
            "Fund your next deal fast. $50K to $5M available. Investor-friendly terms. Call now.",
        ],
        "display_path": ["hard-money", "florida"],
        "final_url": "https://example.com/hard-money",
    },
    "fix_and_flip": {
        "headlines": [
            "Fix & Flip Loans – FL",
            "Rehab Loan Fast Close",
            "Flip Funding 24hr OK",
            "Up to 90% of Cost",
            "Fix Flip – No W2s",
            "Draw Schedule Avail",
            "Close in 10 Days",
            "Direct Flip Lender",
            "Rehab + ARV Lending",
            "100% Rehab Funded",
            "Fast Flip Approval",
            "Fix Flip Experts FL",
            "ARV Up to 70% Avail",
            "Fund Your Flip Now",
            "FL Fix Flip Pros",
        ],
        "descriptions": [
            "Fix and flip loans with up to 90% of purchase + 100% of rehab funded. Close in 10 days.",
            "Direct lender for Florida fix-and-flip investors. No W2s required. 24hr approval.",
            "ARV-based lending up to 70% of after-repair value. Draw schedules. Fast closings.",
            "Fund your next flip without the red tape. Rehab loans for FL investors. Apply now.",
        ],
        "display_path": ["fix-and-flip", "florida"],
        "final_url": "https://example.com/fix-and-flip",
    },
    "bridge_loan": {
        "headlines": [
            "Bridge Loans – FL",
            "Short-Term RE Loans",
            "Bridge Loan Fast Close",
            "Gap Financing Avail",
            "Close Before You Sell",
            "Bridge Loan 7 Days",
            "No Prepay Penalty",
            "Bridge Up to 75% LTV",
            "Buy Before You Sell",
            "Flexible Bridge Terms",
            "Bridge Refi Available",
            "Commercial Bridge Loan",
            "Fast Bridge Approval",
            "FL Bridge Loan Pros",
            "Fund the Gap Now",
        ],
        "descriptions": [
            "Bridge loans for Florida real estate. Close in 7 days. No prepayment penalties.",
            "Buy your next property before selling the current one. Up to 75% LTV bridge financing.",
            "Short-term real estate bridge loans. Commercial and residential. Flexible repayment terms.",
            "Gap financing for investors and homeowners. Fast approvals, competitive rates in FL.",
        ],
        "display_path": ["bridge-loans", "florida"],
        "final_url": "https://example.com/bridge-loans",
    },
    "commercial_re": {
        "headlines": [
            "Commercial RE Loans FL",
            "CRE Loans – Fast Close",
            "Office & Retail Loans",
            "Multi-Family Financing",
            "Commercial Mortgage FL",
            "CRE Up to $20M",
            "Non-Recourse Options",
            "SBA & Conv CRE Loans",
            "Mixed-Use Financing",
            "Commercial Refi Fast",
            "Industrial Loans FL",
            "CRE Experts – Florida",
            "Investor CRE Programs",
            "Fast CRE Approval",
            "Get CRE Quote Today",
        ],
        "descriptions": [
            "Commercial real estate loans up to $20M. Office, retail, multi-family, industrial & more.",
            "Fast CRE financing in Florida. SBA, conventional & non-recourse options available.",
            "Mixed-use, multi-family and commercial mortgage specialists. Competitive rates. Close fast.",
            "Experienced commercial lenders serving FL investors. Get your CRE quote in 24 hours.",
        ],
        "display_path": ["commercial-re", "florida"],
        "final_url": "https://example.com/commercial-re",
    },
    "wholesale_buyer": {
        "headlines": [
            "We Buy Houses Cash FL",
            "Cash Offer in 24 Hours",
            "Sell Your House Fast",
            "No Repairs Needed",
            "Close in 7 Days",
            "Skip the Listing",
            "Any Condition Homes",
            "Wholesale Buyers FL",
            "Fast Cash Home Buyers",
            "Fair Cash Offer Today",
            "No Agent Fees",
            "Inherited Home? We Buy",
            "Avoid Foreclosure Fast",
            "Cash for Homes FL",
            "FL Cash Home Buyers",
        ],
        "descriptions": [
            "We buy Florida houses for cash. Any condition. Close in 7 days. No repairs, no agents.",
            "Get a fair cash offer in 24 hours. No obligation. Skip the listing process entirely.",
            "Avoid foreclosure, inherited properties, problem tenants — we buy as-is, fast.",
            "Trusted cash home buyers across Florida. No fees, no commissions, no hassle.",
        ],
        "display_path": ["cash-buyers", "florida"],
        "final_url": "https://example.com/cash-buyers",
    },
    "smb": {
        "headlines": [
            "SMB Leads – Verified FL",
            "Local Business Leads",
            "B2B Leads – Fast Delivery",
            "Small Biz Data – FL",
            "Targeted SMB Lists",
            "Fresh SMB Contacts",
            "SMB Email Lists FL",
            "Local Biz Leads Fast",
            "Verified B2B Contacts",
            "SMB Lead Gen Experts",
            "Skip Trace for Biz",
            "New SMB Leads Daily",
            "Buy SMB Lead Lists",
            "Quality B2B Data FL",
            "SMB Leads That Convert",
        ],
        "descriptions": [
            "Verified Florida small business leads with owner contact info. Fresh data delivered fast.",
            "Targeted SMB contact lists for local marketing. Email, phone & address included.",
            "Florida B2B lead generation specialists. Verified SMB contacts ready to import.",
            "Stop cold calling wrong numbers. Get verified small business leads in FL today.",
        ],
        "display_path": ["smb-leads", "florida"],
        "final_url": "https://example.com/smb-leads",
    },
    "mid_market": {
        "headlines": [
            "Mid-Market B2B Leads",
            "Verified Biz Contacts",
            "B2B Sales Leads – Fast",
            "Mid-Market Data FL",
            "Decision Maker Leads",
            "B2B Outreach Lists",
            "Fresh Mid-Market Data",
            "Target Mid-Size Firms",
            "B2B Pipeline Builder",
            "Qualified B2B Leads",
            "CRM-Ready Lead Data",
            "Mid-Market Prospects",
            "B2B Lead Experts FL",
            "Sales Leads Delivered",
            "Grow Your Pipeline Now",
        ],
        "descriptions": [
            "Mid-market B2B leads with verified decision-maker contacts. CRM-ready data delivered fast.",
            "Target Florida companies with 50-500 employees. Fresh contact data for your sales team.",
            "Qualified mid-market prospects with phone, email and LinkedIn. Accelerate your pipeline.",
            "Stop wasting time on bad data. Get verified mid-market B2B contacts for FL outreach.",
        ],
        "display_path": ["mid-market", "b2b"],
        "final_url": "https://example.com/mid-market-leads",
    },
    "enterprise": {
        "headlines": [
            "Enterprise B2B Leads",
            "C-Suite Contact Data",
            "Fortune 500 Contacts",
            "Enterprise Sales Leads",
            "VP & Director Emails",
            "Enterprise Data FL",
            "Target Big Companies",
            "Decision Maker Lists",
            "Enterprise Outreach",
            "B2B Enterprise Pros",
            "Close Enterprise Deals",
            "Executive Lead Lists",
            "Intent Data Available",
            "Enterprise Pipeline",
            "Enterprise Leads Fast",
        ],
        "descriptions": [
            "Enterprise B2B lead lists with C-suite, VP and Director contacts. Verified and current.",
            "Target Fortune 500 and large-cap companies in Florida with verified executive data.",
            "Intent-driven enterprise leads for complex sales cycles. CRM-ready. Delivered same day.",
            "Build your enterprise pipeline faster. Verified decision-maker contacts for FL firms.",
        ],
        "display_path": ["enterprise", "b2b"],
        "final_url": "https://example.com/enterprise-leads",
    },
}

# ---------------------------------------------------------------------------
# Meta ad copy — all sub-verticals
# ---------------------------------------------------------------------------
_META_AD_COPY: dict[str, dict] = {
    "hvac": {
        "primary_text": (
            "Florida homeowners — your AC shouldn't be a guessing game. "
            "Our licensed HVAC techs provide same-day service, honest pricing, and a 1-year guarantee. "
            "✅ Same-day service available\n✅ Free estimates\n✅ Licensed & insured in FL"
        ),
        "headline": "AC Repair – Same Day Service",
        "description": "Licensed FL HVAC Techs. Free Estimates.",
        "call_to_action": "Get Quote",
    },
    "roofing": {
        "primary_text": (
            "Florida storm season is unpredictable — is your roof ready? "
            "Our certified roofers provide free drone inspections and handle all insurance claims. "
            "✅ Free drone roof inspection\n✅ Insurance claims experts\n✅ 30-year warranty"
        ),
        "headline": "Free Roof Inspection – FL",
        "description": "Storm Damage Experts. 30-Yr Warranty.",
        "call_to_action": "Book Inspection",
    },
    "solar": {
        "primary_text": (
            "Florida gets 300+ days of sunshine — stop paying FPL for it. "
            "Switch to solar with $0 down and lock in your rate for 25 years. "
            "✅ $0 down installation\n✅ Federal tax credit available\n✅ 25-year panel warranty"
        ),
        "headline": "Go Solar – $0 Down in Florida",
        "description": "Cut Your Electric Bill by 90%.",
        "call_to_action": "Get Free Quote",
    },
    "plumbing": {
        "primary_text": (
            "Plumbing problems don't wait — neither do we. "
            "Our licensed Florida plumbers are available 24/7 for emergencies, repairs, and installations. "
            "✅ 24/7 emergency service\n✅ Same-day appointments\n✅ Licensed & insured"
        ),
        "headline": "24/7 Plumber – Same Day FL",
        "description": "Licensed Plumbers. Free Estimates.",
        "call_to_action": "Call Now",
    },
    "electrical": {
        "primary_text": (
            "Electrical problems are a fire hazard — don't wait. "
            "Our licensed Florida electricians handle panel upgrades, rewiring, EV chargers, and more. "
            "✅ Panel upgrades & rewiring\n✅ EV charger installations\n✅ Free estimates"
        ),
        "headline": "Licensed Electrician – FL",
        "description": "Panel Upgrades. EV Chargers. Free Est.",
        "call_to_action": "Get Quote",
    },
    "water_damage": {
        "primary_text": (
            "Water damage gets worse every hour you wait. "
            "Our certified restoration team responds 24/7 and works directly with your insurance carrier. "
            "✅ 24/7 emergency response\n✅ Direct insurance billing\n✅ Dry in 72 hours"
        ),
        "headline": "Water Damage? Call Us Now",
        "description": "24/7 Response. Insurance Direct Bill.",
        "call_to_action": "Call Now",
    },
    "windows": {
        "primary_text": (
            "Hurricane season is coming. Impact windows pay for themselves in one storm. "
            "Get hurricane-rated windows installed this month — financing available. "
            "✅ Hurricane-rated impact glass\n✅ Financing available\n✅ Energy efficient"
        ),
        "headline": "Impact Windows – Florida",
        "description": "Hurricane Rated. Financing Available.",
        "call_to_action": "Get Free Quote",
    },
    "pest_control": {
        "primary_text": (
            "Florida pests are year-round — your protection should be too. "
            "Get a free inspection and keep your home bug-free with our guaranteed pest control plans. "
            "✅ Free inspection\n✅ Bug-free guarantee\n✅ Year-round protection plans"
        ),
        "headline": "Free Pest Inspection – FL",
        "description": "Bug-Free Guarantee. Year-Round Plans.",
        "call_to_action": "Book Free Inspection",
    },
    "dscr_loan": {
        "primary_text": (
            "Investors — stop letting deals slip because of slow lenders. "
            "Our DSCR loans close in 21 days or less. No tax returns. No W2s. Just the deal. "
            "✅ Loans $100K–$3M\n✅ 75% LTV\n✅ All property types"
        ),
        "headline": "DSCR Loans – Close in 21 Days",
        "description": "No W2s. No Tax Returns.",
        "call_to_action": "Apply Now",
    },
    "hard_money": {
        "primary_text": (
            "Stop losing deals to slow conventional lenders. "
            "Our hard money loans close in 7 days — 24-hour approval, up to 90% LTV, no min credit score. "
            "✅ Close in 7 days\n✅ 24-hour approval\n✅ Up to 90% LTV"
        ),
        "headline": "Hard Money – Close in 7 Days",
        "description": "24hr Approval. No Min Credit Score.",
        "call_to_action": "Apply Now",
    },
    "fix_and_flip": {
        "primary_text": (
            "Ready to flip your next Florida property? "
            "We fund up to 90% of purchase + 100% of rehab costs with fast draw schedules. "
            "✅ Up to 90% of purchase price\n✅ 100% rehab funded\n✅ Close in 10 days"
        ),
        "headline": "Fix & Flip Loans – FL",
        "description": "90% LTV. 100% Rehab. Close in 10 Days.",
        "call_to_action": "Get Funded",
    },
    "bridge_loan": {
        "primary_text": (
            "Need to buy before you sell? Our bridge loans make it possible. "
            "Close in 7 days, no prepayment penalties, flexible terms for FL investors. "
            "✅ Close in 7 days\n✅ No prepayment penalty\n✅ Up to 75% LTV"
        ),
        "headline": "Bridge Loans – Close in 7 Days",
        "description": "Buy Before You Sell. No Prepay Penalty.",
        "call_to_action": "Apply Now",
    },
    "commercial_re": {
        "primary_text": (
            "Florida commercial real estate is booming — fund your next deal with us. "
            "CRE loans up to $20M with fast approvals and competitive rates. "
            "✅ Loans up to $20M\n✅ Office, retail, multi-family & more\n✅ Non-recourse options"
        ),
        "headline": "Commercial RE Loans – FL",
        "description": "Up to $20M. Fast CRE Approvals.",
        "call_to_action": "Get Quote",
    },
    "wholesale_buyer": {
        "primary_text": (
            "Need to sell your Florida home fast — without the hassle? "
            "We buy houses as-is for cash. No repairs, no agents, no fees. Close in 7 days. "
            "✅ Cash offer in 24 hours\n✅ Any condition\n✅ Close in 7 days"
        ),
        "headline": "We Buy FL Houses – Cash Offer",
        "description": "Any Condition. No Fees. Close in 7 Days.",
        "call_to_action": "Get Cash Offer",
    },
    "smb": {
        "primary_text": (
            "Stop wasting time on cold lists that don't convert. "
            "Get verified Florida small business leads with owner contact info — delivered same day. "
            "✅ Verified owner contact data\n✅ Phone, email & address\n✅ Fresh data daily"
        ),
        "headline": "Verified SMB Leads – Florida",
        "description": "Owner Contact Data. Same-Day Delivery.",
        "call_to_action": "Get Leads",
    },
    "mid_market": {
        "primary_text": (
            "Your B2B sales team deserves better data. "
            "Get verified mid-market leads with decision-maker contacts — CRM-ready and fresh. "
            "✅ Decision-maker contacts\n✅ CRM-ready format\n✅ Florida companies 50-500 employees"
        ),
        "headline": "Mid-Market B2B Leads – FL",
        "description": "Decision-Maker Data. CRM-Ready.",
        "call_to_action": "Get Leads",
    },
    "enterprise": {
        "primary_text": (
            "Close enterprise deals faster with better data. "
            "Verified C-suite, VP and Director contacts at Florida's largest companies. Intent data available. "
            "✅ C-suite & VP contacts\n✅ Intent data available\n✅ Fortune 500 coverage"
        ),
        "headline": "Enterprise B2B Leads – FL",
        "description": "C-Suite Contacts. Intent Data Included.",
        "call_to_action": "Get Leads",
    },
}

# ---------------------------------------------------------------------------
# A/B variant copy for Meta ads
# ---------------------------------------------------------------------------
_META_AD_COPY_VARIANT_B: dict[str, dict] = {
    "hvac": {
        "primary_text": (
            "Your AC going out in Florida summer is a 911 situation. "
            "We're the HVAC company that picks up the phone and shows up the same day. "
            "✅ Same-day appointments\n✅ Transparent pricing\n✅ 1-year service guarantee"
        ),
        "headline": "Same-Day AC Repair – Florida",
        "description": "We Show Up. Honest Pricing. Guaranteed.",
        "call_to_action": "Book Now",
    },
    "roofing": {
        "primary_text": (
            "One bad storm can cost you $20,000 in roof damage. "
            "Get a free drone inspection now and know exactly where you stand before hurricane season hits. "
            "✅ Free drone inspection\n✅ Pre-storm documentation\n✅ Insurance claim support"
        ),
        "headline": "Free Drone Roof Inspection – FL",
        "description": "Pre-Storm Check. Insurance Support.",
        "call_to_action": "Schedule Now",
    },
    "solar": {
        "primary_text": (
            "The average FPL bill in Florida is $150+/month. "
            "Solar homeowners pay $0. Which side do you want to be on? Get your free quote now. "
            "✅ $0 monthly electric bill possible\n✅ 25-year warranty\n✅ Increase home value"
        ),
        "headline": "Stop Paying FPL – Go Solar FL",
        "description": "$0 Down. $0 Electric Bill. 25-Yr Warranty.",
        "call_to_action": "Get Free Quote",
    },
    "plumbing": {
        "primary_text": (
            "A leaking pipe doesn't fix itself — it gets more expensive. "
            "Our licensed Florida plumbers are on call 24/7 and will fix it right the first time. "
            "✅ 24/7 availability\n✅ Fixed-price quotes\n✅ 90-day workmanship guarantee"
        ),
        "headline": "Plumber On-Call 24/7 – Florida",
        "description": "Fixed Prices. 90-Day Guarantee.",
        "call_to_action": "Call Now",
    },
    "electrical": {
        "primary_text": (
            "An overloaded electrical panel is a house fire waiting to happen. "
            "Get a free safety inspection from our licensed Florida electricians today. "
            "✅ Free safety inspection\n✅ Panel upgrades from $800\n✅ Licensed & insured"
        ),
        "headline": "Free Electrical Safety Inspection",
        "description": "Panel Upgrades. Licensed FL Electricians.",
        "call_to_action": "Book Free Inspection",
    },
    "water_damage": {
        "primary_text": (
            "Mold starts growing within 24-48 hours of water damage. "
            "Every hour counts — call our 24/7 restoration team now for immediate response. "
            "✅ On-site in 1 hour or less\n✅ Mold prevention protocol\n✅ Insurance handled for you"
        ),
        "headline": "Water Damage – 1-Hour Response",
        "description": "On-Site Fast. Insurance Handled for You.",
        "call_to_action": "Call Now",
    },
    "windows": {
        "primary_text": (
            "Impact windows aren't just about hurricanes — they cut energy bills by 30% year-round. "
            "Get a free in-home estimate and see how much you'll save. "
            "✅ 30% energy savings\n✅ Hurricane protection\n✅ Noise reduction"
        ),
        "headline": "Save 30% on Energy – Impact Windows",
        "description": "Energy Savings + Hurricane Protection.",
        "call_to_action": "Get Free Estimate",
    },
    "pest_control": {
        "primary_text": (
            "Florida termites can eat through $3,000 of wood in a single year. "
            "Get a free inspection and termite bond today — before it's too late. "
            "✅ Free termite inspection\n✅ Termite bonds available\n✅ Licensed & certified"
        ),
        "headline": "Free Termite Inspection – FL",
        "description": "Termite Bonds. Licensed Pest Control.",
        "call_to_action": "Book Free Inspection",
    },
    "dscr_loan": {
        "primary_text": (
            "Most investors lose deals waiting 45+ days for a conventional lender. "
            "Our DSCR loans close in 21 days — no W2s, no tax returns, no drama. "
            "✅ 21-day close guarantee\n✅ $100K–$3M loan amounts\n✅ All FL property types"
        ),
        "headline": "DSCR Loans – 21-Day Close",
        "description": "No W2s. $100K–$3M. All Property Types.",
        "call_to_action": "Get Pre-Approved",
    },
    "hard_money": {
        "primary_text": (
            "The best fix-and-flip deals go under contract in hours. "
            "Our hard money lenders approve in 24 hours and close in 7 days. No excuses. "
            "✅ 24-hour approval\n✅ 7-day close\n✅ No minimum credit score"
        ),
        "headline": "Hard Money – 24hr Approval",
        "description": "7-Day Close. No Min Credit Score.",
        "call_to_action": "Apply Now",
    },
    "fix_and_flip": {
        "primary_text": (
            "We've funded over $50M in Florida fix-and-flip deals. "
            "90% of purchase + 100% of rehab. Draw schedules that actually work. "
            "✅ 90% purchase + 100% rehab\n✅ Flexible draw schedule\n✅ No W2s required"
        ),
        "headline": "Fix & Flip – 90%+100% Funding",
        "description": "Full Rehab Funded. Flexible Draws.",
        "call_to_action": "Get Funded",
    },
    "bridge_loan": {
        "primary_text": (
            "Don't let your dream property go to someone else because your current home hasn't sold. "
            "Bridge loans let you buy now and sell later — on your timeline. "
            "✅ Buy now, sell later\n✅ Close in 7 days\n✅ Flexible 6-24 month terms"
        ),
        "headline": "Bridge Loan – Buy Now Sell Later",
        "description": "Close in 7 Days. Flexible 6-24 Mo Terms.",
        "call_to_action": "Apply Now",
    },
    "commercial_re": {
        "primary_text": (
            "Florida's commercial real estate market is moving fast. "
            "Our CRE loans up to $20M close faster than banks with fewer headaches. "
            "✅ CRE loans to $20M\n✅ Competitive rates\n✅ SBA & conventional options"
        ),
        "headline": "CRE Loans to $20M – Close Fast",
        "description": "SBA & Conv Options. Competitive Rates.",
        "call_to_action": "Get Quote",
    },
    "wholesale_buyer": {
        "primary_text": (
            "Inherited a property? Going through a divorce? Facing foreclosure? "
            "We buy Florida homes for cash — any situation, any condition, fast closing. "
            "✅ Any situation accepted\n✅ Cash offer in 24 hours\n✅ 0% fees or commissions"
        ),
        "headline": "Cash for FL Homes – Any Situation",
        "description": "Any Situation. 0% Fees. Cash Offer 24hr.",
        "call_to_action": "Get Cash Offer",
    },
    "smb": {
        "primary_text": (
            "Most B2B lead lists are 60% outdated before you even open them. "
            "Ours are verified weekly — fresh Florida SMB contacts with owner info included. "
            "✅ Weekly verified data\n✅ Owner contact info included\n✅ CRM import ready"
        ),
        "headline": "Fresh SMB Leads – Verified Weekly",
        "description": "Owner Contacts. Weekly Verified. CRM Ready.",
        "call_to_action": "Get Leads",
    },
    "mid_market": {
        "primary_text": (
            "Your sales reps are wasting 40% of their time on bad data. "
            "Get decision-maker verified mid-market leads and watch your pipeline fill up fast. "
            "✅ Verified decision makers\n✅ 50-500 employee companies\n✅ Same-day delivery"
        ),
        "headline": "Mid-Market Leads – Decision Makers",
        "description": "Verified. 50-500 Employees. Same-Day.",
        "call_to_action": "Get Leads",
    },
    "enterprise": {
        "primary_text": (
            "Enterprise sales cycles are long enough without bad data. "
            "Get verified C-suite contacts and intent signals for Florida's largest companies. "
            "✅ C-suite verified contacts\n✅ Intent data signals\n✅ Same-day delivery"
        ),
        "headline": "Enterprise Leads – C-Suite Verified",
        "description": "Intent Data. C-Suite Contacts. Fast.",
        "call_to_action": "Get Leads",
    },
}


class AdCopyGenerator:
    """
    Generates production-ready Google RSA and Meta ad copy for all supported
    sub-verticals across home services, real estate, and B2B.
    """

    # Sub-verticals grouped by vertical
    VERTICALS: dict[str, list[str]] = {
        "home_services": [
            "hvac", "roofing", "solar", "plumbing", "electrical",
            "water_damage", "windows", "pest_control",
        ],
        "real_estate": [
            "dscr_loan", "hard_money", "fix_and_flip", "bridge_loan",
            "commercial_re", "wholesale_buyer",
        ],
        "b2b": ["smb", "mid_market", "enterprise"],
    }

    def generate_google_rsa(
        self,
        vertical: str,
        sub_vertical: str,
        location: str,
    ) -> dict:
        """
        Generate a Google Responsive Search Ad package for the given sub-vertical.

        Args:
            vertical: Top-level vertical (e.g. ``"home_services"``).
            sub_vertical: Sub-vertical key (e.g. ``"hvac"``).
            location: Target Florida metro or city (e.g. ``"Tampa Bay"``).

        Returns:
            Dict with keys: ``campaign_name``, ``ad_group``, ``headlines``
            (15 items, each ≤ 30 chars), ``descriptions`` (4 items),
            ``final_url``, ``display_path``, ``keywords``,
            ``negative_keywords``, ``bid_strategy``, ``target_cpa``.
        """
        copy = _GOOGLE_RSA_COPY.get(sub_vertical)
        if copy is None:
            raise ValueError(f"Unknown sub_vertical: {sub_vertical!r}")

        headlines = copy["headlines"]
        for h in headlines:
            assert len(h) <= 30, (
                f"Headline exceeds 30 chars ({len(h)}): {h!r}"
            )

        bid = TargetingConfig.BID_RECOMMENDATIONS.get(sub_vertical, {})
        category = _VERTICAL_CATEGORY.get(sub_vertical, vertical)
        neg_keywords = TargetingConfig.NEGATIVE_KEYWORDS.get(category, [])
        keywords = TargetingConfig.KEYWORD_THEMES.get(sub_vertical, [])

        return {
            "campaign_name": f"{sub_vertical.replace('_', ' ').title()} – {location} – Google Search",
            "ad_group": f"{sub_vertical.replace('_', ' ').title()} – {location}",
            "headlines": headlines,
            "descriptions": copy["descriptions"],
            "final_url": copy["final_url"],
            "display_path": copy["display_path"],
            "keywords": keywords,
            "negative_keywords": neg_keywords,
            "bid_strategy": "Target CPA",
            "target_cpa": bid.get("target_cpa", 200.0),
        }

    def generate_meta_ad(
        self,
        vertical: str,
        sub_vertical: str,
        location: str,
        audience_tier: str = "broad",
    ) -> dict:
        """
        Generate a Meta (Facebook / Instagram) ad package for the given sub-vertical.

        Args:
            vertical: Top-level vertical (e.g. ``"real_estate"``).
            sub_vertical: Sub-vertical key (e.g. ``"dscr_loan"``).
            location: Target Florida metro (e.g. ``"Miami"``).
            audience_tier: Audience breadth — ``"broad"``, ``"retargeting"``,
                or ``"lookalike"``.

        Returns:
            Dict with keys: ``campaign_name``, ``ad_set_name``,
            ``primary_text``, ``headline``, ``description``,
            ``call_to_action``, ``audience``, ``placements``,
            ``optimization_goal``, ``bid_strategy``.
        """
        copy = _META_AD_COPY.get(sub_vertical)
        if copy is None:
            raise ValueError(f"Unknown sub_vertical: {sub_vertical!r}")

        category = _VERTICAL_CATEGORY.get(sub_vertical, vertical)
        audience = TargetingConfig.AUDIENCE_SEGMENTS.get(category, {})

        return {
            "campaign_name": f"{sub_vertical.replace('_', ' ').title()} – {location} – Meta",
            "ad_set_name": f"{sub_vertical.replace('_', ' ').title()} – {audience_tier.title()} – {location}",
            "primary_text": copy["primary_text"],
            "headline": copy["headline"],
            "description": copy["description"],
            "call_to_action": copy["call_to_action"],
            "audience": audience,
            "placements": ["Facebook Feed", "Instagram Feed", "Instagram Stories", "Audience Network"],
            "optimization_goal": "LEAD_GENERATION",
            "bid_strategy": "LOWEST_COST",
        }

    def generate_meta_ad_variant_b(
        self,
        vertical: str,
        sub_vertical: str,
        location: str,
    ) -> dict:
        """
        Generate an A/B variant Meta ad for split testing.

        Args:
            vertical: Top-level vertical.
            sub_vertical: Sub-vertical key.
            location: Target Florida metro.

        Returns:
            Meta ad dict using variant B copy.
        """
        copy = _META_AD_COPY_VARIANT_B.get(sub_vertical)
        if copy is None:
            # Fall back to primary copy if no variant exists
            return self.generate_meta_ad(vertical, sub_vertical, location, "broad")

        category = _VERTICAL_CATEGORY.get(sub_vertical, vertical)
        audience = TargetingConfig.AUDIENCE_SEGMENTS.get(category, {})

        return {
            "campaign_name": f"{sub_vertical.replace('_', ' ').title()} – {location} – Meta [Variant B]",
            "ad_set_name": f"{sub_vertical.replace('_', ' ').title()} – Variant B – {location}",
            "primary_text": copy["primary_text"],
            "headline": copy["headline"],
            "description": copy["description"],
            "call_to_action": copy["call_to_action"],
            "audience": audience,
            "placements": ["Facebook Feed", "Instagram Feed", "Instagram Stories", "Audience Network"],
            "optimization_goal": "LEAD_GENERATION",
            "bid_strategy": "LOWEST_COST",
        }
