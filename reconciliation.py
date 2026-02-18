"""
Account Reconciliation Module
Handles interactive account-by-account reconciliation with Claude.
"""

import streamlit as st
import pandas as pd
import json
import os
from datetime import datetime
from typing import Dict, Optional
import io
import session_manager


def load_reconciliation_state(session_id: str) -> Dict:
    """
    Load reconciliation state from file.
    Returns dict with account reconciliation data.
    """
    state_file = f".reconciliation_state_{session_id}.json"
    if os.path.exists(state_file):
        with open(state_file, 'r') as f:
            return json.load(f)
    return {}


def save_reconciliation_state(session_id: str, state: Dict):
    """Save reconciliation state to file."""
    state_file = f".reconciliation_state_{session_id}.json"
    with open(state_file, 'w') as f:
        json.dump(state, f, indent=2)


def get_session_id(tb_merged: pd.DataFrame) -> str:
    """Generate a unique session ID based on TB data."""
    # Use hash of account list as session ID
    accounts = sorted(tb_merged['Account'].astype(str).tolist())
    return str(hash(''.join(accounts)))[:10]


def show_reconciliation_tab(classification_df: pd.DataFrame, tb_merged: pd.DataFrame, api_key: str):
    """
    Display the Account Reconciliation tab.
    Shows account list with reconciliation status and interactive interface.
    """
    st.subheader("📋 Account Reconciliation")
    st.markdown("Work through each account systematically to complete reconciliation.")

    # NetSuite GL Dump Instructions
    with st.expander("📊 How to Get GL Dump from NetSuite", expanded=False):
        st.markdown("""
        ### Step-by-Step Instructions:

        1. **Open NetSuite GL Dump Report**
           - Click here: [NetSuite GL Dump Report](https://4914352.app.netsuite.com/app/reporting/reportrunner.nl?cr=4386&reload=t&whence=)
           - Or navigate to: **Reports → GL Dump Details - All Accounts**

        2. **Set Filters** (at bottom of report):
           - **PERIOD**: Select period (e.g., Jan 2015 to Feb 2026)
           - **SUBSIDIARY CONTEXT**: Select your subsidiary (e.g., Aurea Software FZ-LLC Dubai)
           - **ACCOUNT**: Enter the specific account number you want to reconcile
           - Click **MORE → Find...** to add additional filters if needed

        3. **Run Report**
           - Click **Run Report** or wait for report to load
           - Report will show all transactions for the selected account

        4. **Export to Excel/CSV**
           - Click **Export** button (usually at top right)
           - Select **Excel** or **CSV** format
           - Save the file

        5. **Upload Here**
           - Return to this app
           - Click **Reconcile** button for the account
           - Upload the exported Excel/CSV file
           - Complete the reconciliation process

        **Note:** You need to export GL dump separately for each account you want to reconcile.
        """)

    st.markdown("---")

    # Get or create session ID
    session_id = get_session_id(tb_merged)

    # Initialize reconciliation state in session_state if not exists
    if 'reconciliation_state' not in st.session_state:
        st.session_state.reconciliation_state = load_reconciliation_state(session_id)

    # Create reconciliation tracking DataFrame
    recon_df = classification_df.copy()

    # Add Reconciled column
    recon_df['Reconciled'] = recon_df['Account'].apply(
        lambda acc: st.session_state.reconciliation_state.get(str(acc), {}).get('reconciled', False)
    )

    # Summary statistics (exclude P&L and "PL - Ignore" accounts from reconciliation tracking)
    accounts_needing_recon = recon_df[
        (recon_df['Subcategory'] != 'PL') &
        (recon_df['Category'] != 'PL - Ignore')
    ]
    total_accounts = len(accounts_needing_recon)
    reconciled_count = accounts_needing_recon['Reconciled'].sum()
    progress_pct = (reconciled_count / total_accounts * 100) if total_accounts > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Accounts", total_accounts)
    with col2:
        st.metric("Reconciled", f"{reconciled_count} ({progress_pct:.1f}%)")
    with col3:
        st.metric("Remaining", total_accounts - reconciled_count)

    st.progress(progress_pct / 100)

    # Show info about excluded accounts
    pl_count = len(recon_df[recon_df['Subcategory'] == 'PL'])
    pl_ignore_count = len(recon_df[recon_df['Category'] == 'PL - Ignore'])
    total_excluded = pl_count + pl_ignore_count
    if total_excluded > 0:
        st.caption(f"ℹ️ {total_excluded} account(s) excluded (PL/PL-Ignore - no reconciliation needed)")

    st.markdown("---")

    # Filter options
    col1, col2 = st.columns(2)
    with col1:
        show_filter = st.selectbox(
            "Show accounts:",
            ["All Accounts", "Not Reconciled", "Reconciled", "MISMATCH Only"]
        )
    with col2:
        subcategory_filter = st.selectbox(
            "Filter by subcategory:",
            ["All"] + sorted(recon_df['Subcategory'].unique().tolist())
        )

    # Apply filters
    filtered_df = recon_df.copy()
    if show_filter == "Not Reconciled":
        filtered_df = filtered_df[~filtered_df['Reconciled']]
    elif show_filter == "Reconciled":
        filtered_df = filtered_df[filtered_df['Reconciled']]
    elif show_filter == "MISMATCH Only":
        filtered_df = filtered_df[filtered_df['Status'].str.upper() == 'MISMATCH']

    if subcategory_filter != "All":
        filtered_df = filtered_df[filtered_df['Subcategory'] == subcategory_filter]

    st.markdown(f"**Showing {len(filtered_df)} accounts**")

    # Display account list with reconcile buttons
    for idx, row in filtered_df.iterrows():
        account = str(row['Account'])
        with st.container():
            cols = st.columns([3, 1, 1, 1, 1, 1])

            with cols[0]:
                st.write(f"**{account}**")
            with cols[1]:
                debit = row.get('Debit', 0)
                if debit > 0:
                    st.write(f"Dr: {debit:,.0f}")
            with cols[2]:
                credit = row.get('Credit', 0)
                if credit > 0:
                    st.write(f"Cr: {credit:,.0f}")
            with cols[3]:
                st.write(row.get('Subcategory', ''))
            with cols[4]:
                subcategory = row.get('Subcategory', '')
                category = row.get('Category', '')
                # P&L and "PL - Ignore" accounts don't need reconciliation
                if subcategory == 'PL' or category == 'PL - Ignore':
                    st.info("Not Required")
                elif row['Reconciled']:
                    st.success("✓ Done")
                else:
                    st.warning("⏳ Pending")
            with cols[5]:
                subcategory = row.get('Subcategory', '')
                category = row.get('Category', '')
                # P&L and "PL - Ignore" accounts don't need reconciliation - no button
                if subcategory == 'PL' or category == 'PL - Ignore':
                    st.write("—")
                else:
                    if st.button("Reconcile", key=f"recon_{idx}"):
                        st.session_state.selected_account = account
                        st.session_state.show_reconciliation_interface = True
                        st.rerun()

    # Show reconciliation interface if account selected
    if st.session_state.get('show_reconciliation_interface', False):
        # Add anchor for scrolling
        st.markdown('<div id="reconciliation-section"></div>', unsafe_allow_html=True)

        # Use st.components to inject JavaScript for scrolling
        import streamlit.components.v1 as components
        components.html("""
        <script>
            // Scroll to reconciliation section
            setTimeout(function() {
                window.parent.document.getElementById('reconciliation-section').scrollIntoView({
                    behavior: 'smooth',
                    block: 'start'
                });
            }, 100);
        </script>
        """, height=0)

        # Get selected account info to determine subcategory
        selected_account = st.session_state.selected_account
        account_info = tb_merged[tb_merged['Account'].astype(str) == selected_account].iloc[0]
        subcategory = account_info.get('Subcategory', '')

        # Show appropriate interface based on subcategory
        if subcategory == 'Banks':
            show_bank_reconciliation_interface(
                selected_account,
                tb_merged,
                session_id,
                api_key
            )
        else:
            show_reconciliation_interface(
                selected_account,
                tb_merged,
                session_id,
                api_key
            )


