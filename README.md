# Balance Sheet Buddy

AI-powered balance sheet reconciliation tool powered by Claude AI (Sonnet 4.5).

## What It Does

Balance Sheet Buddy automates the tedious process of balance sheet reconciliation by:
- Validating that accounts are properly classified
- Ensuring balances reflect economic substance (Assets=Debit, Liabilities=Credit, etc.)
- Identifying mismatches and risk areas
- Providing detailed account-level reconciliation
- Generating executive summaries for management

## Features

✅ **Smart Classification** - Automatically validates balance types against expected behavior
✅ **Flexible Input** - Supports Excel and CSV files
✅ **Category Mapping** - Maps accounts to categories and subcategories
✅ **Detailed Analysis** - Provides aging analysis, top components, and recommendations
✅ **Multiple Outputs** - Excel classification view, reconciliation reports, executive summaries
✅ **Account-Specific Rules** - Applies tailored rules for AP, AR, Clearing, PPE, etc.

## How to Use

### 1. Input Files

**Trial Balance (Required):**
- Excel (.xlsx) or CSV format
- Must contain columns: Account, Debit, Credit
- Account can be "Account Number - Account Name"

**Category Mapping (Optional):**
- Excel format
- Columns: Account, Category, Subcategory
- Maps accounts to categories for better classification
- Default mapping file included: `Category mapping Balance Sheet.xlsx`

**GL Dump (Optional):**
- Excel or CSV format
- Columns: Account, Date, Description, Debit, Credit
- Required for detailed analysis (Outputs B & C)

### 2. Analysis Options

**Classification Only (Output A):**
- Fast validation of all accounts
- Shows PASS/MISMATCH status
- Download as Excel file

**Full Analysis (Outputs A, B, C):**
- Complete reconciliation with GL data
- Detailed account breakdowns
- Executive summary with key risks

### 3. Outputs

**Output A - Classification View (Excel):**
- Account | Balance Type | Amount | Category | Subcategory | Commentary | Status
- Color-coded: Green=PASS, Red=MISMATCH

**Output B - Account-Level Reconciliation (Text/HTML):**
- Balance break-up for each account
- Top 5 components
- Aging analysis (for AP/AR)
- Action recommendations

**Output C - Executive Summary (Text/HTML):**
- Accounts fully reconciled
- Accounts requiring action
- Key risk items

## Expected Balance Behavior

| Account Type | Expected Balance | Status if Correct |
|--------------|------------------|-------------------|
| Asset | Debit | ✅ PASS |
| Liability | Credit | ✅ PASS |
| Equity | Credit | ✅ PASS |
| Clearing | Zero | ✅ PASS |
| Contra-Asset | Credit | ✅ PASS |
| P&L | Ignored | N/A |

## Account-Specific Rules

- **Accounts Payable:** Flags balances older than Jan 1, 2024 for write-off consideration
- **Accounts Receivable:** Provides aging analysis and collection recommendations
- **Accrued Expenses:** Summarizes by date and description
- **Banks:** Notes reconciliation requirements
- **Clearing Accounts:** Identifies non-zero balances that should be investigated
- **Deferred Revenue:** Provides waterfall summary
- **PPE:** Verifies depreciation setup
- **Intercompany:** Summarizes by counterparty

## Local Development

### Prerequisites

