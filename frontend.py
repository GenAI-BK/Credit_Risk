import re
import sqlite3
from openai import OpenAI
import fitz  # PyMuPDF
from PIL import Image
import io
from docx import Document
import streamlit as st

llm=OpenAI(api_key=st.secrets["OPENAI_API_KEY"])

st.title("Credit Risk Analysis")

borrower = st.text_input("Enter Borrower's Name")
loan_amount = st.text_input("Enter Requested loan amount")
purpose = st.text_input("Enter Loan Purpose")
credit_score = st.text_input("Enter Credit score")
tenure = st.number_input("Enter the requested tenure for the amount in years")
bank_statement = st.file_uploader("Upload Bank Statements", "DOCX")
credit_statement = st.file_uploader("Upload Credit card statement (Optional)", "DOCX")
bank_account_type = st.selectbox("Select Account Type", ("Savings Account", "Current Account", "Salaried Account"))
income_proof = st.selectbox("Select Income Proof", ("Offer Letter", "Salary slips"))
selected_income_proof = st.file_uploader("Upload Income proof", "DOCX")
assets_info = st.file_uploader("Upload Assets Information", "DOCX")
debts_info = st.file_uploader("Upload Debts Information", "DOCX")

def extract_text_and_images_from_pdf(pdfpath):
    doc = fitz.open(pdfpath)
    text = ""

    for page_number in range(len(doc)):
        page = doc.load_page(page_number)
        page_text = page.get_text()
        text += page_text

        image_list = page.get_images(full=True)
        for img_index, img in enumerate(image_list, start=1):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            image_ext = base_image["ext"]
            image_pil = Image.open(io.BytesIO(image_bytes))
            text += perform_ocr(image_pil)

    return text

def perform_ocr(image):
    try:
        # Convert the image to text using a placeholder prompt (adjust as needed)
        result = llm.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "system", "content": "You are an OCR expert."},
                {"role": "user", "content": "Extract all text from this image."}
            ],
            max_tokens=1000,
        )
        return result.choices[0].message.content
    except Exception as e:
        return "\n"

def read_doc(doc_file):
    doc = Document(doc_file)
    full_text = []
    for paragraph in doc.paragraphs:
        full_text.append(paragraph.text)
    return '\n'.join(full_text)

def process_document(document_text, document_type, prompt):
    response = llm.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": f"You are a financial expert analyzing a {document_type}."},
            {"role": "user", "content": f"Document Type: {document_type}\nDocument Text: {document_text}. \
            {prompt}"}
        ],
    )
    return response.choices[0].message.content

def credit_risk(bank_statement_data, credit_card_data, income_data, assets_data, debts_data):
    response = llm.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a financial expert analyzing credit risk."},
            {"role": "user", "content": f'''
            Bank Statement: {bank_statement_data}
            Credit card Statement: {credit_card_data}
            Proof Of income  ({selected_income_proof}): {income_data}
            Assets: {assets_data}
            Current outstanding debts and Monthly payments for those Debts: {debts_data}
            Credit Score: {credit_score}
            Loan Amount: {loan_amount}
            Loan Purpose: {purpose}
            Loan Tenure: {tenure} years
            Bank Account Type: {bank_account_type}

            Calculate the exposure at default(EAD) (EAD for any loan is the requested loan amount) \
            Assume no potential future drawdowns for simplicity. Once EAD is calculated, \
            calculate Loss Given default(LGD) (taking total assets value in consideration) and \
            Probability of Default(PD)(taking credit score into consideration) in percentage. \
            Calculate expected Loss by multiplying EAD x LGD x PD.
            Also calculate current monthly Debt-to-income ratio and Debt-to-income ratio if the loan is approved\
            and perform a credit risk analysis\. For any of the numbers, do not put ',(commas)' in between
            Based on the given information, Analyze the credit risk and return the response in following format:
            "Borrower's Name: {borrower}"
            "EAD:"   
            "LGD:"
            "PD:"
            "Expected Loss = PD x LGD x EAD:"
            "Present DTI:"
            "DTI if approved:"
            "Positive Indicators:"
            "Risk Factors:"
            "Conclusion:"
            "Tips/Further Steps:"
            '''}
        ],
    )
    return response.choices[0].message.content

def parse_response(response):
    data = {}
    patterns = {
        'EAD': r'EAD\s*:\s*(.*)',
        'LGD': r'LGD\s*:\s*(.*)',
        'PD': r'PD\s*:\s*(.*)',
        'Expected Loss': r'Expected Loss\s*=\s*PD x LGD x EAD\s*:\s*(.*?)(\d+)(?:\D|$)',
        'Positive Indicators': r'Positive Indicators\s*:\s*(.*?)\n(Risk Factors|$)',
        'Risk Factors': r'Risk Factors\s*:\s*(.*?)\n(Conclusion|$)',
        'Conclusion': r'Conclusion\s*:\s*(.*)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, response, re.DOTALL)
        if match:
            value = match.group(1).strip()
            cleaned_value = value.replace('*', '').replace('\n', ' ').strip()
            if key == 'Expected Loss':
                data[key] = match.group(2).strip()
            elif key in ['EAD', 'LGD', 'PD']:
                data[key] = re.findall(r"[-+]?\d*\.\d+|\d+", cleaned_value)[0]
            else:
                data[key] = cleaned_value
        else:
            data[key] = None
    
    return data

def save_to_database(data):
    conn = sqlite3.connect('credit_risk.db')
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS credit_risk_analysis (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        PD TEXT,
                        EAD TEXT,
                        LGD TEXT,
                        Expected_Loss TEXT,
                        Positive_Indicators TEXT,
                        Risk_Factors TEXT,
                        Conclusion TEXT)''')
    cursor.execute('''INSERT INTO credit_risk_analysis (PD, EAD, LGD, Expected_Loss, Positive_Indicators, Risk_Factors, Conclusion)
                      VALUES (?, ?, ?, ?, ?, ?, ?)''', 
                      (data['PD'], data['EAD'], data['LGD'], data['Expected Loss'], data['Positive Indicators'], data['Risk Factors'], data['Conclusion']))
    conn.commit()
    conn.close()

if st.button("Evaluate risk"):  
    if bank_statement and selected_income_proof and assets_info and debts_info:
        bank_statement_data = read_doc(bank_statement)

        credit_card_data = read_doc(credit_statement) if credit_statement else ""

        income_data = read_doc(selected_income_proof)
        income_result = process_document(income_data, 'Income Proof', 'Summarize the document and return the monthly income')

        assets_data = read_doc(assets_info)
        assets_result = process_document(assets_data, "Assets Information", 'Calculate the total value of assets')

        debts_data = read_doc(debts_info)
        debts_result = process_document(debts_data, "Debts Information", 'Summarize the monthly debt payment and total debt amount and return in bullet points')
        print(debts_result)

        ans = credit_risk(bank_statement_data, credit_card_data, income_result, assets_result, debts_result)
        st.write(ans)
        data = parse_response(ans)
        save_to_database(data)  
    else:
        st.error("Please upload all required documents.")