def show_bank_reconciliation_interface(account: str, tb_merged: pd.DataFrame, session_id: str, api_key: str):
    """
    Show bank reconciliation interface - uses screenshot comparison instead of GL dump.
    """
    st.markdown("---")
    st.markdown(f"## 🏦 Bank Reconciliation: {account}")

    # Get account info
    account_row = tb_merged[tb_merged['Account'].astype(str) == account].iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("GL Balance (Debit)", f"${account_row['Debit']:,.2f}")
    with col2:
        st.metric("GL Balance (Credit)", f"${account_row['Credit']:,.2f}")
    with col3:
        gl_balance = account_row['Debit'] if account_row['Debit'] > 0 else account_row['Credit']
        st.metric("Net GL Balance", f"${gl_balance:,.2f}")

    st.info("💡 For bank accounts, upload a screenshot of your bank statement showing the reconciled balance.")

    # Bank statement screenshot upload
    st.markdown("### 1. Upload Bank Statement Screenshot")
    bank_screenshot = st.file_uploader(
        f"Upload bank statement screenshot for {account}",
        type=['png', 'jpg', 'jpeg', 'pdf'],
        key=f"bank_screenshot_{account}"
    )

    if bank_screenshot:
        st.success("✓ Bank statement uploaded")

        # Display the image
        if bank_screenshot.type.startswith('image/'):
            st.image(bank_screenshot, caption="Bank Statement", width='stretch')

        st.markdown("### 2. Verify Balance Match")

        if st.button("🤖 Compare with Claude", key=f"compare_bank_{account}"):
            with st.spinner("Analyzing bank statement..."):
                from anthropic import Anthropic
                import base64

                client = Anthropic(api_key=api_key)

                # Read image and encode
                bank_screenshot.seek(0)
                image_data = base64.standard_b64encode(bank_screenshot.read()).decode("utf-8")

                # Determine media type
                media_type = "image/jpeg"
                if bank_screenshot.type == "image/png":
                    media_type = "image/png"
                elif bank_screenshot.type == "application/pdf":
                    media_type = "application/pdf"

                prompt = f"""Analyze this bank statement screenshot and extract the reconciled balance.

Account: {account}
GL Balance from our records: ${gl_balance:,.2f}

Please:
1. Extract the bank balance from the statement
2. Compare it with our GL balance (${gl_balance:,.2f})
3. Determine if they match (within $1 tolerance for rounding)

Provide your response in this format:

BANK BALANCE: [amount]
GL BALANCE: ${gl_balance:,.2f}
STATUS: [MATCH or MISMATCH]
DIFFERENCE: [amount if any]

RECONCILIATION NOTES:
[Brief notes about the reconciliation]
"""

                response = client.messages.create(
                    model="claude-sonnet-4-5-20250929",
                    max_tokens=1024,
                    messages=[{
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": media_type,
                                    "data": image_data,
                                },
                            },
                            {
                                "type": "text",
                                "text": prompt
                            }
                        ]
                    }]
                )

                reconciliation_result = response.content[0].text

                # Store in session state
                st.session_state[f'bank_recon_result_{account}'] = reconciliation_result
                st.rerun()

        # Show reconciliation results if available
        if f'bank_recon_result_{account}' in st.session_state:
            result = st.session_state[f'bank_recon_result_{account}']

            st.markdown("### 3. Reconciliation Results")

            # Parse result to show status prominently
            if "STATUS: MATCH" in result.upper():
                st.success("✅ **BALANCE MATCHES** - Bank statement matches GL balance!")
            elif "STATUS: MISMATCH" in result.upper():
                st.error("❌ **BALANCE MISMATCH** - Bank statement does not match GL balance")
            else:
                st.warning("⚠️ **REVIEW REQUIRED** - Please review the results below")

            st.markdown(result)

            # Save reconciliation
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✓ Mark as Reconciled", key=f"mark_done_bank_{account}"):
                    # Save reconciliation state
                    if account not in st.session_state.reconciliation_state:
                        st.session_state.reconciliation_state[account] = {}

                    st.session_state.reconciliation_state[account] = {
                        'reconciled': True,
                        'timestamp': datetime.now().isoformat(),
                        'memo': result,
                        'type': 'bank_screenshot'
                    }

                    # Save to file
                    save_reconciliation_state(session_id, st.session_state.reconciliation_state)

                    # Auto-save session
                    if st.session_state.current_session_id:
                        session_manager.auto_save_session(st.session_state.current_session_id)

                    st.success(f"✓ {account} marked as reconciled!")
                    st.session_state.show_reconciliation_interface = False
                    st.rerun()

            with col2:
                # Download reconciliation report
                report_data = f"""Bank Reconciliation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Account: {account}
Category: Bank
GL Balance: ${gl_balance:,.2f}

{result}
"""
                st.download_button(
                    "📥 Download Report",
                    data=report_data,
                    file_name=f"Bank_Reconciliation_{account.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                    mime="text/plain"
                )

    # Close button
    if st.button("← Back to Account List"):
        st.session_state.show_reconciliation_interface = False
        st.rerun()


