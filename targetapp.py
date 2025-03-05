import streamlit as st
import requests
import json
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# ----------------------------
# 1. Fetch product data from RedCircle API with retries and extraction
# ----------------------------
@st.cache(allow_output_mutation=True)
def fetch_product_data_from_api(api_key: str, tcin: str) -> dict:
    """
    Fetch product data from the RedCircle API using the provided API key and TCIN.
    Implements a retry strategy and extracts the nested 'product' data.
    """
    params = {
        'api_key': api_key,
        'type': 'product',
        'tcin': tcin
    }
    
    session = requests.Session()
    retry_strategy = Retry(
        total=3,                      # Total of 3 retries
        backoff_factor=2,             # Waits: 2s, 4s, 8s between retries
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET"]
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    try:
        response = session.get("https://api.redcircleapi.com/request", params=params, timeout=10)
        response.raise_for_status()
        product_data = response.json()
        # Extract the product details from the nested structure.
        if isinstance(product_data, dict) and "product" in product_data:
            product_data = product_data["product"]
        if not isinstance(product_data, dict):
            st.warning("Fetched product data is not a dictionary. Check API response format.")
            return {}
        return product_data
    except requests.exceptions.Timeout:
        st.error("Request timed out even after retries. Please try again later.")
    except requests.exceptions.HTTPError as http_err:
        st.error(f"HTTP error: {http_err}")
    except requests.exceptions.RequestException as req_err:
        st.error(f"Network/Request error: {req_err}")
    except Exception as e:
        st.error(f"Unhandled exception while fetching data: {e}")
    return {}

# ----------------------------
# 2. Initialize session state
# ----------------------------
def init_session_state():
    """
    Initialize session state variables:
      - product_data: data returned from the API.
      - field_status: list of dictionaries for each field and its 'required' status.
      - api_key: API key input from the user.
    """
    if "product_data" not in st.session_state:
        st.session_state.product_data = {}

    if "api_key" not in st.session_state:
        st.session_state.api_key = ""

    if "field_status" not in st.session_state:
        st.session_state.field_status = [
            {"field": "TCIN", "required": True},
            {"field": "Product Title", "required": True},
            {"field": "Brand", "required": True},
            {"field": "Price", "required": True},
            {"field": "Main Image", "required": True},
            {"field": "UPC", "required": False},
            {"field": "DPCI", "required": False},
            {"field": "Description", "required": False},
            {"field": "Ingredients", "required": False},
            {"field": "Feature Bullets", "required": False},
            {"field": "Specifications", "required": False},
            {"field": "Weight", "required": False},
            {"field": "Dimensions", "required": False},
            {"field": "Total Ratings", "required": False},
        ]

# ----------------------------
# 3. Define key mapping
# ----------------------------
# This maps our display names to the API's keys.
# Note: "Price" and "Main Image" are handled separately.
key_mapping = {
    "TCIN": "tcin",
    "Product Title": "title",
    "Brand": "brand",
    "UPC": "upc",
    "DPCI": "dpci",
    "Description": "description",
    "Ingredients": "ingredients",
    "Feature Bullets": "feature_bullets",  # may be a list
    "Specifications": "specifications_flat",  # a flat string version is provided
    "Weight": "weight",
    "Dimensions": "dimensions",
    "Total Ratings": "ratings_total"  # using ratings_total from the response
}

# ----------------------------
# 4. UI Components
# ----------------------------
def draw_header():
    st.title("Product Data Annotator")
    st.caption("Enter your API key and a TCIN to fetch product data via the RedCircle API, then view, annotate, and export it.")

def draw_sidebar():
    with st.sidebar:
        st.header("API Credentials")
        # API key input (hidden for security)
        api_key_input = st.text_input("Enter API Key", value="73EC1316A3E54AE9BE5E5F53A589C5F0", type="password")
        st.session_state.api_key = api_key_input
        
        st.header("Search by TCIN")
        tcin_input = st.text_input("Enter TCIN", value="89603872")
        if st.button("Fetch Data", key="fetch_data_button"):
            if not st.session_state.api_key:
                st.error("Please provide an API key!")
            else:
                product_data = fetch_product_data_from_api(st.session_state.api_key, tcin_input)
                if product_data:
                    st.session_state.product_data = product_data
                else:
                    st.warning("No product data fetched. Check the TCIN or API availability.")

def draw_product_details_tab():
    st.subheader("Product Details")
    data = st.session_state.product_data
    field_status = st.session_state.field_status

    if not data:
        st.info("No product data found. Please enter a valid TCIN in the sidebar.")
        return

    # Determine which fields to display
    required_fields = [fs["field"] for fs in field_status if fs["required"]]
    show_optional = st.checkbox("Show Optional Fields", value=False)
    optional_fields = [fs["field"] for fs in field_status if not fs["required"]] if show_optional else []
    displayed_fields = required_fields + optional_fields

    st.markdown("### Product Information")
    
    # Handle Main Image separately.
    main_image_url = ""
    main_image_data = data.get("main_image")
    if isinstance(main_image_data, dict):
        main_image_url = main_image_data.get("link", "")
    
    # Create a two-column layout if a main image is available.
    if isinstance(main_image_url, str) and main_image_url.startswith("http"):
        col1, col2 = st.columns([1, 2])
        with col1:
            st.image(main_image_url, caption="Main Image", use_container_width=True)
        with col2:
            for field in displayed_fields:
                if field == "Main Image":
                    continue
                if field == "Price":
                    price_obj = data.get("buybox_winner", {}).get("price", {})
                    currency = price_obj.get("currency_symbol", "")
                    value = price_obj.get("value", "N/A")
                    st.markdown(f"**{field}:** {currency}{value}")
                else:
                    api_key_field = key_mapping.get(field, field)
                    value = data.get(api_key_field, "N/A")
                    if isinstance(value, list):
                        value = ", ".join([str(x) for x in value])
                    st.markdown(f"**{field}:** {value}")
    else:
        for field in displayed_fields:
            if field == "Price":
                price_obj = data.get("buybox_winner", {}).get("price", {})
                currency = price_obj.get("currency_symbol", "")
                value = price_obj.get("value", "N/A")
                st.markdown(f"**{field}:** {currency}{value}")
            elif field == "Main Image":
                continue
            else:
                api_key_field = key_mapping.get(field, field)
                value = data.get(api_key_field, "N/A")
                if isinstance(value, list):
                    value = ", ".join([str(x) for x in value])
                st.markdown(f"**{field}:** {value}")

def draw_annotations_tab():
    st.subheader("Annotations: Required vs. Optional Fields")
    st.write(
        "Toggle each field's required status using the table below. "
        "Fields marked as 'required' will appear in the Product Details view."
    )
    st.write("---")
    
    edited_data = st.data_editor(
        st.session_state.field_status,
        key="field_editor",
        use_container_width=True,
        num_rows="dynamic",
        disabled=["field"],
        hide_index=True,
        column_config={
            "field": "Field Name",
            "required": st.column_config.CheckboxColumn(
                "Is Required?",
                help="Check to mark this field as required."
            )
        }
    )
    st.session_state.field_status = edited_data

    st.write("---")
    if st.button("Export Required Fields as JSON"):
        data = st.session_state.product_data
        if not data:
            st.warning("No product data to export. Please fetch data first.")
            return
        required_fields = [row["field"] for row in edited_data if row["required"]]
        final_data = {}
        for field in required_fields:
            if field == "Price":
                price_obj = data.get("buybox_winner", {}).get("price", {})
                currency = price_obj.get("currency_symbol", "")
                value = price_obj.get("value", "N/A")
                final_data[field] = f"{currency}{value}"
            elif field == "Main Image":
                main_img = data.get("main_image", {})
                final_data[field] = main_img.get("link", "N/A") if isinstance(main_img, dict) else "N/A"
            else:
                api_key_field = key_mapping.get(field, field)
                value = data.get(api_key_field, "N/A")
                if isinstance(value, list):
                    value = ", ".join([str(x) for x in value])
                final_data[field] = value
        json_output = json.dumps(final_data, indent=4)
        st.code(json_output, language="json")
        st.success("JSON exported above!")

def main():
    init_session_state()
    draw_header()
    draw_sidebar()

    selected_tab = st.radio("Select Tab", ["Product Details", "Annotations"])
    if selected_tab == "Product Details":
        draw_product_details_tab()
    else:
        draw_annotations_tab()

if __name__ == "__main__":
    main()
