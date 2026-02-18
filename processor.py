"""
Data processing functions for Balance Sheet Buddy.
Handles parsing, cleaning, and formatting of Trial Balance and GL dump files.
"""

import pandas as pd
import re
from typing import Optional, Dict, List, Tuple
import io


def parse_trial_balance(file) -> pd.DataFrame:
    """
    Parse Trial Balance from uploaded file (Excel or CSV).

    Expected columns: Account (number + name), Debit, Credit
    Returns cleaned DataFrame with standardized columns.
    Handles files with title rows by automatically finding the header row.
    """
    try:
        # First, read the file without header to find where the actual headers are
        if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            # Read first 20 rows to find headers
            df_raw = pd.read_excel(file, header=None, nrows=20)

            # Find the row that contains 'Account', 'Debit', 'Credit'
            header_row = None
            for idx, row in df_raw.iterrows():
                row_str = ' '.join([str(x).lower() for x in row if pd.notna(x)])
                if 'account' in row_str and 'debit' in row_str and 'credit' in row_str:
                    header_row = idx
                    break

            if header_row is None:
                raise ValueError("Could not find header row with Account, Debit, Credit columns")

            # Now read the file with the correct header row
            df = pd.read_excel(file, header=header_row)
        else:
            # CSV - read as text to find header row, then parse properly
            file.seek(0)
            lines = file.read().decode('utf-8', errors='ignore').split('\n')

            header_row = None
            for idx, line in enumerate(lines[:20]):  # Check first 20 lines
                line_lower = line.lower()
                if 'account' in line_lower and 'debit' in line_lower and 'credit' in line_lower:
                    header_row = idx
                    break

            if header_row is None:
                raise ValueError("Could not find header row with Account, Debit, Credit columns")

            # Read CSV starting from header row
            file.seek(0)
            df = pd.read_csv(file, skiprows=header_row)

        # Standardize column names (case-insensitive matching)
        df.columns = df.columns.str.strip()

        # Find account, debit, credit columns (flexible matching)
        account_col = None
        debit_col = None
        credit_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'account' in col_lower and account_col is None:
                account_col = col
            elif 'debit' in col_lower and debit_col is None:
                debit_col = col
            elif 'credit' in col_lower and credit_col is None:
                credit_col = col

        if not all([account_col, debit_col, credit_col]):
            raise ValueError(f"Could not find required columns. Found columns: {list(df.columns)}")

        # Helper function to clean and convert currency values
        def clean_currency(value):
            """Remove currency symbols, commas, and convert to float."""
            if pd.isna(value) or value == '':
                return 0.0
            # Convert to string and remove currency symbols (€, $, £, etc.) and commas
            value_str = str(value).replace('€', '').replace('$', '').replace('£', '').replace(',', '').strip()
            try:
                return float(value_str) if value_str else 0.0
            except ValueError:
                return 0.0

        # Create standardized DataFrame with cleaned currency values
        result = pd.DataFrame({
            'Account': df[account_col],
            'Debit': df[debit_col].apply(clean_currency),
            'Credit': df[credit_col].apply(clean_currency)
        })

        return result

    except Exception as e:
        raise Exception(f"Error parsing Trial Balance: {str(e)}")


def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """
    Remove blank rows and total/subtotal rows from Trial Balance.
    Per framework: Ignore aggregation rows and blank rows.
    """
    # Remove rows where Account is null or empty
    df = df[df['Account'].notna()]
    df = df[df['Account'].astype(str).str.strip() != '']

    # Remove ALL rows that start with "Total" or "Subtotal" (catches subtotal rows like "Total - 11500")
    # This catches: "Total", "Total - Account Name", "Subtotal", etc.
    total_start_pattern = re.compile(r'^\s*total[\s\-]', re.IGNORECASE)
    df = df[~df['Account'].astype(str).str.contains(total_start_pattern, na=False)]

    # Remove standalone total rows
    total_exact_pattern = re.compile(r'^\s*(total|subtotal|sub-total|grand total|sum)\s*$', re.IGNORECASE)
    df = df[~df['Account'].astype(str).str.match(total_exact_pattern)]

    # Remove rows where both debit and credit are 0 (likely blank)
    df = df[~((df['Debit'] == 0) & (df['Credit'] == 0))]

    # Also remove "Opening Balance" rows as they're often aggregates
    df = df[~df['Account'].astype(str).str.contains(r'^\s*opening\s+balance', case=False, na=False)]

    return df.reset_index(drop=True)


