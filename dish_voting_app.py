import streamlit as st
import pandas as pd
import uuid
import io

st.set_page_config(page_title="Group Meal Planner", layout="centered")
st.title("🍽️ Group Meal Planner")

# Session state to keep track of app phase
if "phase" not in st.session_state:
    st.session_state.phase = "submit"
if "dishes" not in st.session_state:
    st.session_state.dishes = []
if "votes" not in st.session_state:
    st.session_state.votes = {}
if "ingredients" not in st.session_state:
    st.session_state.ingredients = []
if "num_people" not in st.session_state:
    st.session_state.num_people = 8

# Phase 1: Submit dishes
if st.session_state.phase == "submit":
    st.header("Step 1: Submit your dishes")
    with st.form("dish_form"):
        dish_name = st.text_input("Dish name")
        dish_type = st.selectbox("Dietary type", ["Vegan", "Vegetarian", "Carnivore"])
        submitted = st.form_submit_button("Add dish")
        if submitted and dish_name:
            dish_id = str(uuid.uuid4())
            st.session_state.dishes.append({"id": dish_id, "name": dish_name, "type": dish_type})
            st.success(f"Added: {dish_name} ({dish_type})")

    if st.session_state.dishes:
        st.subheader("Current proposed dishes")
        delete_dish = None
        for d in st.session_state.dishes:
            col1, col2 = st.columns([4, 1])
            with col1:
                st.markdown(f"- {d['name']} ({d['type']})")
            with col2:
                if st.button("❌", key=f"delete_{d['id']}"):
                    delete_dish = d
        if delete_dish:
            st.session_state.dishes = [d for d in st.session_state.dishes if d != delete_dish]
            st.rerun()

    if st.button("Proceed to voting"):
        st.session_state.phase = "vote"

# Phase 2: Vote on dishes
elif st.session_state.phase == "vote":
    st.header("Step 2: Vote for dishes you like")
    st.write("You can vote for as many dishes as you want.")
    with st.form("vote_form"):
        selected = st.multiselect("Select your favorite dishes:", [d["name"] for d in st.session_state.dishes])
        voted = st.form_submit_button("Submit votes")
        if voted:
            for dish in selected:
                st.session_state.votes[dish] = st.session_state.votes.get(dish, 0) + 1
            st.success("Votes submitted!")

    if st.button("See results and select dishes"):
        st.session_state.phase = "select"

# Phase 3: Select top dishes automatically
elif st.session_state.phase == "select":
    st.header("Step 3: Top voted dishes")
    vote_df = pd.DataFrame([{"Dish": k, "Votes": v} for k, v in st.session_state.votes.items()])
    vote_df = vote_df.sort_values("Votes", ascending=False)
    st.dataframe(vote_df)

    top_dishes = vote_df.head(6)["Dish"].tolist()
    st.session_state.top_dishes = top_dishes

    st.markdown("### Selected dishes:")
    for dish in top_dishes:
        st.markdown(f"- {dish}")

    if st.button("Add ingredients for selected dishes"):
        st.session_state.phase = "ingredients"

# Phase 4: Add ingredients
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
                st.session_state.ingredients.append({
                    "dish": dish,
                    "name": ing_name,
                    "qty": ing_qty,
                    "unit": ing_unit
                })
                st.success(f"Added {ing_name} to {dish}")

    if st.button("Generate shopping list"):
        st.session_state.phase = "shopping"

# Phase 5: Generate shopping list
elif st.session_state.phase == "shopping":
    st.header("Step 5: Shopping list")
    df = pd.DataFrame(st.session_state.ingredients)
    shopping = df.groupby(["name", "unit"])['qty'].sum().reset_index()
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

    # Reset button
    st.markdown("---")
    if st.button("🔁 Reset all and start over"):
        st.session_state.clear()
        st.rerun()
