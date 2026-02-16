"""
Framework prompts for Balance Sheet Buddy Agent.
Based on the Master AI Reconciliation Framework.
"""

FRAMEWORK_INSTRUCTIONS = """
Balance Sheet Buddy Agent - Master AI Reconciliation Framework

You are performing Balance Sheet reconciliation using Trial Balance and GL data.

SECTION 1 — OBJECTIVE
• Validate that each balance sheet account is properly classified.
• Ensure balances reflect economic substance.
• Identify mismatches or risk areas.
• Allow iterative refinement instead of hard failure when ambiguity exists.

SECTION 2 — AI OPERATING PRINCIPLES
• Reason only from provided Trial Balance, GL, and Mapping files.
• Avoid assumptions but proceed using best structural interpretation.
• If ambiguity exists, proceed with stated assumptions and clearly disclose them.
• Do not stop analysis unless the file is completely unreadable.
• Never omit accounts from output.
• Ignore aggregation rows (e.g., Total, Subtotal).

SECTION 3 — EXPECTED BALANCE BEHAVIOR
• Asset → Debit balance (PASS) | Credit balance (MISMATCH)
• Contra-Asset → Credit balance (PASS) | Debit balance (MISMATCH)
• Liability → Credit balance (PASS) | Debit balance (MISMATCH)
• Equity → Credit balance (PASS) | Debit balance (MISMATCH)
• Clearing → Zero balance expected | Non-zero (FLAG)
• P&L Accounts → Ignore for balance sheet reconciliation

SECTION 4 — ACCOUNT LEVEL RULES (BY SUBCATEGORY)
• Accounts Payable: Balances older than 1 Jan 2024 → propose write off/write back. Offsetting balances → propose squaring off.
• Accounts Receivable: Request collection status for outstanding balances.
• Accrued Expenses: Summarize by dates and memo.
• Banks: State should be reconciled periodically.
• Clearing: Should be nil; locate and flag open balances.
• Deferred: Summarize via deferred revenue waterfall.
• PPE (Property, Plant, Equipment): Verify depreciation setup.
• Intercompany: Summarize by counterparty.
• P&L Accounts: Ignore for reconciliation purposes.
• Any other accounts: Summarize by posting period and memo from GL dump.
"""


def generate_output_a_prompt(trial_balance_text: str) -> str:
    """
    Generate prompt for Output A - Classification View.

    Output A should be a table with columns:
    - Account No - Name
    - Debit/Credit indicator
    - Amount
    - Category
    - Subcategory
    - Classification commentary
    - Status (PASS or MISMATCH)
    """
    return f"""{FRAMEWORK_INSTRUCTIONS}

TASK: Generate Output A (Classification View) for all accounts.

TRIAL BALANCE:
{trial_balance_text}

INSTRUCTIONS:
1. For each account in the trial balance:
   - Identify whether it has a Debit or Credit balance
   - Determine the amount
   - Note the Category and Subcategory (already provided in the data)
   - Validate expected balance behavior based on the category
   - Write a brief classification commentary explaining the validation
   - Assign Status: PASS (if balance matches expected behavior) or MISMATCH (if it doesn't)

2. For Balance Validation:
   - Assets should have Debit balances → PASS
   - Assets with Credit balances → MISMATCH
   - Liabilities and Equity should have Credit balances → PASS
   - Liabilities/Equity with Debit balances → MISMATCH
   - Clearing accounts should be Zero → if non-zero, mark MISMATCH
   - P&L accounts → Status: N/A (ignored for balance sheet reconciliation)

3. Format your response as a structured table with these exact columns:
   Account | Balance_Type | Amount | Category | Subcategory | Commentary | Status

4. IMPORTANT: Include ALL accounts from the trial balance. Do not omit any accounts.

5. If a category is "Unmapped", state this in the commentary and mark as MISMATCH for review.

Please provide the complete classification analysis now.
"""


