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

    # Summary statistics
    total_accounts = len(recon_df)
    reconciled_count = recon_df['Reconciled'].sum()
    progress_pct = (reconciled_count / total_accounts * 100) if total_accounts > 0 else 0

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Total Accounts", total_accounts)
    with col2:
        st.metric("Reconciled", f"{reconciled_count} ({progress_pct:.1f}%)")
    with col3:
        st.metric("Remaining", total_accounts - reconciled_count)

    st.progress(progress_pct / 100)

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
                if row['Reconciled']:
                    st.success("✓ Done")
                else:
                    st.warning("⏳ Pending")
            with cols[5]:
                if st.button("Reconcile", key=f"recon_{idx}"):
                    st.session_state.selected_account = account
                    st.session_state.show_reconciliation_interface = True
                    st.rerun()

    # Show reconciliation interface if account selected
    if st.session_state.get('show_reconciliation_interface', False):
        show_reconciliation_interface(
            st.session_state.selected_account,
            tb_merged,
            session_id,
            api_key
        )


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
            st.write(f"**{len(gl_df)} transactions loaded**")

            # Show transaction summary
            with st.expander("📊 View Transactions"):
                st.dataframe(gl_df, use_container_width=True)

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

                    prompt = f"""Analyze this account for reconciliation:

Account: {account}
Category: {account_row.get('Category', 'N/A')}
Subcategory: {account_row.get('Subcategory', 'N/A')}
Balance: Debit ${account_row['Debit']:,.2f} / Credit ${account_row['Credit']:,.2f}

GL Transactions:
{gl_text}

Please provide:
1. **Reconciliation Memo**: Summary of account activity, key findings, any issues
2. **Reconciliation Schedule**: Detailed breakdown (by vendor, date, or category as appropriate)
3. **Recommendations**: Any actions needed

Format as:
MEMO:
[memo content]

SCHEDULE:
[schedule in table format]

RECOMMENDATIONS:
[recommendations]
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

        except Exception as e:
            st.error(f"Error parsing GL dump: {str(e)}")

    # Close button
    if st.button("← Back to Account List"):
        st.session_state.show_reconciliation_interface = False
        st.rerun()