def load_category_mapping(file) -> pd.DataFrame:
    """
    Load category mapping file (Excel).
    Expected columns: Account (or Account Number), Category, Subcategory
    """
    try:
        df = pd.read_excel(file)
        df.columns = df.columns.str.strip()

        # Find columns flexibly
        account_col = None
        category_col = None
        subcategory_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'account' in col_lower and account_col is None:
                account_col = col
            elif col_lower == 'category' and category_col is None:
                category_col = col
            elif 'subcategory' in col_lower and subcategory_col is None:
                subcategory_col = col

        if not all([account_col, category_col, subcategory_col]):
            raise ValueError(f"Mapping file must have Account, Category, and Subcategory columns. Found: {list(df.columns)}")

        result = pd.DataFrame({
            'Account_Key': df[account_col].astype(str).str.strip().str.lower(),
            'Category': df[category_col],
            'Subcategory': df[subcategory_col]
        })

        return result

    except Exception as e:
        raise Exception(f"Error loading category mapping: {str(e)}")


def merge_with_mapping(tb_df: pd.DataFrame, mapping_df: pd.DataFrame) -> pd.DataFrame:
    """
    Merge Trial Balance with category mapping.
    Uses fuzzy matching on account name/number.
    """
    # Create matching key from TB account (lowercase, stripped)
    tb_df['Account_Key'] = tb_df['Account'].astype(str).str.strip().str.lower()

    # Merge on Account_Key
    merged = tb_df.merge(
        mapping_df[['Account_Key', 'Category', 'Subcategory']],
        on='Account_Key',
        how='left'
    )

    # For unmatched accounts, try partial matching on account number at start
    unmatched = merged['Category'].isna()
    if unmatched.any():
        for idx in merged[unmatched].index:
            account_str = str(merged.loc[idx, 'Account'])
            # Extract account number (usually at start)
            match = re.match(r'^(\d+)', account_str)
            if match:
                account_num = match.group(1)
                # Try to find mapping by account number prefix
                mapping_match = mapping_df[mapping_df['Account_Key'].str.startswith(account_num)]
                if not mapping_match.empty:
                    merged.loc[idx, 'Category'] = mapping_match.iloc[0]['Category']
                    merged.loc[idx, 'Subcategory'] = mapping_match.iloc[0]['Subcategory']

    # Fill remaining unmapped with "Unmapped"
    merged['Category'] = merged['Category'].fillna('Unmapped')
    merged['Subcategory'] = merged['Subcategory'].fillna('Unknown')

    # Drop the matching key
    merged = merged.drop('Account_Key', axis=1)

    return merged


def format_for_claude(df: pd.DataFrame) -> str:
    """
    Convert Trial Balance DataFrame to text format for Claude analysis.
    Creates a clear, structured text representation.
    """
    lines = ["TRIAL BALANCE DATA", "=" * 80, ""]

    for idx, row in df.iterrows():
        account = row['Account']
        debit = row['Debit']
        credit = row['Credit']
        category = row.get('Category', 'N/A')
        subcategory = row.get('Subcategory', 'N/A')

        balance_type = "Dr" if debit > 0 else "Cr" if credit > 0 else "Zero"
        amount = debit if debit > 0 else credit

        line = f"Account: {account} | Type: {balance_type} | Amount: {amount:,.2f}"
        if category != 'N/A':
            line += f" | Category: {category} | Subcategory: {subcategory}"

        lines.append(line)

    lines.append("")
    lines.append(f"Total Accounts: {len(df)}")
    lines.append(f"Total Debits: {df['Debit'].sum():,.2f}")
    lines.append(f"Total Credits: {df['Credit'].sum():,.2f}")

    return "\n".join(lines)


