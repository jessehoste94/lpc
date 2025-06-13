import streamlit as st
import requests
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import io

st.set_page_config(layout="wide")
st.title("Trademark Pattern Checker (EUIPO Sandbox)")

# Inputvelden
brand = st.text_input("Merknaam", value="PAXON")
client_id = "a4a03e03938a6bde6b0893fc495c4eef"
access_token = st.text_input("Access Token (Ask Jesse)", type="password")
extra_patterns = st.text_area("Extra patronen (optioneel, 1 per lijn)", 
    placeholder="bv.\npa??on\nwordMarkSpecification.verbalElement==*xon")

# Optionele filters
st.markdown("**Optionele filters**")
col1, col2, col3 = st.columns(3)
with col1:
    mark_kind = st.multiselect("Mark Kind", ["INDIVIDUAL", "EU_COLLECTIVE", "EU_CERTIFICATION"])
    mark_feature = st.multiselect("Mark Feature", ["WORD", "FIGURATIVE", "SHAPE_3D", "COLOUR", "SOUND", "HOLOGRAM", "OLFACTORY", "POSITION", "PATTERN", "MOTION", "MULTIMEDIA", "OTHER"])
with col2:
    mark_basis = st.multiselect("Mark Basis", ["EU_TRADEMARK", "INTERNATIONAL_TRADEMARK"])
    status = st.multiselect("Status", ["RECEIVED", "UNDER_EXAMINATION", "APPLICATION_PUBLISHED", "REGISTRATION_PENDING", "REGISTERED", "WITHDRAWN", "REFUSED", "OPPOSITION_PENDING", "APPEALED", "CANCELLATION_PENDING", "CANCELLED", "SURRENDERED", "EXPIRED", "APPEALABLE", "START_OF_OPPOSITION_PERIOD", "ACCEPTANCE_PENDING", "ACCEPTED", "REMOVED_FROM_REGISTER"])
with col3:
    nice_classes = st.multiselect("Nice Classes (selecteer)", list(range(1, 46)))
    registration_date = st.text_input("Registratiedatum na (YYYY-MM-DD)")

# Functie voor genereren van query-patronen
def generate_star_queries(brand):
    queries = [f'wordMarkSpecification.verbalElement=="{brand}"']
    if len(brand) > 2:
        stem = brand[:-2]
        queries.append(f'wordMarkSpecification.verbalElement=={stem}*')
    for i in range(1, len(brand)):
        queries.append(f'wordMarkSpecification.verbalElement=={brand[:i]}*{brand[i:]}')
    if len(brand) > 3:
        queries.append(f'wordMarkSpecification.verbalElement==*{brand[1:]}')
    star_between_letters = '*'.join(brand)
    queries.append(f'wordMarkSpecification.verbalElement=={star_between_letters}')
    return queries

# Flatten nested dictionaries in trademark items
def flatten_trademark(trademark):
    flat = trademark.copy()
    flat["verbalElement"] = trademark.get("wordMarkSpecification", {}).get("verbalElement", None)
    if trademark.get("applicants"):
        flat["applicant_name"] = ", ".join([a.get("name", "") for a in trademark["applicants"]])
    if trademark.get("representatives"):
        flat["representative_name"] = ", ".join([r.get("name", "") for r in trademark["representatives"]])
    flat["nice_classes"] = ", ".join(map(str, trademark.get("niceClasses", [])))
    return flat

