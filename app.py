import streamlit as st
import urllib.parse
import re
from datetime import date
from google import genai
import json

FORM_BASE_URL = "https://docs.google.com/forms/d/e/1FAIpQLSfRjB5LSEfQHgI3Ew4GaRaOMEjLO7k4Vq-2zzaxSlt6PyO9nA/viewform"

ENTRY_DATE     = "1365003201"
ENTRY_TIME     = "1132666168"
ENTRY_CALLTYPE = "1228861024"

ENTRY_IDS = {
    "Resident":      {"name": "1352014911", "phone": "672229889",  "address": "1378368785", "inquiry": "1074280340", "city": "520241761"},
    "Lead (Leasing)":{"name": "977848052",  "phone": "1511733965", "inquiry": "1250825539"},
    "Worker":        {"name": "1819818518", "inquiry": "519057867"},
    "Owner":         {"name": "44469820",   "inquiry": "2051184989"},
    "Other":         {"name": "703619804",  "phone": "1955131867", "inquiry": "1507646955"},
    "Emergency":     {"name": "703619804",  "phone": "1955131867", "inquiry": "1507646955"},
}

CALL_TYPES = ["Emergency", "Lead (Leasing)", "Other", "Owner", "Resident", "Worker"]


def extract_with_ai(transcript: str, api_key: str) -> dict:
    today = date.today().strftime("%m/%d/%Y")
    client = genai.Client(api_key=api_key)

    prompt = f"""You are reading a voicemail transcript. Extract the following and return ONLY valid JSON.

Today's date is {today} — use it as fallback if no date is mentioned.

Extract:
- date: MM/DD/YYYY
- hour: 1-12 (no leading zero)
- minute: two digits like 00 or 30
- ampm: AM or PM
- call_type: pick one from: Emergency, Lead (Leasing), Other, Owner, Resident, Worker
- name: caller's full name
- phone: formatted as ###-###-####
- address: full street address if mentioned
- city: city name only
- inquiry: a clear 2-4 sentence summary of why they are calling and what they need

Transcript:
{transcript}

Return only this JSON:
{{
  "date": "",
  "hour": "",
  "minute": "",
  "ampm": "",
  "call_type": "",
  "name": "",
  "phone": "",
  "address": "",
  "city": "",
  "inquiry": ""
}}"""

    response = client.models.generate_content(model="gemini-2.0-flash", contents=prompt)
    text = response.text.strip()
    match = re.search(r'\{[\s\S]+\}', text)
    if match:
        data = json.loads(match.group())
        if data.get("call_type") not in CALL_TYPES:
            data["call_type"] = "Other"
        return data
    raise ValueError("Could not parse AI response")


def build_prefill_url(info: dict) -> str:
    try:
        month, day, year = info["date"].split("/")
    except Exception:
        today = date.today()
        month, day, year = str(today.month), str(today.day), str(today.year)

    hour = int(info.get("hour", 12))
    ampm = info.get("ampm", "PM")
    if ampm == "PM" and hour != 12:
        hour += 12
    elif ampm == "AM" and hour == 12:
        hour = 0

    params = [
        ("usp", "pp_url"),
        (f"entry.{ENTRY_DATE}_year",   year),
        (f"entry.{ENTRY_DATE}_month",  str(int(month))),
        (f"entry.{ENTRY_DATE}_day",    str(int(day))),
        (f"entry.{ENTRY_TIME}_hour",   str(hour)),
        (f"entry.{ENTRY_TIME}_minute", info.get("minute", "00")),
        (f"entry.{ENTRY_CALLTYPE}",    info.get("call_type", "Other")),
    ]

    ids = ENTRY_IDS.get(info.get("call_type", "Other"), {})
    for field in ["name", "phone", "address", "city", "inquiry"]:
        if info.get(field) and field in ids:
            params.append((f"entry.{ids[field]}", info[field]))

    return FORM_BASE_URL + "?" + urllib.parse.urlencode(params)


# ── Streamlit UI ──────────────────────────────────────────────────────────────

st.set_page_config(page_title="Voicemail Form Filler", page_icon="📋", layout="centered")

st.title("📋 Voicemail Form Filler")
st.write("Paste a voicemail transcript below and we'll fill out the form for you.")

api_key = st.secrets.get("GEMINI_API_KEY", "")

transcript = st.text_area("Paste transcript here:", height=220, placeholder="Good morning, my name is...")

if st.button("Fill the Form", type="primary", disabled=not transcript.strip()):
    if not api_key:
        st.error("Gemini API key not configured. Contact your admin.")
    else:
        with st.spinner("Reading transcript..."):
            try:
                info = extract_with_ai(transcript, api_key)
            except Exception as e:
                st.error(f"Error reading transcript: {e}")
                st.stop()

        st.success("Done! Here is what was found:")

        col1, col2 = st.columns(2)
        with col1:
            info["date"]      = st.text_input("Date (MM/DD/YYYY)", value=info.get("date", ""))
            info["hour"]      = st.text_input("Hour", value=info.get("hour", "12"))
            info["minute"]    = st.text_input("Minute", value=info.get("minute", "00"))
            info["ampm"]      = st.selectbox("AM/PM", ["AM", "PM"], index=0 if info.get("ampm") == "AM" else 1)
            info["call_type"] = st.selectbox("Call Type", CALL_TYPES, index=CALL_TYPES.index(info.get("call_type", "Other")))
        with col2:
            info["name"]    = st.text_input("Name",    value=info.get("name", ""))
            info["phone"]   = st.text_input("Phone",   value=info.get("phone", ""))
            info["address"] = st.text_input("Address", value=info.get("address", ""))
            info["city"]    = st.text_input("City",    value=info.get("city", ""))

        info["inquiry"] = st.text_area("Inquiry / Summary", value=info.get("inquiry", ""), height=120)

        url = build_prefill_url(info)
        st.markdown(f"### [Click here to open the pre-filled form]({url})")
        st.caption("The form will open in a new tab with all fields already filled in. Just review and click Susunod → Isumite.")
