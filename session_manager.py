"""
Session Management Module
Handles saving and restoring work sessions including TB data, classification results, and reconciliation progress.
Supports both manual (download/upload) and automatic (server-side) persistence.
"""

import streamlit as st
import pandas as pd
import json
import pickle
import base64
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import io
import os
import hashlib
import glob


def export_session() -> bytes:
    """
    Export current session state to a downloadable file.
    Returns serialized session data as bytes.
    """
    session_data = {
        'export_timestamp': datetime.now().isoformat(),
        'version': '1.0',
        'data': {}
    }

    # Save classification DataFrame
    if 'classification_df' in st.session_state and st.session_state.classification_df is not None:
        session_data['data']['classification_df'] = st.session_state.classification_df.to_json(orient='split')

    # Save trial balance DataFrame
    if 'tb_merged' in st.session_state and st.session_state.tb_merged is not None:
        session_data['data']['tb_merged'] = st.session_state.tb_merged.to_json(orient='split')

    # Save classification result text
    if 'classification_result' in st.session_state:
        session_data['data']['classification_result'] = st.session_state.classification_result

    # Save reconciliation result text
    if 'reconciliation_result' in st.session_state:
        session_data['data']['reconciliation_result'] = st.session_state.reconciliation_result

    # Save Excel output
    if 'excel_output' in st.session_state and st.session_state.excel_output is not None:
        excel_data = st.session_state.excel_output
        # Handle BytesIO objects
        if hasattr(excel_data, 'getvalue'):
            excel_data = excel_data.getvalue()
        session_data['data']['excel_output'] = base64.b64encode(excel_data).decode('utf-8')

    # Save reconciliation state (which accounts are reconciled)
    if 'reconciliation_state' in st.session_state:
        session_data['data']['reconciliation_state'] = st.session_state.reconciliation_state

    # Save analysis completion flag
    if 'analysis_complete' in st.session_state:
        session_data['data']['analysis_complete'] = st.session_state.analysis_complete

    # Serialize to JSON
    json_str = json.dumps(session_data, indent=2)
    return json_str.encode('utf-8')


def import_session(uploaded_file) -> bool:
    """
    Import and restore a previously saved session.
    Returns True if successful, False otherwise.
    """
    try:
        # Read the uploaded file
        session_data = json.load(uploaded_file)

        # Verify version
        if 'version' not in session_data or 'data' not in session_data:
            st.error("Invalid session file format")
            return False

        data = session_data['data']

        # Restore classification DataFrame
        if 'classification_df' in data:
            st.session_state.classification_df = pd.read_json(io.StringIO(data['classification_df']), orient='split')

        # Restore trial balance DataFrame
        if 'tb_merged' in data:
            st.session_state.tb_merged = pd.read_json(io.StringIO(data['tb_merged']), orient='split')

        # Restore classification result text
        if 'classification_result' in data:
            st.session_state.classification_result = data['classification_result']

        # Restore reconciliation result text
        if 'reconciliation_result' in data:
            st.session_state.reconciliation_result = data['reconciliation_result']

        # Restore Excel output
        if 'excel_output' in data:
            st.session_state.excel_output = base64.b64decode(data['excel_output'].encode('utf-8'))

        # Restore reconciliation state
        if 'reconciliation_state' in data:
            st.session_state.reconciliation_state = data['reconciliation_state']

        # Restore analysis completion flag
        if 'analysis_complete' in data:
            st.session_state.analysis_complete = data['analysis_complete']
        else:
            st.session_state.analysis_complete = True  # If we have data, analysis was complete

        return True

    except Exception as e:
        st.error(f"Error importing session: {str(e)}")
        return False


def get_session_summary(session_data: Dict[str, Any]) -> str:
    """
    Generate a summary of what's in a session file.
    """
    if 'data' not in session_data:
        return "Invalid session file"

    data = session_data['data']
    summary_parts = []

    # Count accounts
    if 'classification_df' in data:
        df = pd.read_json(io.StringIO(data['classification_df']), orient='split')
        summary_parts.append(f"📊 {len(df)} accounts")

    # Check reconciliation progress
    if 'reconciliation_state' in data:
        recon_state = data['reconciliation_state']
        reconciled_count = sum(1 for acc in recon_state.values() if acc.get('reconciled', False))
        summary_parts.append(f"✓ {reconciled_count} accounts reconciled")

    # Export timestamp
    if 'export_timestamp' in session_data:
        timestamp = session_data['export_timestamp']
        summary_parts.append(f"📅 Saved: {timestamp[:10]}")

    return " | ".join(summary_parts) if summary_parts else "Session data available"


# ============================================================================
# AUTO-SAVE FUNCTIONS (Server-Side Persistence)
# ============================================================================

SESSIONS_DIR = ".sessions"