# Functie om alle pagina's op te halen per query
def fetch_all_data(query, headers, expected_length=None):
    all_results = []
    page = 0
    while True:
        extra_conditions = []
        if mark_kind:
            or_condition = " or ".join([f"markKind=={v}" for v in mark_kind])
            extra_conditions.append(f"({or_condition})")
        if mark_feature:
            or_condition = " or ".join([f"markFeature=={v}" for v in mark_feature])
            extra_conditions.append(f"({or_condition})")
        if mark_basis:
            or_condition = " or ".join([f"markBasis=={v}" for v in mark_basis])
            extra_conditions.append(f"({or_condition})")
        if status:
            or_condition = " or ".join([f"status=={v}" for v in status])
            extra_conditions.append(f"({or_condition})")
        if nice_classes:
            values = ','.join(str(n) for n in nice_classes)
            extra_conditions.append(f"niceClasses=all=({values})")
        if registration_date:
            extra_conditions.append(f"registrationDate>={registration_date}")

        full_query = query
        if extra_conditions:
            full_query += " and " + " and ".join(extra_conditions)

        #st.write(f"🔎 Query uitgevoerd: `{full_query}`")

        params = {
            "query": full_query,
            "size": 100,
            "page": page
        }
        response = requests.get(BASE_URL, headers=headers, params=params)
        if response.status_code != 200:
            st.error(f"❌ Fout voor query: {query} – Status {response.status_code}")
            return [], None
        data = response.json()
        trademarks = data.get("trademarks", [])
        if expected_length:
            trademarks = [t for t in trademarks if len(t.get("wordMarkSpecification", {}).get("verbalElement", "")) == expected_length]
        all_results.extend(trademarks)
        if page >= data.get("totalPages", 1) - 1:
            break
        page += 1
    return all_results, None

# Download helper
def get_excel_download_link(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# Actieknop
if st.button("Start analyse") and brand and access_token and client_id:
    BASE_URL = "https://api-sandbox.euipo.europa.eu/trademark-search/trademarks"
    HEADERS = {
        "X-IBM-Client-Id": client_id,
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }

    pattern_counts = []
    detailed_dfs = []

    base_patterns = [(p, None) for p in generate_star_queries(brand)]

    if extra_patterns:
        print(extra_patterns)
        for line in extra_patterns.splitlines():

            clean = line.strip()

            if not clean:
                continue
            if '?' in clean:
                val = clean
                wildcard_version = val.replace('?', '*')
                pattern = f'wordMarkSpecification.verbalElement=={wildcard_version}'
                expected_length = len(val)
                base_patterns.append((pattern, expected_length))
            else:
                base_patterns.append((clean, None))

    with st.spinner("Bezig met ophalen van resultaten..."):
        for pattern, length_filter in base_patterns:
            all_data, _ = fetch_all_data(pattern, HEADERS, expected_length=length_filter)
            if all_data is None:
                pattern_counts.append({"pattern": pattern, "match_count": float('-inf')})
                continue
            flattened = [flatten_trademark(item) for item in all_data]
            df_flat = pd.DataFrame(flattened)
            count = len(df_flat)
            detailed_dfs.append((pattern, df_flat))
            pattern_counts.append({"pattern": pattern, "match_count": count})

    valid_results = [entry for entry in pattern_counts if isinstance(entry["match_count"], int)]
    result_df = pd.DataFrame(valid_results).sort_values(by="match_count", ascending=False)

    st.subheader("Aantal geregistreerde merken per patroon")
    st.dataframe(result_df, use_container_width=True)

    if not result_df.empty:
        fig, ax = plt.subplots(figsize=(12, 5))
        result_df['Pattern'] = result_df['pattern'].str.replace("wordMarkSpecification.verbalElement==", "")
        sns.barplot(data=result_df, x="match_count", y="Pattern", ax=ax)
        ax.set_xlabel("Aantal resultaten")
        ax.set_ylabel("Zoekpatroon")
        st.pyplot(fig)

    st.markdown("---")
    for pattern, df_view in detailed_dfs:
        if not df_view.empty:
            with st.expander(f"Bekijk resultaten voor patroon: {pattern} ({len(df_view)})"):
                st.dataframe(df_view, use_container_width=True)
                excel_data = get_excel_download_link(df_view)
                st.download_button(
                    label="📥 Download resultaten als Excel",
                    data=excel_data,
                    file_name=f"results_{brand}_{pattern.replace('*', 'STAR')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
