import google.generativeai as genai
import os
import fitz # PyMuPDF
from PIL import Image
import io
from docx import Document
import streamlit as st

api_key = st.secrets["GOOGLE_API_KEY"]
bank_statement=st.file_uploader("Upload Bank Statements", "PDF")
# pdf_path="C:/Users/jugal.gurnani/Downloads/credit_risk/images_merged.pdf"
bank_account_type=st.selectbox("Select Account Type",("Savings Account", "Current Account", "Salaried Account"))
income_proof=st.selectbox("Select Income Proof",("Offer Letter", "Salary slips"))
selected_income_proof=st.file_uploader("Upload Income proof", "DOCX")
assets_info=st.file_uploader("Uplaod Assets Information", "DOCX")
debts_info=st.file_uploader("Upload Debts Information")
# offer_letter=read_doc(doc_file="C:/Users/jugal.gurnani/Downloads/credit_risk/Olivia_Offer_Letter.docx")
# asset_info=read_doc(doc_file="C:/Users/jugal.gurnani/Downloads/credit_risk/Olivia_Williams_Assets.docx")
# debts_info=read_doc(doc_file="C:/Users/jugal.gurnani/Downloads/credit_risk/Olivia_Williams_Debts.docx")
credit_score=st.text_input("Enter Credit score")
loan_amount=st.text_input("Enter Requested loan amount")
tenure=st.number_input("Enter the requested tenure for the amount in years")

genai.configure(api_key=api_key)
client=genai.GenerativeModel("gemini-1.5-flash")



def extract_images_from_pdf(pdfpath):
    doc = fitz.open(pdfpath)  # Open the PDF file

    # Initialize a list to store all images for concatenation
    text=""

    for page_number in range(len(doc)):  # Iterate through each page
        page = doc.load_page(page_number)
        image_list = page.get_images(full=True) # Get a list of all images on the page

        for img_index, img in enumerate(image_list, start=1):
            xref = img[0]  # The XREF of the image
            base_image = doc.extract_image(xref)  # Extract the image information
            image_bytes = base_image["image"]  # The image bytes
            image_ext = base_image["ext"]  # The image extension
            image_pil = Image.open(io.BytesIO(image_bytes))
            text+=perform_ocr(image_pil)
    return text

def perform_ocr(image):
    try:
        result=client.generate_content(
            ["Perform OCR on the given image and extract every peice of text from the image.\
            If you see nothing in the image, just return back '''Blank Page''' ", "\n\n", image],
        )

        return result.text
    except ValueError:
        return "\n"

def read_doc(doc_file):
    doc=Document(doc_file)
    full_text=[]
    for paragraph in doc.paragraphs:
        full_text.append(paragraph.text)
    return '\n'.join(full_text)

llm=genai.GenerativeModel(model_name="gemini-1.5-pro", system_instruction="You are a financial expert, \
                        your task is to analyze through the provided bank statements, income proof, assets and debts\
                        and analyze risk in crediting a loan by calculating 'Probability of Default (PD)', \
                        'Loss Given Default(LGD)', 'Exposure at default(EAD)' . Also suggest, if the loan \
                        should be passed, at what interest rate should it be passed to minimize credit risk.")

def credit_risk(final_text, income, assets, debts):
    response=llm.generate_content(
        [f'''The given context contains bank statement of a customer for last 6 months and {income_proof}\
        as a proof of income. The bank account type is {bank_account_type} and the\
        loan amount asked for is {loan_amount} for Car Loan for {tenure} years Tenure. Calculate the exposure at default(EAD) by looking at the debts \
        Assume no potential future drawdowns for simplicity. Once EAD is calculated, calculate Loss Given default(LGD)\
        and Probability of Default(PD). Calculate expected Loss by multiplying EAD x LGD x PD
        Also, perform a credit risk analysis\
        Credit Score:{credit_score}\
        Based on the given information, Analyze the credit risk and return the response in following format:\
        "EAD"
        "LGD"
        "PD"
        "Expected Loss = PD x LGD x EAD:"
        "Positive Indicators"
        "Risk Factors"
        "Conclusion"
        "Tips/Further Steps"
        Bank Statement: {final_text}
        Proof Of income ({income_proof}): {income}
        Assets: {assets}
        Current outstanding debts and Monthly payments for those Debts: {debts} ''']
    )
    return response.text

if st.button("Generate Report"):
    if bank_statement and selected_income_proof and assets_info and debts_info:
        final_text = extract_images_from_pdf(pdfpath=bank_statement)
        income = read_doc(selected_income_proof)
        assets = read_doc(assets_info)
        debts = read_doc(debts_info)
        ans = credit_risk(final_text, income, assets, debts)
        st.write(ans)
    else:
        st.error("Please upload all required documents.")