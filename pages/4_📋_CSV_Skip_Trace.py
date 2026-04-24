"""
CSV Skip-Trace Upload Page
==========================
Upload a CSV (or Excel) file of owner names and mailing addresses, run the
existing skip-tracing pipeline on every row, watch live progress, and download
the enriched results.
"""

from __future__ import annotations

import traceback
import tempfile
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="CSV Skip-Trace",
    page_icon="📋",
    layout="wide",
    initial_sidebar_state="expanded",
)

try:
    import googlesearch  # noqa: F401
except ImportError:
    st.error(
        "❌ Missing dependency: `googlesearch-python` is not installed.\n\n"
        "Run this in PowerShell then restart Streamlit:\n"
        "```\npip install googlesearch-python\n```"
    )
    st.stop()


def _load_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Read an uploaded CSV or Excel file into a DataFrame."""
    name = uploaded_file.name.lower()
    if name.endswith(".xlsx") or name.endswith(".xls"):
        return pd.read_excel(uploaded_file, dtype=str)
    return pd.read_csv(uploaded_file, dtype=str, encoding_errors="replace")


def _detect_columns(df: pd.DataFrame) -> tuple[Optional[str], Optional[str]]:
    """Return (name_col, address_col) by simple case-insensitive keyword matching."""
    _NAME_KEYWORDS = {
        "owner name", "owner", "name", "grantor", "taxpayer", "llc name",
        "owner 1", "owner1", "primary owner", "mailing name",
    }
    _ADDR_KEYWORDS = {
        "mailing address", "mail address", "mailing addr", "address", "addr",
        "mail addr", "owner address", "correspondence address", "contact address",
    }

    cols_lower = {c: c.lower() for c in df.columns}
    name_col = next((c for c, low in cols_lower.items() if low in _NAME_KEYWORDS), None)
    addr_col = next((c for c, low in cols_lower.items() if low in _ADDR_KEYWORDS), None)
    return name_col, addr_col


def _clean_df_with_cleaner(
    uploaded_file,
    name_col: str,
    address_col: str,
) -> pd.DataFrame:
    """Save uploaded file to a temp path and run CSVCleaner.load_and_clean()."""
    from utils.csv_cleaner import CSVCleaner  # noqa: PLC0415

    suffix = Path(uploaded_file.name).suffix or ".csv"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    cleaner = CSVCleaner(name_col=name_col, address_col=address_col)
    return cleaner.load_and_clean(tmp_path)


def main():
    st.title("CSV Skip-Trace Upload")
    st.success("✅ Production")
    st.markdown(
        "Upload a CSV or Excel file containing **owner names** and "
        "**mailing addresses**. The pipeline will skip-trace each owner and "
        "return **phone numbers** and **email addresses** where available."
    )

    st.divider()

    # ── 1. File upload ──────────────────────────────────────────────────────
    uploaded = st.file_uploader(
        "Upload owner list",
        type=["csv", "xlsx"],
        help="CSV or Excel file with at least an owner-name column and a mailing-address column.",
    )

    if uploaded is None:
        st.info("👆 Upload a CSV or Excel file to get started.")
        return

    try:
        raw_df = _load_uploaded_file(uploaded)
    except Exception as exc:
        st.error(f"Could not read the uploaded file: {exc}")
        return

    if raw_df.empty:
        st.warning("The uploaded file appears to be empty.")
        return

    st.subheader("Preview (first 5 rows)")
    st.dataframe(raw_df.head(5), use_container_width=True)

    cols = raw_df.columns.tolist()

    # ── 2. Column mapping ───────────────────────────────────────────────────
    st.subheader("Column Mapping")

    auto_name, auto_addr = _detect_columns(raw_df)

    use_auto = st.checkbox(
        "Auto-detect columns (recommended)",
        value=True,
        help="Uses fuzzy matching to find the name and address columns automatically.",
    )

    if use_auto:
        if auto_name and auto_addr:
            st.success(
                f"✅ Detected name column: **{auto_name}** | "
                f"address column: **{auto_addr}**"
            )
            name_col = auto_name
            addr_col = auto_addr
        else:
            st.warning(
                "Auto-detection could not identify both columns. "
                "Please select them manually below."
            )
            use_auto = False

    if not use_auto:
        col_l, col_r = st.columns(2)
        with col_l:
            name_col = st.selectbox(
                "Owner Name column",
                options=cols,
                index=cols.index(auto_name) if auto_name and auto_name in cols else 0,
            )
        with col_r:
            addr_col = st.selectbox(
                "Mailing Address column",
                options=cols,
                index=cols.index(auto_addr) if auto_addr and auto_addr in cols else 0,
            )

    # ── 3. Settings ─────────────────────────────────────────────────────────
    st.subheader("Settings")
    max_owners = st.number_input(
        "Max owners to skip-trace",
        min_value=1,
        max_value=656,
        value=100,
        step=10,
        help="How many unique owner names to process from the uploaded file.",
    )
    st.warning(
        "⚠️ Google rate-limiting may occur on large batches. "
        "For best results, run in chunks of **50–100 owners** at a time."
    )

    st.divider()

    # ── 4. Run button ────────────────────────────────────────────────────────
    run = st.button("▶ Start Skip-Trace", type="primary")

    if not run:
        return

    # ── 5. Execute pipeline ──────────────────────────────────────────────────
    try:
        from skip_tracing.phone_scraper import PhoneScraper  # noqa: PLC0415
        from skip_tracing.google_dorking import GoogleDorker  # noqa: PLC0415
    except ImportError as exc:
        st.error(
            f"Import error — a required dependency may be missing.\n\n"
            f"```\n{traceback.format_exc()}\n```\n\n"
            f"Try: `pip install rapidfuzz`\n\nError: {exc}"
        )
        return

    try:
        cleaned = _clean_df_with_cleaner(uploaded, name_col, addr_col)
    except Exception as exc:
        st.error(f"Column cleaning failed:\n\n```\n{traceback.format_exc()}\n```")
        return

    # De-duplicate by Owner Name, keep first occurrence
    cleaned = cleaned.drop_duplicates(subset=["Owner Name"]).reset_index(drop=True)
    cleaned = cleaned.head(int(max_owners))

    total = len(cleaned)
    if total == 0:
        st.warning("No owners found after cleaning. Check the column mapping.")
        return

    st.info(f"Processing **{total}** unique owners…")

    phone_scraper = PhoneScraper()
    dorker = GoogleDorker()

    results: list[dict] = []
    progress_bar = st.progress(0)
    status_line = st.empty()
    _any_rate_limited = False
    _sample_queries: list[str] = []

    _rate_limit_msg = (
        "⚠️ Google rate-limited after **{n}** owners. "
        "Stopping early — results so far are available below."
    )

    try:
        for i, row in enumerate(cleaned.itertuples(index=False), start=1):
            owner = getattr(row, "Owner Name", "")
            address = getattr(row, "Mailing Address", "")

            status_line.markdown(f"**[{i}/{total}]** Skip-tracing: `{owner}`")
            progress_bar.progress(i / total)

            phone_result = phone_scraper.lookup(owner, address)
            if phone_result.get("rate_limited"):
                _any_rate_limited = True
                st.warning(_rate_limit_msg.format(n=i - 1))
                break

            dork_result = dorker.search(owner)
            if dork_result.get("rate_limited"):
                _any_rate_limited = True
                st.warning(_rate_limit_msg.format(n=i - 1))
                break

            # Capture sample queries for the first owner only
            if i == 1:
                _sample_queries = dork_result.get("queries", [])

            results.append(
                {
                    "Owner Name": owner,
                    "Mailing Address": address,
                    "Phones": "; ".join(phone_result.get("phones", [])),
                    "Emails": "; ".join(dork_result.get("emails", [])),
                    "LinkedIn": "; ".join(dork_result.get("linkedin", [])),
                }
            )

        status_line.empty()
        progress_bar.progress(1.0)

    except Exception:
        st.error(f"An error occurred during skip-tracing:\n\n```\n{traceback.format_exc()}\n```")
        return

    # ── 6. Results table ─────────────────────────────────────────────────────
    if not results:
        st.info("No results were collected (the run may have been rate-limited immediately).")
        return

    results_df = pd.DataFrame(
        results,
        columns=["Owner Name", "Mailing Address", "Phones", "Emails", "LinkedIn"],
    )

    st.divider()
    st.subheader("Results")

    total_rows = len(results_df)
    phones_found = results_df["Phones"].ne("").sum()
    emails_found = results_df["Emails"].ne("").sum()

    m1, m2, m3 = st.columns(3)
    m1.metric("Owners processed", total_rows)
    m2.metric("With phone numbers", phones_found)
    m3.metric("With emails", emails_found)

    # ── Diagnostics (shown when 0 phones and 0 emails) ────────────────────────
    if phones_found == 0 and emails_found == 0:
        with st.expander("🔍 Diagnostics — why are results empty?", expanded=True):
            try:
                import googlesearch as _gs  # noqa: F401
                st.success("✅ `googlesearch-python` is installed.")
            except ImportError:
                st.error(
                    "❌ `googlesearch-python` is **not** installed. "
                    "Run `pip install googlesearch-python` and restart Streamlit."
                )

            if _any_rate_limited:
                st.warning(
                    "⚠️ **Rate-limiting detected** — Google blocked the automated "
                    "search session before results could be collected."
                )
            else:
                st.info(
                    "No rate-limiting was explicitly detected, but Google may still "
                    "be silently returning empty results for automated queries."
                )

            if _sample_queries:
                st.markdown("**Sample queries fired for the first owner:**")
                for q in _sample_queries:
                    st.code(q, language=None)
            else:
                st.info("No queries were recorded (the run may have been blocked immediately).")

            st.info(
                "💡 **Advice:** Google frequently blocks automated searches. "
                "Try running a smaller batch (10–20 owners) or waiting 30 minutes "
                "between runs. You can also try the run again at a different time of day."
            )

    st.dataframe(results_df, use_container_width=True)

    # ── 7. Download button ────────────────────────────────────────────────────
    csv_bytes = results_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download enriched CSV",
        data=csv_bytes,
        file_name="skip_traced_results.csv",
        mime="text/csv",
    )


if __name__ == "__main__":
    main()