def generate_session_id() -> str:
    """
    Generate a unique session ID based on current session state.
    Uses hash of TB data + timestamp for uniqueness.
    """
    # Create a hash from TB data if available
    if 'tb_merged' in st.session_state and st.session_state.tb_merged is not None:
        tb_hash = hashlib.md5(
            st.session_state.tb_merged.to_json().encode()
        ).hexdigest()[:8]
    else:
        tb_hash = hashlib.md5(str(datetime.now()).encode()).hexdigest()[:8]

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return f"session_{tb_hash}_{timestamp}"


def ensure_sessions_dir():
    """Create sessions directory if it doesn't exist."""
    os.makedirs(SESSIONS_DIR, exist_ok=True)


def auto_save_session(session_id: Optional[str] = None) -> str:
    """
    Automatically save current session to server file.
    Returns the session ID.
    """
    ensure_sessions_dir()

    # Generate new session ID if not provided
    if session_id is None:
        session_id = generate_session_id()

    # Get session data
    session_data = {
        'export_timestamp': datetime.now().isoformat(),
        'version': '1.0',
        'session_id': session_id,
        'data': {}
    }

    # Save all session state data
    if 'classification_df' in st.session_state and st.session_state.classification_df is not None:
        session_data['data']['classification_df'] = st.session_state.classification_df.to_json(orient='split')

    if 'tb_merged' in st.session_state and st.session_state.tb_merged is not None:
        session_data['data']['tb_merged'] = st.session_state.tb_merged.to_json(orient='split')

    if 'classification_result' in st.session_state:
        session_data['data']['classification_result'] = st.session_state.classification_result

    if 'reconciliation_result' in st.session_state:
        session_data['data']['reconciliation_result'] = st.session_state.reconciliation_result

    if 'excel_output' in st.session_state and st.session_state.excel_output is not None:
        excel_data = st.session_state.excel_output
        # Handle BytesIO objects
        if hasattr(excel_data, 'getvalue'):
            excel_data = excel_data.getvalue()
        session_data['data']['excel_output'] = base64.b64encode(excel_data).decode('utf-8')

    if 'reconciliation_state' in st.session_state:
        session_data['data']['reconciliation_state'] = st.session_state.reconciliation_state

    if 'analysis_complete' in st.session_state:
        session_data['data']['analysis_complete'] = st.session_state.analysis_complete

    # Save to file
    session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")
    with open(session_file, 'w') as f:
        json.dump(session_data, f)

    return session_id


def auto_load_session(session_id: str) -> bool:
    """
    Automatically load session from server file.
    Returns True if successful, False otherwise.
    """
    try:
        session_file = os.path.join(SESSIONS_DIR, f"{session_id}.json")

        if not os.path.exists(session_file):
            return False

        with open(session_file, 'r') as f:
            session_data = json.load(f)

        # Verify version
        if 'version' not in session_data or 'data' not in session_data:
            return False

        data = session_data['data']

        # Restore all session state
        if 'classification_df' in data:
            st.session_state.classification_df = pd.read_json(io.StringIO(data['classification_df']), orient='split')

        if 'tb_merged' in data:
            st.session_state.tb_merged = pd.read_json(io.StringIO(data['tb_merged']), orient='split')

        if 'classification_result' in data:
            st.session_state.classification_result = data['classification_result']

        if 'reconciliation_result' in data:
            st.session_state.reconciliation_result = data['reconciliation_result']

        if 'excel_output' in data:
            st.session_state.excel_output = base64.b64decode(data['excel_output'].encode('utf-8'))

        if 'reconciliation_state' in data:
            st.session_state.reconciliation_state = data['reconciliation_state']

        if 'analysis_complete' in data:
            st.session_state.analysis_complete = data['analysis_complete']
        else:
            st.session_state.analysis_complete = True

        return True

    except Exception as e:
        st.error(f"Error loading session: {str(e)}")
        return False


def cleanup_old_sessions(days: int = 7):
    """
    Delete session files older than specified days.
    """
    try:
        ensure_sessions_dir()
        cutoff_date = datetime.now() - timedelta(days=days)

        for session_file in glob.glob(os.path.join(SESSIONS_DIR, "session_*.json")):
            file_time = datetime.fromtimestamp(os.path.getmtime(session_file))
            if file_time < cutoff_date:
                os.remove(session_file)
    except Exception:
        pass  # Silently fail - cleanup is not critical


def get_session_id_from_url() -> Optional[str]:
    """
    Get session ID from URL query parameters.
    """
    try:
        query_params = st.query_params
        # Handle both dict-like access and attribute access
        if hasattr(query_params, 'get'):
            return query_params.get('session_id', None)
        elif 'session_id' in query_params:
            return query_params['session_id']
        else:
            return None
    except Exception:
        return None


def set_session_id_in_url(session_id: str):
    """
    Add session ID to URL query parameters.
    """
    try:
        st.query_params['session_id'] = session_id
    except Exception:
        pass  # Silently fail if query params not supported
