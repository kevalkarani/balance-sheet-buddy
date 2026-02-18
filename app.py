"""
Balance Sheet Buddy - Web Application
A Streamlit app for AI-powered balance sheet reconciliation.
"""

import streamlit as st
import pandas as pd
from anthropic import Anthropic
import os
from datetime import datetime

# Import our custom modules
import processor
import prompts
import outputs
import reconciliation
import session_manager


# Page configuration
st.set_page_config(
    page_title="Balance Sheet Buddy",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)


def check_api_key():
    """Check if Claude API key is configured."""
    try:
        api_key = st.secrets["ANTHROPIC_API_KEY"]
        return api_key
    except (FileNotFoundError, KeyError):
        st.error("⚠️ ANTHROPIC_API_KEY not configured. Please add it to Streamlit secrets.")
        st.info("""
        **For local development:** Create `.streamlit/secrets.toml` with:
        ```toml
        ANTHROPIC_API_KEY = "your-api-key-here"
        ```

        **For Streamlit Cloud:** Add the API key in App Settings → Secrets
        """)
        st.stop()
        return None


def call_claude(prompt: str, api_key: str, max_tokens: int = 16384) -> str:
    """Call Claude API with the given prompt using streaming for large responses."""
    try:
        client = Anthropic(api_key=api_key)

        # Use streaming for responses that might take a while
        full_response = ""

        with client.messages.stream(
            model="claude-sonnet-4-5-20250929",
            max_tokens=max_tokens,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        ) as stream:
            for text in stream.text_stream:
                full_response += text

        return full_response

    except Exception as e:
        st.error(f"Error calling Claude API: {str(e)}")
        return None