def show_reconciliation_interface(account: str, tb_merged: pd.DataFrame, session_id: str, api_key: str):
    """
    Show the interactive reconciliation interface for a specific account.
    """
    st.markdown("---")
    st.markdown(f"## 🔍 Reconciling: {account}")

    # Get account info
    account_row = tb_merged[tb_merged['Account'].astype(str) == account].iloc[0]

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Debit", f"${account_row['Debit']:,.2f}")
    with col2:
        st.metric("Credit", f"${account_row['Credit']:,.2f}")
    with col3:
        st.metric("Category", account_row.get('Category', 'N/A'))

    # GL dump upload for this account
    st.markdown("### 1. Upload GL Dump for this Account")
    gl_file = st.file_uploader(
        f"Upload GL transactions for {account}",
        type=['xlsx', 'xls', 'csv'],
        key=f"gl_upload_{account}"
    )

    if gl_file:
        st.success("✓ GL dump uploaded")

        # Parse GL dump
        try:
            import processor
            gl_df = processor.parse_gl_dump(gl_file)

            # Overall summary
            st.write(f"**{len(gl_df)} transactions loaded**")

            # Year-by-year breakdown
            st.markdown("**📅 Breakdown by Year:**")
            gl_df['Year'] = pd.to_datetime(gl_df['Date'], errors='coerce').dt.year
            year_summary = gl_df.groupby('Year').agg({
                'Debit': 'sum',
                'Credit': 'sum',
                'Date': 'count'
            }).rename(columns={'Date': 'Transactions'})

            # Display year summary in columns
            years = sorted(year_summary.index.dropna().astype(int).tolist())
            if years:
                cols = st.columns(min(len(years), 4))  # Max 4 columns
                for idx, year in enumerate(years):
                    with cols[idx % 4]:
                        st.metric(
                            f"{year}",
                            f"{int(year_summary.loc[year, 'Transactions'])} txns",
                            f"Net: ${year_summary.loc[year, 'Debit'] - year_summary.loc[year, 'Credit']:,.0f}"
                        )

            # Show transaction summary
            with st.expander("📊 View All Transactions", expanded=False):
                st.dataframe(gl_df, width='stretch')

            # Interactive reconciliation with Claude
            st.markdown("### 2. Reconciliation Analysis")

            if st.button("🤖 Analyze with Claude", key=f"analyze_{account}"):
                with st.spinner("Analyzing account..."):
                    # Format data for Claude
                    gl_text = processor.format_gl_for_claude(gl_df, account)

                    # Call Claude for reconciliation
                    from anthropic import Anthropic
                    import prompts

                    client = Anthropic(api_key=api_key)

                    prompt = f"""Perform a comprehensive reconciliation analysis for this account:

Account: {account}
Category: {account_row.get('Category', 'N/A')}
Subcategory: {account_row.get('Subcategory', 'N/A')}
Balance: Debit ${account_row['Debit']:,.2f} / Credit ${account_row['Credit']:,.2f}

GL Transactions:
{gl_text}

Provide a comprehensive analysis with the following sections:

## SECTION 1: RECONCILIATION MEMO
- Summary of account activity
- Key observations and findings
- Any discrepancies or issues identified
- Balance validation (does it match expected behavior?)

## SECTION 2: RECONCILIATION SCHEDULE
Detailed breakdown in table format:
- By vendor/counterparty (if applicable)
- By date/aging buckets (if applicable)
- By transaction type (if applicable)
Show amounts clearly with totals

## SECTION 3: OUTPUT B - ACCOUNT-LEVEL ANALYSIS
- Top 5 largest components of this balance
- Aging analysis (if applicable - group by date ranges)
- Key risk items or unusual transactions
- Validation of balance type (should it be debit/credit?)
- Any red flags or items needing investigation

## SECTION 4: OUTPUT C - EXECUTIVE SUMMARY
- High-level summary (2-3 sentences for executives)
- Key findings and concerns
- Priority recommendations
- Overall status: **Clean** / **Needs Attention** / **Critical**

## SECTION 5: RECOMMENDATIONS
- Specific actions needed
- Priority level for each action
- Who should handle (if relevant)

Format professionally with clear headers and tables where appropriate.
"""

                    response = client.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=4096,
                        messages=[{"role": "user", "content": prompt}]
                    )

                    reconciliation_result = response.content[0].text

                    # Store in session state
                    st.session_state[f'recon_result_{account}'] = reconciliation_result
                    st.rerun()

            # Show reconciliation results if available
            if f'recon_result_{account}' in st.session_state:
                result = st.session_state[f'recon_result_{account}']

                st.markdown("### 3. Reconciliation Results")
                st.markdown(result)

                # Save reconciliation
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✓ Mark as Reconciled", key=f"mark_done_{account}"):
                        # Save reconciliation state
                        if account not in st.session_state.reconciliation_state:
                            st.session_state.reconciliation_state[account] = {}

                        st.session_state.reconciliation_state[account] = {
                            'reconciled': True,
                            'timestamp': datetime.now().isoformat(),
                            'memo': result,
                            'gl_rows': len(gl_df)
                        }

                        # Save to file
                        save_reconciliation_state(session_id, st.session_state.reconciliation_state)

                        # Auto-save session
                        if st.session_state.current_session_id:
                            session_manager.auto_save_session(st.session_state.current_session_id)

                        st.success(f"✓ {account} marked as reconciled!")
                        st.session_state.show_reconciliation_interface = False
                        st.rerun()

                with col2:
                    # Download reconciliation report
                    report_data = f"""Account Reconciliation Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Account: {account}
Category: {account_row.get('Category', 'N/A')}
Subcategory: {account_row.get('Subcategory', 'N/A')}
Balance: Debit ${account_row['Debit']:,.2f} / Credit ${account_row['Credit']:,.2f}
Transactions: {len(gl_df)}

{result}
"""
                    st.download_button(
                        "📥 Download Report",
                        data=report_data,
                        file_name=f"Reconciliation_{account.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                        mime="text/plain"
                    )

                # GL Chat Interface - Always visible
                st.markdown("---")
                st.markdown("### 💬 Chat with GL Data")
                st.markdown(f"Ask questions about the GL transactions for **{account}**")

                # Initialize chat history for this account
                chat_key = f'gl_chat_{account}'
                if chat_key not in st.session_state:
                    st.session_state[chat_key] = []

                # Display chat history
                for message in st.session_state[chat_key]:
                    with st.chat_message(message["role"]):
                        st.markdown(message["content"])

                # Chat input
                user_input = st.chat_input(f"Ask about {account} transactions...", key=f"chat_input_{account}")

                if user_input:
                    # Add user message
                    st.session_state[chat_key].append({
                        "role": "user",
                        "content": user_input
                    })

                    # Get GL context
                    gl_context = processor.format_gl_for_claude(gl_df, account)

                    # Build messages for Claude
                    from anthropic import Anthropic
                    client = Anthropic(api_key=api_key)

                    system_prompt = f"""You are a financial analysis assistant. You have access to GL transaction data for account {account}.

Account Details:
- Account: {account}
- Category: {account_row.get('Category', 'N/A')}
- Subcategory: {account_row.get('Subcategory', 'N/A')}
- Balance: Debit ${account_row['Debit']:,.2f} / Credit ${account_row['Credit']:,.2f}

GL Transactions:
{gl_context}

Answer questions about these transactions clearly and concisely. Use actual data to support your answers."""

                    # Prepare messages
                    api_messages = []
                    for msg in st.session_state[chat_key]:
                        api_messages.append({
                            "role": msg["role"],
                            "content": msg["content"]
                        })

                    # Get response
                    response = client.messages.create(
                        model="claude-sonnet-4-5-20250929",
                        max_tokens=2048,
                        system=system_prompt,
                        messages=api_messages
                    )

                    assistant_response = response.content[0].text

                    # Add assistant response
                    st.session_state[chat_key].append({
                        "role": "assistant",
                        "content": assistant_response
                    })

                    st.rerun()

        except Exception as e:
            st.error(f"Error parsing GL dump: {str(e)}")

    # Close button
    if st.button("← Back to Account List"):
        st.session_state.show_reconciliation_interface = False
        st.rerun()