- Python 3.8 or higher
- Claude API key (get one at [console.anthropic.com](https://console.anthropic.com))

### Installation

1. Clone or download this repository
2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Create `.streamlit/secrets.toml` with your API key:
```toml
ANTHROPIC_API_KEY = "sk-ant-your-api-key-here"
```

4. Run the app:
```bash
streamlit run app.py
```

5. Open your browser to `http://localhost:8501`

## Deployment to Streamlit Cloud (Free)

### Step 1: Create GitHub Repository

1. Go to [github.com](https://github.com) and create a new repository
2. Upload all files from the `balancesheet` folder:
   - `app.py`
   - `processor.py`
   - `prompts.py`
   - `outputs.py`
   - `requirements.txt`
   - `.streamlit/config.toml`
   - `Category mapping Balance Sheet.xlsx` (optional default mapping)
   - `README.md`

### Step 2: Get Claude API Key

1. Go to [console.anthropic.com](https://console.anthropic.com)
2. Sign up or log in
3. Navigate to "API Keys"
4. Create a new API key
5. Copy the key (starts with `sk-ant-...`)
6. **Set spending limits** to control costs (recommended: $10-50/month)

### Step 3: Deploy to Streamlit Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign up with GitHub (free, no credit card required)
3. Click "New app"
4. Select your GitHub repository
5. Set:
   - **Main file path:** `app.py`
   - **Python version:** 3.9 or higher
6. Click "Advanced settings"
7. In "Secrets" section, add:
```toml
ANTHROPIC_API_KEY = "sk-ant-your-api-key-here"
```
8. Click "Deploy"

### Step 4: Share Your App

After deployment (takes 2-3 minutes):
- You'll get a public URL like: `https://your-app-name.streamlit.app`
- Share this URL with anyone who needs to use the tool
- They can upload files and run analyses without any setup

## Cost Estimation

**Infrastructure Costs:** $0 (Streamlit Cloud free tier)

**AI Usage Costs (Claude API):**
- Classification Only: ~$0.25-$0.75 per analysis
- Full Analysis with GL: ~$0.75-$2.00 per analysis
- Depends on file size and number of accounts

**Free Tier Limits:**
- Streamlit Cloud: 1 free app, suitable for ~100 users/month
- Claude API: Pay-as-you-go, no minimum commitment

**Cost Control Tips:**
1. Set API spending limits in Anthropic Console
2. Monitor usage in Anthropic dashboard
3. Start with classification-only analyses
4. Use full analysis only when detailed reconciliation is needed

## Troubleshooting

### "Could not find required columns"
- Ensure your Trial Balance has columns named "Account", "Debit", and "Credit"
- Column names are case-insensitive but must contain these keywords

### "ANTHROPIC_API_KEY not configured"
- For local: Create `.streamlit/secrets.toml` with your API key
- For cloud: Add API key in Streamlit Cloud app settings → Secrets

### "Error calling Claude API"
- Check that your API key is valid
- Verify you have available credit in your Anthropic account
- Check your internet connection

### "No GL data could be parsed"
- Ensure GL dump has columns: Account, Date, Debit, Credit
- Check file format (Excel or CSV)
- Verify file is not corrupted

### High API costs
- Set spending limits in Anthropic Console
- Start with smaller test files
- Use "Classification Only" mode when possible
- Consider using "Show mismatches only" option

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the framework document: `Balance Sheet Buddy Agent — End-to-End Design Plan.docx`
3. Check Streamlit documentation: [docs.streamlit.io](https://docs.streamlit.io)
4. Check Anthropic documentation: [docs.anthropic.com](https://docs.anthropic.com)

## Technical Architecture

**Frontend:** Streamlit (Python web framework)
**AI Engine:** Claude API (Sonnet 4.5 model)
**Data Processing:** Pandas + OpenPyXL
**Hosting:** Streamlit Cloud (free tier)

**File Structure:**
```
balancesheet/
├── app.py                      # Main Streamlit application
├── processor.py                # Data parsing and cleaning
├── prompts.py                  # Claude API prompt templates
├── outputs.py                  # Excel and report generation
├── requirements.txt            # Python dependencies
├── .streamlit/
│   └── config.toml            # Streamlit configuration
├── Category mapping Balance Sheet.xlsx  # Default mapping
└── README.md                   # This file
```

## License

This project is provided as-is for balance sheet reconciliation purposes.

## Credits

- Built with [Streamlit](https://streamlit.io)
- Powered by [Claude AI](https://anthropic.com) (Sonnet 4.5)
- Based on the Balance Sheet Buddy Agent Master Framework

---

**Version:** 1.0.0
**Last Updated:** February 2026
