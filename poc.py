import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
import pandas as pd

# Load secrets
cred_dict = st.secrets["firebase"].copy()  # make a copy

# Fix private_key newlines
cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

# Initialize Firebase app
if not firebase_admin._apps:
    cred = credentials.Certificate(cred_dict)
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------------- FETCH FIRESTORE DATA ----------------------
def fetch_transactions():
    transactions_ref = db.collection("transactions")
    docs = transactions_ref.stream()

    transactions = []
    for doc in docs:
        data = doc.to_dict()
        if "result" in data:
            result = data["result"]
            tx = {
                "hash": result.get("hash"),
                "from": result.get("from"),
                "to": result.get("to"),
                "value": float(result.get("value", 0)),
                "time": result.get("readable_time"),
                "success": data.get("status", "0"),
                "tokenTransfers": result.get("tokenTransfers", [])
            }
            transactions.append(tx)
    return transactions

# ---------------------- FETCH ORGANIZATION NAME ----------------------
def get_org_name(wallet_address):
    org_ref = db.collection("organizations").document(wallet_address)
    doc = org_ref.get()
    if doc.exists:
        return doc.to_dict().get("name", "Dummy")
    return "Dummy"

# ---------------------- COMPUTE SUMMARY BY SENDING WALLET ----------------------
def compute_sender_summary(transactions):
    sender_summary = {}
    for tx in transactions:
        sender = tx["from"]
        if sender not in sender_summary:
            sender_summary[sender] = {
                "transactions": [],
                "total_value": 0,
                "total_credits": 0
            }
        sender_summary[sender]["transactions"].append(tx)
        sender_summary[sender]["total_value"] += tx["value"]
        for t in tx["tokenTransfers"]:
            sender_summary[sender]["total_credits"] += t.get("amount", 0)
    return sender_summary

# ---------------------- STREAMLIT UI ----------------------
st.set_page_config(page_title="🌱 GreenChain Audit Dashboard", layout="wide")

st.title("🌿 GreenChain Audit Dashboard")
st.write("Track and verify blockchain transactions for carbon credit purchases.")

transactions = fetch_transactions()

if not transactions:
    st.warning("No transactions found in Firestore.")
else:
    summary = compute_sender_summary(transactions)
    st.subheader("📊 Sending Wallet Transactions Overview")

    for sender_wallet, data in summary.items():
        org_name = get_org_name(sender_wallet)

        with st.form(key=f"form_{sender_wallet}"):
            st.write(f"### 🏢 {org_name}")
            st.caption(f"Sending Wallet: `{sender_wallet}`")

            # Table now shows "To" addresses for each transaction
            tx_df = pd.DataFrame([
                {
                    "Txn Hash": tx["hash"],
                    "To": tx["to"],
                    "Value (ETH)": tx["value"],
                    "Time": tx["time"],
                    "Success": tx["success"],
                    "Credits (CC)": sum(t.get("amount", 0) for t in tx["tokenTransfers"])
                }
                for tx in data["transactions"]
            ])

            st.dataframe(tx_df, use_container_width=True, hide_index=True)

            # Balances correspond to sending wallet
            st.write("**💰 Total Crypto Spent:**", data["total_value"])
            st.write("**🌍 Total Carbon Credits Purchased:**", data["total_credits"])
            st.write(f"**🧾 Net Summary:** {data['total_credits']} CC for {data['total_value']} ETH")

            approve_button = st.form_submit_button("✅ Approve", use_container_width=True)
            if approve_button:
                st.success(f"Approved transactions for {org_name} ({sender_wallet})")
