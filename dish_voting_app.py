import streamlit as st
import pandas as pd
import uuid
import io
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json

st.set_page_config(page_title="Group Meal Planner", layout="wide")
st.title("🍽️ Group Meal Planner")

# Set up Google Sheets connection
def get_gsheet_connection():
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    credentials = ServiceAccountCredentials.from_json_keyfile_dict(st.secrets["gcp_service_account"], scope)
    client = gspread.authorize(credentials)
    return client

# Load or create sheets
client = get_gsheet_connection()
sheet = client.open("Group Meal Planner")
dishes_ws = sheet.worksheet("dishes")
votes_ws = sheet.worksheet("votes")
ing_ws = sheet.worksheet("ingredients")

# Phase state
if "phase" not in st.session_state:
    st.session_state.phase = "submit"

# Helper functions for Google Sheets
def load_dishes():
    try:
        data = dishes_ws.get_all_records()
        return data
    except:
        return []

def add_dish(name, type):
    dishes_ws.append_row([str(uuid.uuid4()), name, type])

def delete_dish_by_name(name):
    all_rows = dishes_ws.get_all_values()
    headers = all_rows[0]
    new_rows = [row for row in all_rows[1:] if len(row) < 2 or row[1].strip().lower() != name.strip().lower()]

    # Clear the sheet and re-upload
    dishes_ws.clear()
    dishes_ws.append_row(headers)
    for row in new_rows:
        row = row + [""] * (len(headers) - len(row))
        dishes_ws.append_row(row)

def load_votes():
    data = votes_ws.get_all_records()
    return {row['dish']: row['votes'] for row in data}

def submit_votes(selected):
    votes = load_votes()
    for dish in selected:
        votes[dish] = votes.get(dish, 0) + 1
    votes_ws.clear()
    votes_ws.append_row(["dish", "votes"])
    for dish, count in votes.items():
        votes_ws.append_row([dish, count])

def load_top_dishes():
    votes = load_votes()
    sorted_votes = sorted(votes.items(), key=lambda x: x[1], reverse=True)
    return [dish for dish, _ in sorted_votes[:6]]

def add_ingredient(dish, name, qty, unit):
    ing_ws.append_row([dish, name, qty, unit])

def load_ingredients():
    return ing_ws.get_all_records()

# Navigation helper
def nav_buttons(prev_phase=None, next_phase=None):
    cols = st.columns([1, 5, 1])
    if prev_phase:
        if cols[0].button("⬅️ Back"):
            st.session_state.phase = prev_phase
            st.rerun()
    if next_phase:
        if cols[2].button("Next ➡️"):
            st.session_state.phase = next_phase
            st.rerun()

# Layout container
outer_left, main_col, outer_right = st.columns([1, 4, 1])
with main_col:

    # Step 1: Submit dishes
    if st.session_state.phase == "submit":
        st.header("Step 1: Submit your dishes")
        with st.form("dish_form"):
            dish_name = st.text_input("Dish name")
            dish_type = st.selectbox("Dietary type", ["Vegan", "Vegetarian", "Carnivore"])
            submitted = st.form_submit_button("Add dish")
            if submitted and dish_name:
                add_dish(dish_name, dish_type)
                st.success(f"Added: {dish_name} ({dish_type})")

        current_dishes = load_dishes()
        if current_dishes:
            st.subheader("Current proposed dishes")
            used_keys = set()
            for i, d in enumerate(current_dishes):
                name = d.get('name', f'Unnamed {i}')
                type_ = d.get('type', 'Unknown')
                key = f"delete_{name}_{i}"
                if key in used_keys:
                    key = f"delete_{name}_{i}_{uuid.uuid4()}"
                used_keys.add(key)
                col1, col2 = st.columns([0.85, 0.15])
                with col1:
                    st.markdown(f"- {name} ({type_})")
                with col2:
                    if st.button("🗑️", key=key, help="Delete dish"):
                        delete_dish_by_name(name)
                        st.rerun()

        nav_buttons(next_phase="vote")

    # Step 2: Vote for dishes
    elif st.session_state.phase == "vote":
        st.header("Step 2: Vote for dishes you like")
        st.write("You can vote for as many dishes as you want.")
        dish_names = [d['name'] for d in load_dishes() if 'name' in d]
        with st.form("vote_form"):
            selected = st.multiselect("Select your favorite dishes:", dish_names)
            voted = st.form_submit_button("Submit votes")
            if voted:
                submit_votes(selected)
                st.success("Votes submitted!")

        nav_buttons(prev_phase="submit", next_phase="select")

    # Step 3: Show top dishes
    elif st.session_state.phase == "select":
        st.header("Step 3: Top voted dishes")
        votes = load_votes()
        vote_df = pd.DataFrame([{"Dish": k, "Votes": v} for k, v in votes.items()])
        vote_df = vote_df.sort_values("Votes", ascending=False)
        st.dataframe(vote_df)

        top_dishes = load_top_dishes()
        st.session_state.top_dishes = top_dishes

        st.markdown("### Selected dishes:")
        for dish in top_dishes:
            st.markdown(f"- {dish}")

        nav_buttons(prev_phase="vote", next_phase="ingredients")

    # Step 4: Add ingredients
    elif st.session_state.phase == "ingredients":
        st.header("Step 4: Add ingredients or link to a recipe")
        for dish in st.session_state.top_dishes:
            st.subheader(f"Ingredients for {dish}")
            with st.form(f"ingredients_{dish}"):
                recipe_url = st.text_input("Optional: Link to full recipe", key=f"url_{dish}")
                ing_name = st.text_input("Ingredient name", key=f"ing_{dish}")
                ing_qty = st.number_input("Total amount needed", min_value=0.0, step=0.1, key=f"qty_{dish}")
                ing_unit = st.text_input("Unit (e.g. grams, units, cups)", key=f"unit_{dish}")
                added = st.form_submit_button("Add ingredient")
                if added and ing_name and ing_unit:
                    add_ingredient(dish, ing_name, ing_qty, ing_unit)
                    st.success(f"Added {ing_name} to {dish}")

        nav_buttons(prev_phase="select", next_phase="shopping")

    # Step 5: Generate shopping list
    elif st.session_state.phase == "shopping":
        st.header("Step 5: Shopping list")
        df = pd.DataFrame(load_ingredients())
        shopping = df.groupby(["name", "unit"])["qty"].sum().reset_index()
        shopping = shopping.rename(columns={"name": "Ingredient", "unit": "Unit", "qty": "Total Quantity"})

        st.dataframe(shopping)

        # Export to Excel
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            shopping.to_excel(writer, index=False, sheet_name='Shopping List')
            writer.save()
        st.download_button(
            label="Download shopping list as Excel",
            data=output.getvalue(),
            file_name="shopping_list.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.markdown("---")
        if st.button("🔁 Reset all and start over"):
            st.session_state.clear()
            dishes_ws.clear()
            votes_ws.clear()
            ing_ws.clear()
            dishes_ws.append_row(["id", "name", "type"])
            votes_ws.append_row(["dish", "votes"])
            ing_ws.append_row(["dish", "name", "qty", "unit"])
            st.rerun()

        nav_buttons(prev_phase="ingredients")
