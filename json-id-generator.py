import streamlit as st
import json
import logging
import requests
from bs4 import BeautifulSoup
import os
from openai import AzureOpenAI
from dotenv import load_dotenv
import re
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
 
load_dotenv()
 
logging.basicConfig(level=logging.ERROR, format='%(asctime)s - %(message)s')
 
class AdvancedWebContentExtractor:
    def __init__(self, url):
        """
        Initialize web content extractor
        """
        self.url = url
        self.driver = self._setup_webdriver()
        self.extracted_contents = []
 
    def _setup_webdriver(self):
        """
        Configure robust Selenium WebDriver
        """
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/110.0.0.0 Safari/537.36")
       
        driver = webdriver.Chrome(options=chrome_options)
        return driver
 
    def expand_all_collapsible_sections(self):
        """
        Expand all collapsible sections using multiple strategies
        """
        try:
            # Navigate to page
            self.driver.get(self.url)
            time.sleep(2)  # Initial page load wait
 
            # Multiple expansion strategies
            expansion_strategies = [
                "//a[@data-toggle='collapse']",
                "//a[contains(@class, 'collapsed')]",
                "//a[contains(@class, 'icon-angle-right')]",
                "//a[@aria-expanded='false']",
                "//button[contains(@class, 'accordion-button')]"
            ]
 
            for strategy in expansion_strategies:
                try:
                    # Find all collapsible elements
                    collapsible_elements = self.driver.find_elements(By.XPATH, strategy)
                   
                    for element in collapsible_elements:
                        try:
                            # Scroll to element
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                            time.sleep(0.5)
                           
                            # Click to expand with JavaScript
                            self.driver.execute_script("arguments[0].click();", element)
                            time.sleep(1)  # Wait for content to load
                        except Exception as click_error:
                            print(f"Click error with element: {click_error}")
               
                except Exception as strategy_error:
                    print(f"Strategy failed: {strategy_error}")
 
            # Additional wait for dynamic content
            time.sleep(3)
 
        except Exception as e:
            print(f"Expansion error: {e}")
 
    def extract_comprehensive_contents(self):
        """
        Extract contents from multiple element types
        """
        try:
            # Get page source after expansion
            page_source = self.driver.page_source
           
            # Parse with BeautifulSoup
            soup = BeautifulSoup(page_source, 'html.parser')
           
            # Comprehensive content extraction
            content_selectors = [
                ('Paragraphs', soup.find_all('p')),
                ('Headings', soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6'])),
                ('Divs', soup.find_all('div', class_=lambda x: x and any(keyword in str(x) for keyword in ['content', 'text', 'description']))),
                ('Spans', soup.find_all('span', class_=lambda x: x and any(keyword in str(x) for keyword in ['text', 'content']))),
                ('Articles', soup.find_all('article')),
                ('Sections', soup.find_all('section'))
            ]
 
            # Extract and clean contents
            extracted_contents = {}
            for selector_name, elements in content_selectors:
                contents = [
                    elem.get_text(strip=True)
                    for elem in elements
                    if elem.get_text(strip=True)
                ]
                extracted_contents[selector_name] = contents
 
            return extracted_contents
 
        except Exception as e:
            print(f"Comprehensive extraction error: {e}")
            return {}
 
    def comprehensive_extraction(self):
        """
        Complete workflow: extract contents
        """
        try:
            # Expand all sections
            self.expand_all_collapsible_sections()
 
            # Extract comprehensive contents
            extracted_contents = self.extract_comprehensive_contents()
 
            return {
                'contents': extracted_contents
            }
 
        except Exception as e:
            print(f"Comprehensive extraction error: {e}")
            return None
 
        finally:
            # Always close the driver
            if self.driver:
                self.driver.quit()
 
def sanitize_text(text):
    """Sanitize text to avoid encoding errors."""
    return text.encode('utf-8', 'ignore').decode('utf-8')

def extract_text_from_json(json_content):
    try:
        content = json.loads(json_content)
        return json.dumps(content, indent=2)
    except json.JSONDecodeError as e:
        logging.error(f"Error parsing JSON: {e}")
        return None

def calculate_tokens(text):
    return len(text.split())

def calculate_cost(input_tokens, output_tokens):
    input_cost = (input_tokens / 1000) * 0.0050
    output_cost = (output_tokens / 1000) * 0.0150
    total_cost = input_cost + output_cost
    return input_cost, output_cost, total_cost

def setup_azure_openai():
    endpoint = os.getenv("ENDPOINT_URL")
    deployment = os.getenv("DEPLOYMENT_NAME")
    subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
 
    return AzureOpenAI(
        azure_endpoint=endpoint,
        api_key=subscription_key,
        api_version=os.getenv("AZURE_OPENAI_VERSION")
    ), deployment
 
def generate_schema(client, deployment, text_content, url, user_prompt, retries=3):
    for attempt in range(retries):
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
            logging.error(f"Attempt {attempt + 1} failed: {e}")
            time.sleep(2)  # Wait before retrying
 
    return {"error": "Failed to generate schema after multiple attempts"}
 
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
   
    # Initialize session state for generated schema and input text
    if "generated_schema" not in st.session_state:
        st.session_state.generated_schema = None
    if "input_text" not in st.session_state:
        st.session_state.input_text = ""
   
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
                extractor = AdvancedWebContentExtractor(url)
                result = extractor.comprehensive_extraction()
                if result:
                    text_content = "\n".join(
                        [content for section in result['contents'].values() for content in section]
                    )
                    st.session_state.input_text = text_content
                else:
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
                # Calculate tokens and cost
                input_text = st.session_state.input_text
                output_text = json.dumps(st.session_state.generated_schema, indent=2)
                input_tokens = calculate_tokens(input_text)
                output_tokens = calculate_tokens(output_text)
                input_cost, output_cost, total_cost = calculate_cost(input_tokens, output_tokens)

                st.write(f"Input Tokens: {input_tokens}, Cost: ${input_cost:.4f}")
                st.write(f"Output Tokens: {output_tokens}, Cost: ${output_cost:.4f}")
                st.write(f"Total Cost: ${total_cost:.4f}")

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
           
            st.session_state.input_text = text_content
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
                    # Calculate tokens and cost
                    input_text = st.session_state.input_text
                    output_text = json.dumps(st.session_state.generated_schema, indent=2)
                    input_tokens = calculate_tokens(input_text)
                    output_tokens = calculate_tokens(output_text)
                    input_cost, output_cost, total_cost = calculate_cost(input_tokens, output_tokens)

                    st.write(f"Input Tokens: {input_tokens}, Cost: ${input_cost:.4f}")
                    st.write(f"Output Tokens: {output_tokens}, Cost: ${output_cost:.4f}")
                    st.write(f"Total Cost: ${total_cost:.4f}")
                   
                with col2:
                    st.subheader("Raw JSON-LD")
                    schema_text = f'<script type="application/ld+json">\n{json.dumps(st.session_state.generated_schema, indent=2)}\n</script>'
                    st.code(schema_text, language="html")

if __name__ == "__main__":
    main()