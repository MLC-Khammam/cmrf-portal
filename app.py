import streamlit as st
import json
import gspread
from google.oauth2.service_account import Credentials
from google import genai
from google.genai import types

# --- PAGE CONFIG ---
st.set_page_config(page_title="CMRF Application Portal", page_icon="📑", layout="wide")

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

USERS = {
    "admin": {"password": "adminpassword123", "role": "admin", "approved": True},
    "staff1": {"password": "staffpassword123", "role": "staff", "approved": True}
}

def init_session():
    if "logged_in" not in st.session_state:
        st.session_state["logged_in"] = False
        st.session_state["username"] = ""
        st.session_state["role"] = ""

init_session()

def login_page():
    st.title("🏛️ MLC Office - CMRF Application Portal")
    tab1, tab2 = st.tabs(["Login", "Register Staff"])
    
    with tab1:
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        if st.button("Login", type="primary"):
            user = USERS.get(username)
            if user and user["password"] == password:
                if user["approved"]:
                    st.session_state["logged_in"] = True
                    st.session_state["username"] = username
                    st.session_state["role"] = user["role"]
                    st.success("Login Successful!")
                    st.rerun()
                else:
                    st.error("Your account is pending Admin approval.")
            else:
                st.error("Invalid Username or Password.")

    with tab2:
        new_user = st.text_input("New Username")
        new_pass = st.text_input("New Password", type="password")
        if st.button("Request Access"):
            if new_user in USERS:
                st.warning("Username already exists.")
            elif new_user and new_pass:
                USERS[new_user] = {"password": new_pass, "role": "staff", "approved": False}
                st.info("Registration requested.")

def extract_cmrf_pdf_data(pdf_file, api_key):
    """Extracts CMRF data using Gemini 2.0 Flash."""
    client = genai.Client(api_key=api_key)
    pdf_bytes = pdf_file.read()
    
    prompt = """
    Extract all details from this Telangana CMRF Application form accurately into JSON.
    Return ONLY a raw JSON object with these exact keys:
    {
      "token_no": "CMRF Token Number",
      "applicant_name": "Applicant Name",
      "age": "Age",
      "gender": "Gender",
      "aadhaar": "Aadhaar Number",
      "mobile": "Mobile Number",
      "district": "District",
      "mandal": "Mandal",
      "village": "Village",
      "pincode": "Pincode",
      "address": "Address",
      "ration_card": "FSC Number / Ration Card",
      "bank_name": "Bank Name",
      "account_no": "Account Number",
      "ifsc": "IFSC",
      "branch": "Branch",
      "recommended_by": "Recommended By",
      "letter_date": "Letter Date",
      "hospital_name": "Hospital Name (Extract hospital name ONLY, e.g. KHIMS HOSPITAL)",
      "bill_amount": "Bill Amount"
    }
    """

    # Primary active model IDs in google-genai SDK
    candidate_models = ["gemini-2.0-flash", "gemini-1.5-flash"]
    response_text = None
    last_error = None

    for model_name in candidate_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=[
                    types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
                    prompt
                ],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            response_text = response.text
            if response_text:
                break
        except Exception as e:
            last_error = str(e)
            continue

    if not response_text:
        raise Exception(f"Gemini API Error: {last_error}")

    return json.loads(response_text)

def append_to_google_sheet(data_row):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=scope
        )
        client = gspread.authorize(creds)
        sheet = client.open("CMRF_Applications_Master").sheet1
        sheet.append_row(data_row)
        return True, "Successfully written to Google Sheets!"
    except Exception as e:
        return False, str(e)

def main_app():
    st.sidebar.title(f"Logged in as: {st.session_state['username'].capitalize()}")
    
    api_key = GEMINI_API_KEY
    if not api_key:
        api_key = st.sidebar.text_input("Enter Gemini API Key", type="password")

    if st.sidebar.button("Logout"):
        st.session_state["logged_in"] = False
        st.rerun()

    st.title("📋 CMRF Data Entry Portal")
    st.markdown("Upload the downloaded CMRF PDF application form to parse and push directly into Google Sheets.")
    st.divider()

    col_left, col_right = st.columns([1, 1])

    with col_left:
        st.subheader("1. Upload & Input")
        uploaded_file = st.file_uploader("Upload CMRF Application Form (PDF)", type=["pdf"])
        referring_leader = st.text_input("Referring Leader Name (Referring CMRF to MLC Office)")

    if uploaded_file and referring_leader:
        if not api_key:
            st.error("Please provide a Gemini API Key in Streamlit Secrets or sidebar.")
            return

        with st.spinner("AI parsing PDF form..."):
            try:
                extracted_data = extract_cmrf_pdf_data(uploaded_file, api_key)
                
                with col_right:
                    st.subheader("2. Extracted Data Preview")
                    st.json(extracted_data)

                st.divider()
                
                if st.button("🚀 Send Data to Google Sheets", type="primary"):
                    row = [
                        extracted_data.get("token_no", "N/A"),
                        extracted_data.get("applicant_name", "N/A"),
                        f"{extracted_data.get('age', '')} / {extracted_data.get('gender', '')}",
                        extracted_data.get("aadhaar", "N/A"),
                        extracted_data.get("mobile", "N/A"),
                        extracted_data.get("district", "N/A"),
                        extracted_data.get("mandal", "N/A"),
                        extracted_data.get("village", "N/A"),
                        extracted_data.get("address", "N/A"),
                        extracted_data.get("ration_card", "N/A"),
                        extracted_data.get("bank_name", "N/A"),
                        extracted_data.get("account_no", "N/A"),
                        extracted_data.get("ifsc", "N/A"),
                        extracted_data.get("branch", "N/A"),
                        extracted_data.get("recommended_by", "N/A"),
                        extracted_data.get("letter_date", "N/A"),
                        extracted_data.get("hospital_name", "N/A"),
                        extracted_data.get("bill_amount", "N/A"),
                        referring_leader,
                        st.session_state["username"]
                    ]
                    
                    success, msg = append_to_google_sheet(row)
                    if success:
                        st.balloons()
                        st.success(msg)
                    else:
                        st.error(f"Google Sheet Error: {msg}")

            except Exception as e:
                st.error(f"Extraction failed: {str(e)}")

    elif uploaded_file and not referring_leader:
        st.warning("⚠️ Please fill in the 'Referring Leader Name' field.")

if st.session_state["logged_in"]:
    main_app()
else:
    login_page()
