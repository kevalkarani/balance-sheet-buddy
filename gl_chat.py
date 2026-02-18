"""
GL Chat Module
Interactive chat interface for asking questions about General Ledger data.
"""

import streamlit as st
import pandas as pd
from anthropic import Anthropic
from typing import List, Dict
import processor


def format_gl_context(gl_df: pd.DataFrame, max_rows: int = 500) -> str:
    """
    Format GL data as context for Claude.
    Limits to recent transactions if dataset is large.
    """
    if gl_df.empty:
        return "No GL data available."

    # Sort by date and take most recent transactions if too large
    gl_sorted = gl_df.sort_values('Date', ascending=False)
    if len(gl_sorted) > max_rows:
        gl_sorted = gl_sorted.head(max_rows)
        note = f"\n(Showing most recent {max_rows} of {len(gl_df)} total transactions)\n"
    else:
        note = f"\n(All {len(gl_df)} transactions included)\n"

    # Format as structured text
    lines = ["GENERAL LEDGER DATA", "=" * 80, note]

    # Add summary statistics
    lines.append(f"Date Range: {gl_sorted['Date'].min()} to {gl_sorted['Date'].max()}")
    lines.append(f"Total Debits: {gl_sorted['Debit'].sum():,.2f}")
    lines.append(f"Total Credits: {gl_sorted['Credit'].sum():,.2f}")
    lines.append(f"Unique Accounts: {gl_sorted['Account'].nunique()}")
    lines.append("")
    lines.append("TRANSACTIONS:")
    lines.append("-" * 80)

    # Add transaction details
    for idx, row in gl_sorted.iterrows():
        date_str = row['Date'].strftime('%Y-%m-%d') if pd.notna(row['Date']) else 'Unknown'
        account = row['Account']
        desc = row['Description']
        debit = row['Debit']
        credit = row['Credit']
        amount = debit if debit > 0 else -credit

        line = f"{date_str} | {account} | {desc} | Amount: {amount:,.2f}"
        lines.append(line)

    return "\n".join(lines)


def call_claude_chat(messages: List[Dict], gl_context: str, api_key: str) -> str:
    """
    Call Claude API with chat messages and GL context.
    """
    try:
        client = Anthropic(api_key=api_key)

        # Build system message with GL context
        system_message = f"""You are a helpful financial analysis assistant. You have access to General Ledger transaction data.

{gl_context}

Your role:
- Answer questions about the GL data above
- Provide summaries, analysis, and insights
- Help identify patterns, anomalies, or specific transactions
- Be concise but thorough
- Use actual data from the GL to support your answers
- Format numbers with commas for readability

If asked about something not in the data, clearly state that."""

        # Call Claude API
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=4096,
            system=system_message,
            messages=messages
        )

        return response.content[0].text

    except Exception as e:
        return f"Error calling Claude API: {str(e)}"


def show_gl_chat_interface(gl_df: pd.DataFrame, api_key: str):
    """
    Display interactive chat interface for GL analysis.
    """
    st.markdown("### 💬 Chat with Your GL Data")
    st.markdown("Ask questions about your General Ledger transactions and get instant analysis from Claude.")

    # Check if GL data is available
    if gl_df is None or gl_df.empty:
        st.warning("⚠️ No GL data available. Please upload GL dump files in the sidebar to enable chat.")
        return

    # Initialize chat history in session state
    if 'gl_chat_history' not in st.session_state:
        st.session_state.gl_chat_history = []

    # Show GL data summary
    with st.expander("📊 GL Data Summary", expanded=False):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Transactions", f"{len(gl_df):,}")
        with col2:
            st.metric("Total Debits", f"${gl_df['Debit'].sum():,.0f}")
        with col3:
            st.metric("Total Credits", f"${gl_df['Credit'].sum():,.0f}")
        with col4:
            st.metric("Unique Accounts", f"{gl_df['Account'].nunique()}")

        st.markdown("**Date Range:**")
        st.write(f"{gl_df['Date'].min().strftime('%Y-%m-%d')} to {gl_df['Date'].max().strftime('%Y-%m-%d')}")

    st.markdown("---")

    # Suggested questions
    st.markdown("**💡 Try asking:**")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("📊 Summarize all transactions by account"):
            st.session_state.gl_chat_input = "Summarize all transactions by account"
        if st.button("🔍 What are the largest transactions?"):
            st.session_state.gl_chat_input = "What are the largest transactions by amount?"
    with col2:
        if st.button("📅 Show transactions from last month"):
            st.session_state.gl_chat_input = "Show me transactions from the last month"
        if st.button("⚠️ Are there any unusual patterns?"):
            st.session_state.gl_chat_input = "Are there any unusual patterns or anomalies in the transactions?"

    st.markdown("---")

    # Display chat history
    chat_container = st.container()
    with chat_container:
        for message in st.session_state.gl_chat_history:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    # Chat input
    user_input = st.chat_input("Ask a question about your GL data...", key="gl_chat_input_widget")

    # Handle suggested question button clicks
    if 'gl_chat_input' in st.session_state and st.session_state.gl_chat_input:
        user_input = st.session_state.gl_chat_input
        st.session_state.gl_chat_input = None

    if user_input:
        # Add user message to history
        st.session_state.gl_chat_history.append({
            "role": "user",
            "content": user_input
        })

        # Display user message
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

        # Prepare GL context
        gl_context = format_gl_context(gl_df)

        # Build messages for Claude (without system message in messages list)
        api_messages = []
        for msg in st.session_state.gl_chat_history:
            api_messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Get Claude's response
        with chat_container:
            with st.chat_message("assistant"):
                with st.spinner("Analyzing GL data..."):
                    response = call_claude_chat(api_messages, gl_context, api_key)
                    st.markdown(response)

        # Add assistant response to history
        st.session_state.gl_chat_history.append({
            "role": "assistant",
            "content": response
        })

        # Rerun to update chat display
        st.rerun()

    # Clear chat button
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 1, 2])
    with col1:
        if st.button("🗑️ Clear Chat", width='stretch'):
            st.session_state.gl_chat_history = []
            st.rerun()
    with col2:
        if st.button("📥 Download Chat", width='stretch'):
            chat_text = "\n\n".join([
                f"{'User' if msg['role'] == 'user' else 'Claude'}: {msg['content']}"
                for msg in st.session_state.gl_chat_history
            ])
            st.download_button(
                label="Download as Text",
                data=chat_text,
                file_name="gl_chat_history.txt",
                mime="text/plain",
                width='stretch'
            )