def main():
    # Initialize session state for persisting results
    if 'analysis_complete' not in st.session_state:
        st.session_state.analysis_complete = False
    if 'classification_result' not in st.session_state:
        st.session_state.classification_result = None
    if 'classification_df' not in st.session_state:
        st.session_state.classification_df = None
    if 'excel_output' not in st.session_state:
        st.session_state.excel_output = None
    if 'reconciliation_result' not in st.session_state:
        st.session_state.reconciliation_result = None
    if 'tb_merged' not in st.session_state:
        st.session_state.tb_merged = None
    if 'current_session_id' not in st.session_state:
        st.session_state.current_session_id = None
    if 'session_auto_loaded' not in st.session_state:
        st.session_state.session_auto_loaded = False

    # Auto-load session from URL if present (only once per page load)
    if not st.session_state.session_auto_loaded:
        session_id = session_manager.get_session_id_from_url()
        if session_id and not st.session_state.analysis_complete:
            if session_manager.auto_load_session(session_id):
                st.session_state.current_session_id = session_id
                st.session_state.session_auto_loaded = True
                st.success(f"✅ Session restored automatically!")
                st.rerun()
        st.session_state.session_auto_loaded = True

    # Cleanup old sessions (run once on app load)
    session_manager.cleanup_old_sessions(days=7)

    # Header
    st.title("📊 Balance Sheet Buddy")
    st.markdown("### AI-Powered Balance Sheet Reconciliation")
    st.caption("🔄 Version: 2024-02-17.2 (Streaming + Status Fix)")
    st.markdown("---")

    # Check API key
    api_key = check_api_key()

    # Sidebar
    with st.sidebar:
        # Session Management - Load Previous Session
        st.markdown("### 📂 Load Previous Session")
        session_file = st.file_uploader(
            "Upload saved session file",
            type=['json'],
            help="Restore your previous work by uploading a saved session file",
            key="session_uploader"
        )

        if session_file:
            if st.button("🔄 Restore Session", type="primary", width='stretch'):
                with st.spinner("Restoring session..."):
                    if session_manager.import_session(session_file):
                        st.success("✅ Session restored successfully!")
                        st.rerun()
                    else:
                        st.error("❌ Failed to restore session")

        st.markdown("---")
        st.header("📁 File Uploads")

        # Category Mapping - Always use default (hidden from users)
        default_mapping_path = "Category mapping Balance Sheet.xlsx"
        use_default_mapping = True
        mapping_file = None  # Users cannot upload custom mapping

        # Trial Balance
        st.subheader("1. Trial Balance (Required)")
        tb_file = st.file_uploader(
            "Upload Trial Balance",
            type=['xlsx', 'xls', 'csv'],
            help="Excel or CSV file with Account, Debit, and Credit columns"
        )

        # Debug: Show upload status
        if tb_file is not None:
            st.success(f"✓ File uploaded: {tb_file.name}")
        else:
            st.info("Waiting for file...")

        st.markdown("---")

        # GL Dump
        st.subheader("2. GL Dump (Optional)")
        gl_files = st.file_uploader(
            "Upload GL dump file(s)",
            type=['xlsx', 'xls', 'csv'],
            accept_multiple_files=True,
            help="General Ledger transaction details for detailed analysis (Output B & C)"
        )

        st.markdown("---")

        # Analysis options
        st.subheader("⚙️ Analysis Options")
        analysis_type = st.radio(
            "Select analysis type:",
            ["Classification Only (Output A)", "Full Analysis (Outputs A, B, C)"],
            help="Classification provides validation status. Full analysis includes detailed reconciliation."
        )

        show_mismatches_only = st.checkbox(
            "Show mismatches only",
            value=False,
            help="If checked, Output A will only show accounts with MISMATCH status"
        )

    # Main content area
    # Debug: Show file status
    if tb_file:
        st.write(f"📁 File detected: {tb_file.name} ({tb_file.size:,} bytes)")

    if not tb_file:
        # Welcome screen
        st.info("👈 Please upload a Trial Balance file to get started")

        st.markdown("### How to Use Balance Sheet Buddy")

        col1, col2 = st.columns(2)

        with col1:
            st.markdown("#### 📥 Input Files")
            st.markdown("""
            **Trial Balance (Required):**
            - Excel or CSV format
            - Must have: Account, Debit, Credit columns
            - Account can be "Account Number - Name"

            **Category Mapping (Optional):**
            - Maps accounts to Categories and Subcategories
            - Helps with automated classification
            - If not provided, accounts marked as "Unmapped"

            **GL Dump (Optional):**
            - Transaction-level details
            - Required for detailed analysis (Outputs B & C)
            - Multiple files supported
            """)

        with col2:
            st.markdown("#### 📤 Outputs")
            st.markdown("""
            **Output A - Classification View:**
            - Excel file with validation status
            - Shows PASS/MISMATCH for each account
            - Validates balance behavior (Asset=Debit, Liability=Credit, etc.)

            **Output B - Account Reconciliation:**
            - Detailed breakdown of each account
            - Top 5 components, aging analysis
            - Action recommendations

            **Output C - Executive Summary:**
            - High-level overview
            - Accounts needing attention
            - Key risk items
            """)

        st.markdown("---")
        st.markdown("### Expected Balance Behavior")
        st.markdown("""
        | Account Type | Expected Balance | Status if Correct |
        |--------------|------------------|-------------------|
        | Asset | Debit | ✅ PASS |
        | Liability | Credit | ✅ PASS |
        | Equity | Credit | ✅ PASS |
        | Clearing | Zero | ✅ PASS |
        | Contra-Asset | Credit | ✅ PASS |
        """)

    else:
        # Process uploaded files
        st.success("✓ Trial Balance uploaded")
        st.write("---")

        # Analysis button - prominently displayed
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            analyze_button = st.button("🚀 Analyze Balance Sheet", type="primary", width='stretch')

        if analyze_button:
            with st.spinner("Processing files and performing analysis..."):

                try:
                    # Step 1: Parse Trial Balance
                    with st.status("📊 Parsing Trial Balance...", expanded=True) as status:
                        tb_df = processor.parse_trial_balance(tb_file)
                        st.write(f"✓ Loaded {len(tb_df)} accounts")

                        # Clean data
                        tb_df_clean = processor.clean_data(tb_df)
                        removed = len(tb_df) - len(tb_df_clean)
                        st.write(f"✓ Removed {removed} blank/total rows")
                        st.write(f"✓ {len(tb_df_clean)} accounts ready for analysis")

                        status.update(label="✓ Trial Balance parsed", state="complete")

                    # Step 2: Load and merge category mapping
                    with st.status("🗂️ Loading category mapping...", expanded=True) as status:
                        if mapping_file:
                            mapping_df = processor.load_category_mapping(mapping_file)
                            st.write(f"✓ Loaded {len(mapping_df)} category mappings from uploaded file")
                        elif use_default_mapping:
                            with open(default_mapping_path, 'rb') as f:
                                mapping_df = processor.load_category_mapping(f)
                            st.write(f"✓ Loaded {len(mapping_df)} category mappings from default file")
                        else:
                            mapping_df = pd.DataFrame({
                                'Account_Key': [],
                                'Category': [],
                                'Subcategory': []
                            })
                            st.write("⚠️ No mapping file provided - accounts will be marked as 'Unmapped'")

                        # Merge with trial balance
                        tb_merged = processor.merge_with_mapping(tb_df_clean, mapping_df)
                        mapped_count = len(tb_merged[tb_merged['Category'] != 'Unmapped'])
                        st.write(f"✓ Mapped {mapped_count}/{len(tb_merged)} accounts")

                        status.update(label="✓ Category mapping applied", state="complete")

                    # Step 3: Format for Claude
                    with st.status("🤖 Preparing data for AI analysis...", expanded=True) as status:
                        tb_text = processor.format_for_claude(tb_merged)
                        st.write(f"✓ Formatted {len(tb_merged)} accounts for analysis")
                        status.update(label="✓ Data formatted", state="complete")

                    # Step 4: Call Claude for Output A
                    with st.status("🧠 Analyzing with Claude AI (Output A)...", expanded=True) as status:
                        if show_mismatches_only:
                            prompt = prompts.generate_mismatch_only_prompt(tb_text)
                        else:
                            prompt = prompts.generate_output_a_prompt(tb_text)

                        # Calculate max_tokens based on account count (roughly 100 tokens per account + overhead)
                        estimated_tokens = max(16384, len(tb_merged) * 100 + 2000)
                        estimated_tokens = min(estimated_tokens, 32000)  # Cap at model limit
                        st.write(f"✓ Using {estimated_tokens} max tokens for {len(tb_merged)} accounts")
                        st.write("⏳ Streaming response from Claude (this may take 30-60 seconds)...")

                        classification_result = call_claude(prompt, api_key, max_tokens=estimated_tokens)

                        if classification_result:
                            st.write("✓ Classification analysis complete")
                            status.update(label="✓ Output A generated", state="complete")
                        else:
                            st.error("Failed to get analysis from Claude")
                            st.stop()

                    # Step 5: Parse classification results into DataFrame
                    with st.status("📋 Parsing classification results...", expanded=True) as status:
                        classification_df = outputs.parse_claude_table_response(classification_result)

                        # Check if parsing was successful AND Status column has actual values
                        has_valid_status = (not classification_df.empty and
                                          'Status' in classification_df.columns and
                                          classification_df['Status'].notna().any())

                        if has_valid_status:
                            st.write(f"✓ Parsed {len(classification_df)} accounts from Claude response")
                            # Merge with tb_merged to get Debit, Credit, Amount columns
                            # Match on Account column
                            classification_df = tb_merged.merge(
                                classification_df[['Account', 'Status', 'Balance_Type', 'Commentary'] if 'Commentary' in classification_df.columns else ['Account', 'Status', 'Balance_Type']],
                                on='Account',
                                how='left'
                            )
                            # Fill missing Status with inferred values
                            if classification_df['Status'].isna().any():
                                def infer_status(row):
                                    if pd.notna(row.get('Status')):
                                        return row['Status']
                                    category = str(row.get('Category', '')).lower()
                                    balance_type = 'Debit' if row['Debit'] > 0 else 'Credit' if row['Credit'] > 0 else 'Zero'
                                    if 'asset' in category and 'contra' not in category:
                                        return 'PASS' if balance_type == 'Debit' else 'MISMATCH'
                                    elif 'liability' in category or 'equity' in category:
                                        return 'PASS' if balance_type == 'Credit' else 'MISMATCH'
                                    elif 'clearing' in category:
                                        return 'PASS' if balance_type == 'Zero' else 'MISMATCH'
                                    else:
                                        return 'PASS'
                                classification_df['Status'] = classification_df.apply(infer_status, axis=1)
                        else:
                            st.write("⚠️ Claude response not in table format or Status column empty - using trial balance with inferred status")
                            # Use trial balance and infer basic status
                            classification_df = tb_merged.copy()

                            # Infer basic PASS/MISMATCH based on balance type
                            def infer_status(row):
                                category = str(row.get('Category', '')).lower()
                                balance_type = 'Debit' if row['Debit'] > 0 else 'Credit' if row['Credit'] > 0 else 'Zero'

                                # Basic validation rules
                                if 'asset' in category and 'contra' not in category:
                                    return 'PASS' if balance_type == 'Debit' else 'MISMATCH'
                                elif 'liability' in category or 'equity' in category:
                                    return 'PASS' if balance_type == 'Credit' else 'MISMATCH'
                                elif 'clearing' in category:
                                    return 'PASS' if balance_type == 'Zero' else 'MISMATCH'
                                else:
                                    return 'PASS'  # Default for unmapped

                            classification_df['Status'] = classification_df.apply(infer_status, axis=1)
                            classification_df['Balance_Type'] = classification_df.apply(
                                lambda row: 'Debit' if row['Debit'] > 0 else 'Credit' if row['Credit'] > 0 else 'Zero',
                                axis=1
                            )
                            classification_df['Amount'] = classification_df.apply(
                                lambda row: row['Debit'] if row['Debit'] > 0 else row['Credit'],
                                axis=1
                            )

                        # Ensure required columns exist even if parsed successfully
                        if 'Balance_Type' not in classification_df.columns:
                            classification_df['Balance_Type'] = classification_df.apply(
                                lambda row: 'Debit' if row['Debit'] > 0 else 'Credit' if row['Credit'] > 0 else 'Zero',
                                axis=1
                            )
                        if 'Amount' not in classification_df.columns:
                            classification_df['Amount'] = classification_df.apply(
                                lambda row: row['Debit'] if row['Debit'] > 0 else row['Credit'],
                                axis=1
                            )

                        # Generate Excel using the same DataFrame that will be displayed
                        # This ensures Excel matches what user sees on screen
                        excel_output = outputs.create_classification_excel_from_df(classification_df)
                        st.write("✓ Excel file created")
                        status.update(label="✓ Classification parsed", state="complete")

                    # Step 6: If full analysis requested and GL provided
                    reconciliation_result = None
                    if analysis_type == "Full Analysis (Outputs A, B, C)" and gl_files:
                        with st.status("🧠 Performing detailed reconciliation (Outputs B & C)...", expanded=True) as status:
                            # Parse GL dumps
                            gl_dfs = []
                            for gl_file in gl_files:
                                try:
                                    gl_df = processor.parse_gl_dump(gl_file)
                                    gl_dfs.append(gl_df)
                                    st.write(f"✓ Loaded {len(gl_df)} transactions from {gl_file.name}")
                                except Exception as e:
                                    st.warning(f"⚠️ Could not parse {gl_file.name}: {str(e)}")

                            if gl_dfs:
                                # Combine all GL data
                                gl_combined = pd.concat(gl_dfs, ignore_index=True)
                                gl_text = processor.format_gl_for_claude(gl_combined)
                                st.write(f"✓ Total {len(gl_combined)} transactions loaded")

                                # Call Claude for Outputs B & C
                                bc_prompt = prompts.generate_output_bc_prompt(tb_text, gl_text)
                                reconciliation_result = call_claude(bc_prompt, api_key)

                                if reconciliation_result:
                                    st.write("✓ Detailed reconciliation complete")
                                    status.update(label="✓ Outputs B & C generated", state="complete")
                            else:
                                st.warning("No GL data could be parsed")
                                status.update(label="⚠️ GL parsing failed", state="error")

                    elif analysis_type == "Full Analysis (Outputs A, B, C)" and not gl_files:
                        st.warning("⚠️ Full analysis requires GL dump files. Upload GL files in the sidebar.")

                    # Store results in session state
                    st.session_state.analysis_complete = True
                    st.session_state.classification_result = classification_result
                    st.session_state.classification_df = classification_df
                    st.session_state.excel_output = excel_output
                    st.session_state.reconciliation_result = reconciliation_result
                    st.session_state.tb_merged = tb_merged

                    # Auto-save session to server
                    with st.spinner("💾 Auto-saving your session..."):
                        session_id = session_manager.auto_save_session(st.session_state.current_session_id)
                        st.session_state.current_session_id = session_id
                        session_manager.set_session_id_in_url(session_id)
                        st.success("✅ Session auto-saved! You can bookmark this URL to return to your work.")

                except Exception as e:
                    st.error(f"❌ Error during analysis: {str(e)}")
                    st.exception(e)

        # Display results (outside the button block, using session state)
        if st.session_state.analysis_complete:
            st.markdown("---")

            # Header with Save Session button
            col1, col2 = st.columns([3, 1])
            with col1:
                st.header("📊 Analysis Results")
            with col2:
                # Save Session button (for manual backup)
                session_bytes = session_manager.export_session()
                st.download_button(
                    label="📥 Download Backup",
                    data=session_bytes,
                    file_name=f"BSBuddy_Session_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    mime="application/json",
                    width='stretch',
                    help="Download a backup copy of your session (auto-save is already active)"
                )

            # Show auto-save status
            if st.session_state.current_session_id:
                st.info(f"🔄 Auto-save active • Session ID: `{st.session_state.current_session_id}` • Bookmark this page to return to your work anytime!")

            # Summary stats - pass classification DataFrame which has Status column
            stats = outputs.extract_summary_stats(
                st.session_state.classification_result,
                st.session_state.classification_df  # Changed from tb_merged to classification_df
            )

            # Also pass DataFrame to summary for listing mismatched accounts
            classification_df_for_stats = st.session_state.classification_df if st.session_state.classification_df is not None and not st.session_state.classification_df.empty else st.session_state.tb_merged

            # Display summary in a code block for proper formatting
            summary_text = outputs.create_summary_text(stats, classification_df_for_stats)
            st.text(summary_text)

            st.markdown("---")

            # Output tabs - Always include Account Reconciliation tab
            if st.session_state.reconciliation_result:
                tab1, tab2, tab3, tab4 = st.tabs([
                    "📋 Output A - Classification",
                    "🔍 Account Reconciliation",
                    "📊 Output B - Reconciliation",
                    "📈 Output C - Summary"
                ])
            else:
                tab1, tab2 = st.tabs([
                    "📋 Output A - Classification",
                    "🔍 Account Reconciliation"
                ])

            with tab1:
                st.subheader("Classification View")

                # Download button for Excel
                st.download_button(
                    label="⬇️ Download Output A (Excel)",
                    data=st.session_state.excel_output,
                    file_name=f"Balance_Sheet_Classification_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                    key="download_excel"
                )

                # Display classification results as table
                st.markdown("#### Classification Results")
                if st.session_state.classification_df is not None and not st.session_state.classification_df.empty:
                    # Format the dataframe for display
                    display_df = st.session_state.classification_df.copy()

                    # Format numerical columns with commas, no decimals
                    def format_number(value):
                        """Format number with thousand separators, no decimals."""
                        try:
                            num = float(value)
                            return f"{num:,.0f}"
                        except (ValueError, TypeError):
                            return value

                    # Apply formatting to numerical columns
                    for col in ['Debit', 'Credit', 'Amount']:
                        if col in display_df.columns:
                            display_df[col] = display_df[col].apply(format_number)

                    # Color code based on status
                    def highlight_status(row):
                        if 'Status' in row and isinstance(row['Status'], str):
                            if row['Status'].upper() == 'PASS':
                                return ['background-color: #d4edda'] * len(row)
                            elif row['Status'].upper() == 'MISMATCH':
                                return ['background-color: #f8d7da'] * len(row)
                        return [''] * len(row)

                    # Apply styling: colors and right-align numerical columns
                    styled_df = display_df.style.apply(highlight_status, axis=1)

                    # Right-align numerical columns (Debit, Credit, Amount)
                    align_dict = {}
                    for col in ['Debit', 'Credit', 'Amount']:
                        if col in display_df.columns:
                            align_dict[col] = 'text-align: right'

                    if align_dict:
                        styled_df = styled_df.set_properties(subset=list(align_dict.keys()), **{'text-align': 'right'})

                    # Display with styling - large height to show many rows
                    st.dataframe(
                        styled_df,
                        width='stretch',
                        height=600  # Scrollable table
                    )
                else:
                    st.info("Classification table could not be parsed. Download Excel file for full results.")

                # Show raw text as expandable section
                with st.expander("📄 View Raw Claude Response"):
                    st.text(st.session_state.classification_result)

            # Tab 2: Account Reconciliation (NEW)
            with tab2:
                reconciliation.show_reconciliation_tab(
                    st.session_state.classification_df,
                    st.session_state.tb_merged,
                    api_key
                )

            if st.session_state.reconciliation_result:
                # Parse sections
                sections = st.session_state.reconciliation_result.split("OUTPUT C")
                output_b = sections[0].replace("OUTPUT B", "").strip()
                output_c = sections[1].strip() if len(sections) > 1 else ""

                with tab3:  # Changed from tab2 to tab3
                    st.subheader("Account-Level Reconciliation")
                    st.markdown(output_b)

                    # Download button
                    st.download_button(
                        label="⬇️ Download Output B (Text)",
                        data=output_b,
                        file_name=f"Account_Reconciliation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        width='stretch',
                        key="download_output_b"
                    )

                with tab4:  # Changed from tab3 to tab4
                    st.subheader("Executive Summary")
                    st.markdown(output_c)

                    # Download button
                    st.download_button(
                        label="⬇️ Download Output C (Text)",
                        data=output_c,
                        file_name=f"Executive_Summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                        mime="text/plain",
                        width='stretch',
                        key="download_output_c"
                    )

                # Combined report download
                st.markdown("---")
                combined_html = outputs.create_combined_report(
                    st.session_state.classification_result,
                    output_b,
                    output_c
                )
                st.download_button(
                    label="⬇️ Download Complete Report (HTML)",
                    data=combined_html,
                    file_name=f"Balance_Sheet_Complete_Report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                    mime="text/html",
                    width='stretch',
                    key="download_complete"
                )

            st.success("✅ Analysis complete!")

    # Footer
    st.markdown("---")
    st.markdown("""
    <div style='text-align: center; color: #666; font-size: 0.9em;'>
        <p>Balance Sheet Buddy | Powered by Claude AI (Sonnet 4.5)</p>
        <p>Cost estimate: ~$0.50-$2 per analysis |
        <a href='https://github.com' target='_blank'>Documentation</a> |
        <a href='https://console.anthropic.com' target='_blank'>Get API Key</a></p>
    </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()
