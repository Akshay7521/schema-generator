import streamlit as st
import json
import logging
import requests
from bs4 import BeautifulSoup
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import re

load_dotenv()

logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(message)s')

def sanitize_text(text):
    """Sanitize text to avoid encoding errors."""
    return text.encode('utf-8', 'ignore').decode('utf-8')

def setup_azure_openai():
    endpoint = os.getenv("ENDPOINT_URL")
    deployment = os.getenv("DEPLOYMENT_NAME")
    subscription_key = os.getenv("AZURE_OPENAI_API_KEY")

    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=subscription_key,
        api_version=os.getenv("AZURE_OPENAI_VERSION")
    ), deployment

def extract_text_from_web(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3'
    }
    response = requests.get(url, headers=headers, timeout=10)
    response.raise_for_status()
    soup = BeautifulSoup(response.content, "html.parser")

    formatted_text = ""
    images = [img['src'] for img in soup.find_all('img') if 'src' in img.attrs]

    for tag in soup.find_all(text=True):
        if tag.name == 'p':
            formatted_text += f"\n{sanitize_text(tag.get_text())}\n"
        else:
            formatted_text2 = ' '.join(sanitize_text(tag.get_text()).split())
            formatted_text = formatted_text + formatted_text2

    formatted_text = formatted_text + ' '.join(images)
    return formatted_text

def extract_text_from_json(json_content):
    try:
        content = json.loads(json_content)
        return json.dumps(content, indent=2)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON: {e}")
        return None