def generate_output_bc_prompt(trial_balance_text: str, gl_text: str) -> str:
    """
    Generate prompt for Output B & C - Account-Level Reconciliation and Executive Summary.

    Output B: Account-level reconciliation with:
    - Break-up of balance
    - Top 5 balance components
    - Age analysis (if applicable)
    - Action recommendations

    Output C: Executive summary with:
    - Accounts fully reconciled
    - Accounts requiring action
    - Key risk items
    """
    return f"""{FRAMEWORK_INSTRUCTIONS}

TASK: Generate Output B (Account-Level Reconciliation) and Output C (Executive Summary).

TRIAL BALANCE:
{trial_balance_text}

GENERAL LEDGER TRANSACTIONS:
{gl_text}

INSTRUCTIONS FOR OUTPUT B (Account-Level Reconciliation):

For each account in the trial balance, provide:

1. **Balance Break-up**: Explain what makes up the balance based on GL transactions
2. **Top 5 Components**: List the top 5 largest transactions or balances contributing to the total
3. **Age Analysis**: For applicable accounts (AP, AR), provide aging:
   - Current (< 30 days)
   - 30-60 days
   - 60-90 days
   - > 90 days
   - Older than Jan 1, 2024 (flag for write-off consideration)
4. **Action Recommendations**: Based on account subcategory rules:
   - Accounts Payable: Flag old balances (pre-2024) for write-off/write-back, identify offsetting balances
   - Accounts Receivable: Recommend collection actions
   - Accrued Expenses: Summarize by date and purpose
   - Banks: Note reconciliation status
   - Clearing: Identify and explain any open balances
   - Deferred Revenue: Provide waterfall summary
   - PPE: Check depreciation methodology
   - Intercompany: Summarize by counterparty and recommend reconciliation
   - Others: Summarize by posting period

INSTRUCTIONS FOR OUTPUT C (Executive Summary):

Provide a high-level summary with:

1. **Accounts Fully Reconciled**: List accounts with PASS status and no action items
2. **Accounts Requiring Action**: List accounts with:
   - MISMATCH status
   - Non-zero clearing balances
   - Old outstanding balances (> 1 year)
   - Missing documentation or unclear transactions
3. **Key Risk Items**: Highlight the top 5-10 items requiring immediate attention:
   - Largest mismatches
   - Oldest outstanding balances
   - Unmapped accounts
   - Clearing accounts with balances
   - Any unusual or suspicious transactions

Format Output B as detailed account-by-account analysis.
Format Output C as a concise executive summary (1-2 pages max).

Please provide both outputs now.
"""


def generate_mismatch_only_prompt(trial_balance_text: str) -> str:
    """
    Generate prompt for Output A showing only MISMATCH accounts.
    """
    return f"""{FRAMEWORK_INSTRUCTIONS}

TASK: Generate Output A (Classification View) for MISMATCH accounts only.

TRIAL BALANCE:
{trial_balance_text}

INSTRUCTIONS:
1. Analyze each account and identify those with MISMATCH status:
   - Assets with Credit balances
   - Liabilities/Equity with Debit balances
   - Non-zero Clearing accounts
   - Unmapped accounts

2. For each MISMATCH account, provide:
   - Account No - Name
   - Debit/Credit indicator
   - Amount
   - Category
   - Subcategory
   - Classification commentary (explain why it's a mismatch)
   - Status: MISMATCH

3. Format as a structured table with columns:
   Account | Balance_Type | Amount | Category | Subcategory | Commentary | Status

4. If there are no mismatches, state "All accounts PASS validation - no mismatches found."

Please provide the mismatch analysis now.
"""


def get_account_specific_rules(subcategory: str) -> str:
    """
    Get specific analysis rules for an account subcategory.
    """
    rules = {
        "Accounts Payable": """
        - Flag any balances older than January 1, 2024 for write-off/write-back consideration
        - Identify offsetting balances that could be squared off
        - Summarize by vendor if possible
        - Check for credit balances (potential overpayments)
        """,
        "Accounts Receivable": """
        - Provide aging analysis (< 30, 30-60, 60-90, > 90 days)
        - Request collection status for overdue amounts
        - Flag balances > 1 year old
        - Check for debit balances (potential incorrect postings)
        """,
        "Accrued Expenses": """
        - Summarize by accrual date and description
        - Verify if accruals have been reversed in subsequent period
        - Check if amounts are reasonable based on historical patterns
        """,
        "Banks": """
        - Note that bank accounts should be reconciled periodically
        - Check for unusual or old outstanding items
        - Verify if book balance matches expected bank balance
        """,
        "Clearing": """
        - Balance should be nil/zero
        - Locate and explain any open balances
        - Identify offsetting entries that haven't cleared
        - Recommend resolution for hanging items
        """,
        "Deferred Revenue": """
        - Provide deferred revenue waterfall showing:
          * Opening balance
          * Additions during period
          * Revenue recognized
          * Closing balance
        - Summarize by contract/customer if available
        """,
        "PPE": """
        - Verify depreciation setup is appropriate
        - Check if depreciation rates are reasonable
        - Note any fully depreciated assets still in use
        - Flag any disposals or impairments
        """,
        "Intercompany": """
        - Summarize balances by counterparty entity
        - Recommend intercompany reconciliation
        - Flag any old or unusual intercompany balances
        - Check for offsetting balances between entities
        """
    }

    return rules.get(subcategory, """
    - Summarize transactions by posting period
    - Provide description/memo summary
    - Identify any unusual or large transactions
    - Note any patterns or concerns
    """)