def parse_gl_dump(file) -> pd.DataFrame:
    """
    Parse GL dump file (Excel or CSV).
    Expected columns: Account, Date, Description/Memo, Debit, Credit
    Returns DataFrame with transaction details.
    """
    try:
        if file.name.endswith('.xlsx') or file.name.endswith('.xls'):
            df = pd.read_excel(file)
        else:
            df = pd.read_csv(file)

        df.columns = df.columns.str.strip()

        # Find required columns flexibly
        account_col = None
        date_col = None
        desc_col = None
        debit_col = None
        credit_col = None

        for col in df.columns:
            col_lower = col.lower()
            if 'account' in col_lower and account_col is None:
                account_col = col
            elif 'date' in col_lower and date_col is None:
                date_col = col
            elif any(x in col_lower for x in ['description', 'memo', 'narration']) and desc_col is None:
                desc_col = col
            elif 'debit' in col_lower and debit_col is None:
                debit_col = col
            elif 'credit' in col_lower and credit_col is None:
                credit_col = col

        required = {'Account': account_col, 'Date': date_col, 'Debit': debit_col, 'Credit': credit_col}
        missing = [k for k, v in required.items() if v is None]
        if missing:
            raise ValueError(f"GL dump missing required columns: {missing}")

        result = pd.DataFrame({
            'Account': df[account_col],
            'Date': pd.to_datetime(df[date_col], errors='coerce'),
            'Description': df[desc_col] if desc_col else '',
            'Debit': pd.to_numeric(df[debit_col], errors='coerce').fillna(0),
            'Credit': pd.to_numeric(df[credit_col], errors='coerce').fillna(0)
        })

        return result

    except Exception as e:
        raise Exception(f"Error parsing GL dump: {str(e)}")


def format_gl_for_claude(gl_df: pd.DataFrame, account_name: str = None) -> str:
    """
    Format GL dump data for Claude analysis.
    Optionally filter by specific account.
    """
    if account_name:
        gl_df = gl_df[gl_df['Account'].astype(str).str.contains(account_name, case=False, na=False)]

    if gl_df.empty:
        return f"No GL transactions found{' for ' + account_name if account_name else ''}."

    lines = [f"GENERAL LEDGER TRANSACTIONS{' - ' + account_name if account_name else ''}", "=" * 80, ""]

    # Sort by date
    gl_df = gl_df.sort_values('Date')

    for idx, row in gl_df.iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'Unknown'
        account = row['Account']
        desc = row['Description']
        debit = row['Debit']
        credit = row['Credit']
        amount = debit if debit > 0 else -credit

        line = f"{date_str} | {account} | {desc} | Amount: {amount:,.2f}"
        lines.append(line)

    lines.append("")
    lines.append(f"Total Transactions: {len(gl_df)}")
    lines.append(f"Total Debits: {gl_df['Debit'].sum():,.2f}")
    lines.append(f"Total Credits: {gl_df['Credit'].sum():,.2f}")

    return "\n".join(lines)


def extract_account_number(account_str: str) -> Optional[str]:
    """Extract account number from account string (usually at the beginning)."""
    match = re.match(r'^(\d+)', str(account_str).strip())
    return match.group(1) if match else None


def get_balance_type(debit: float, credit: float) -> str:
    """Determine if balance is Debit, Credit, or Zero."""
    if debit > 0 and credit == 0:
        return "Debit"
    elif credit > 0 and debit == 0:
        return "Credit"
    elif debit == 0 and credit == 0:
        return "Zero"
    else:
        return "Mixed"  # Both debit and credit (unusual)