def generate_schema(client, deployment, text_content, url, user_prompt):
    try:
        if user_prompt:
            prompt = f"{user_prompt}\n\nExtract all relevant information from this content:\n{text_content}\n\nReturn ONLY the JSON-LD schema, nothing else. Ensure all JSON is properly formatted with double quotes."
        else:
            prompt = f"""Generate a detailed, SEO-optimized schema in JSON-LD format following schema.org guidelines.
Ensure that the schema is generic enough to cover diverse content types but also includes the following aspects where applicable:
 
- Use the most relevant schema type (e.g., `Article`, `Recipe`, `Event`, `Product`) based on the provided content.
- Include key properties specific to the schema type (e.g., `author`, `datePublished`, `headline` for `Article`; `prepTime`, `cookTime`, `recipeIngredient`, `rating` for `Recipe`).
-Make sure that you do not add anything extra other than the content or modify the content.
- Include at least 15 SEO-friendly keywords extracted from the content.
- Ensure that the schema includes `@context`, `@type`, `url`, and `description` fields at a minimum.
- Include additional fields such as `mainEntityOfPage`, `image`, `publisher`, or `offers` when relevant.
- The output MUST be valid JSON-LD with proper syntax and double quotes.
 
Extract all relevant information from this content
    {text_content}"""
        
        messages = [
            {
                "role": "system",
                "content": "You are a 20+ years experienced schema generator for better SEO for websites. "
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        completion = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=3000,
            temperature=0,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            stream=False
        )
        
        response = completion.choices[0].message.content
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        
        if json_start == -1 or json_end == 0:
            raise ValueError("No valid JSON found in response")
        
        schema_json = response[json_start:json_end]
        
        try:
            return json.loads(schema_json)
        except json.JSONDecodeError as e:
            logging.error(f"Error parsing JSON: {e}")
            return {"error": "Invalid JSON format in response"}
        
    except Exception as e:
        logging.error(f"Error generating schema: {e}")
        return {"error": str(e)}

def compare_schemas(client, deployment, user_schema, generated_schema):
    try:
        prompt = f"""Compare the following two JSON-LD schemas and provide an accuracy score. 
            The accuracy score should reflect how closely the user schema matches the generated schema.
            Provide the score as a percentage and list the missing or additional fields in the user schema compared to the generated schema.

        User Schema:
        {user_schema}

        Generated Schema:
        {generated_schema}

        Return the accuracy score as a percentage and list the missing or additional fields."""
                
        messages = [
            {
                "role": "system",
                "content": "You are an AI assistant that compares JSON-LD schemas and provides an accuracy score and detailed comparision."
            },
            {
                "role": "user",
                "content": prompt
            }
        ]
        
        completion = client.chat.completions.create(
            model=deployment,
            messages=messages,
            max_tokens=3000,
            temperature=0,
            top_p=0.95,
            frequency_penalty=0,
            presence_penalty=0,
            stop=None,
            stream=False
        )
        
        response = completion.choices[0].message.content
        
        # Extract accuracy score from response
        accuracy_match = re.search(r'(\d+(\.\d+)?)%', response)
        if accuracy_match:
            accuracy = float(accuracy_match.group(1))
        else:
            raise ValueError("No valid accuracy score found in response")
        
        # Extract missing or additional fields
        missing_fields = re.findall(r'Missing fields: (.+)', response)
        additional_fields = re.findall(r'Additional fields: (.+)', response)
        
        return {
            "accuracy": accuracy,
            "missing_fields": missing_fields,
            "additional_fields": additional_fields,
            "detailed_comparison": response
        }
    
    except Exception as e:
        logging.error(f"Error comparing schemas: {e}")
        return {"error": str(e)}

def main():
    st.set_page_config(page_title="Schema Generator & Validator", layout="wide")
    
    st.title("Schema Generator & Validator")
    st.markdown("""
    This app generates and validates SEO-friendly JSON-LD schema for webpages.
    You can either generate a schema from a URL or a JSON file, and validate your own schema against our standards.
    """)
    
    # Initialize Azure OpenAI
    try:
        client, deployment = setup_azure_openai()
    except Exception as e:
        st.error(f"Error connecting to Azure OpenAI: {e}")
        st.info("Make sure your Azure OpenAI credentials are properly configured in the environment variables.")
        return
    
    # Initialize session state for generated schema
    if "generated_schema" not in st.session_state:
        st.session_state.generated_schema = None
    
    # Create tabs for different functionalities
    tab1, tab2, tab3 = st.tabs(["Generate Schema from URL", "Generate Schema from JSON File", "Validate Schema"])
    
    with tab1:
        # URL input
        url = st.text_input("Enter webpage URL:", placeholder="https://example.com/")
        
        # Prompt text area with default value
        user_prompt = st.text_area("Customize your prompt:", value=f"""Generate a detailed, SEO-optimized schema in JSON-LD format following schema.org guidelines.
Ensure that the schema is generic enough to cover diverse content types but also includes the following aspects where applicable:
 
- Use the most relevant schema type (e.g., `Article`, `Recipe`, `Event`, `Product`) based on the provided content.
- Include key properties specific to the schema type (e.g., `author`, `datePublished`, `headline` for `Article`; `prepTime`, `cookTime`, `recipeIngredient`, `rating` for `Recipe`).
-Make sure that you do not add anything extra other than the content or modify the content.
- Include at least 15 SEO-friendly keywords extracted from the content.
- Ensure that the schema includes `@context`, `@type`, `url`, and `description` fields at a minimum.
- Include additional fields such as `mainEntityOfPage`, `image`, `publisher`, or `offers` when relevant.
- The output MUST be valid JSON-LD with proper syntax and double quotes.
 
Extract all relevant information from this content""")
        
        if st.button("Generate Schema from URL"):
            if not url:
                st.warning("Please enter a URL")
                return
                
            with st.spinner("Fetching webpage content..."):
                text_content = extract_text_from_web(url)
                
            if not text_content:
                st.error("Could not fetch webpage content. Please check the URL and try again.")
                return
                
            with st.spinner("Generating schema..."):
                st.session_state.generated_schema = generate_schema(client, deployment, text_content, url, user_prompt)
                
            if "error" in st.session_state.generated_schema:
                st.error(f"Error generating schema: {st.session_state.generated_schema['error']}")
                return
            
            # Display results
            col1, col2 = st.columns(2)
            
            with col1:
                st.download_button(
                    label="Download Schema",
                    data=json.dumps(st.session_state.generated_schema, indent=2),
                    file_name="schema.json",
                    mime="application/json"
                )
                
                st.subheader("Generated Schema (Pretty)")
                st.write(st.session_state.generated_schema)
                
            with col2:
                st.subheader("Raw JSON-LD")
                schema_text = f'<script type="application/ld+json">\n{json.dumps(st.session_state.generated_schema, indent=2)}\n</script>'
                st.code(schema_text, language="html")
    
    with tab2:
        st.subheader("Upload JSON File")
        st.markdown("""
        Upload a JSON file containing the webpage content or other content to generate a schema.
        """)
        
        uploaded_file = st.file_uploader("Choose a JSON file", type="json")
        
        if uploaded_file is not None:
            json_content = uploaded_file.read().decode("utf-8")
            text_content = extract_text_from_json(json_content)
            
            if not text_content:
                st.error("Could not parse JSON file. Please check the file and try again.")
                return
            
            # Prompt text area with default value
            user_prompt = st.text_area("Customize your prompt:", value=f"""Generate a detailed, SEO-optimized schema in JSON-LD format following schema.org guidelines.
Ensure that the schema is generic enough to cover diverse content types but also includes the following aspects where applicable:
 
- Use the most relevant schema type (e.g., `Article`, `Recipe`, `Event`, `Product`) based on the provided content.
- Include key properties specific to the schema type (e.g., `author`, `datePublished`, `headline` for `Article`; `prepTime`, `cookTime`, `recipeIngredient`, `rating` for `Recipe`).
-Make sure that you do not add anything extra other than the content or modify the content.
- Include at least 15 SEO-friendly keywords extracted from the content.
- Ensure that the schema includes `@context`, `@type`, `url`, and `description` fields at a minimum.
- Include additional fields such as `mainEntityOfPage`, `image`, `publisher`, or `offers` when relevant.
- The output MUST be valid JSON-LD with proper syntax and double quotes.
 
Extract all relevant information from this content
            """)
            
            if st.button("Generate Schema from JSON File"):
                with st.spinner("Generating schema..."):
                    st.session_state.generated_schema = generate_schema(client, deployment, text_content, None, user_prompt)
                    
                if "error" in st.session_state.generated_schema:
                    st.error(f"Error generating schema: {st.session_state.generated_schema['error']}")
                    return
                
                # Display results
                col1, col2 = st.columns(2)
                
                with col1:
                    st.download_button(
                        label="Download Schema",
                        data=json.dumps(st.session_state.generated_schema, indent=2),
                        file_name="schema.json",
                        mime="application/json"
                    )
                    
                    st.subheader("Generated Schema (Pretty)")
                    st.write(st.session_state.generated_schema)
                    
                with col2:
                    st.subheader("Raw JSON-LD")
                    schema_text = f'<script type="application/ld+json">\n{json.dumps(st.session_state.generated_schema, indent=2)}\n</script>'
                    st.code(schema_text, language="html")
    
    with tab3:
        st.subheader("Schema Validator")
        st.markdown("""
        Paste your schema JSON-LD here to validate it against our standards.
        The validator will check for required fields and proper formatting.
        """)
        
        user_schema = st.text_area(
            "Your Schema JSON-LD",
            height=300,
            placeholder='Paste your JSON-LD schema here...'
        )
        
        if st.button("Validate Schema"):
            try:
                # First check if it's valid JSON
                try:
                    user_json = json.loads(user_schema)
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON format: {str(e)}")
                    return
                
                # Compare the schemas
                if st.session_state.generated_schema:
                    with st.spinner("Comparing schemas..."):
                        comparison_result = compare_schemas(client, deployment, user_schema, json.dumps(st.session_state.generated_schema, indent=2))
                    
                    if "error" in comparison_result:
                        st.error(f"Error comparing schemas: {comparison_result['error']}")
                        return
                    
                    # Display results
                    st.subheader("Validation Results")
                    
                    # Display accuracy
                    st.metric("Schema Accuracy", f"{comparison_result['accuracy']}%")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        if comparison_result['missing_fields']:
                            st.error("Missing Fields:")
                            for field in comparison_result['missing_fields']:
                                st.write(f"• {field}")
                    
                    with col2:
                        if comparison_result['additional_fields']:
                            st.error("Additional Fields:")
                            for field in comparison_result['additional_fields']:
                                st.write(f"• {field}")
                    
                    # Display detailed comparison
                    st.subheader("Detailed Comparison")
                    st.write(comparison_result['detailed_comparison'])
                else:
                    st.error("No generated schema available for comparison. Please generate a schema first.")
                
            except Exception as e:
                st.error(f"Error during validation: {str(e)}")

if __name__ == "__main__":
    main()