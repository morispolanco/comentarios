import streamlit as st
import pandas as pd
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
import re
from datetime import datetime
import requests
import subprocess
import os

# Streamlit page configuration
st.set_page_config(page_title="Amazon Book Reviews Extractor", layout="wide")

# Title and description
st.title("Amazon Book Reviews Extractor")
st.markdown("Extract user reviews for a specific book from Amazon using its ASIN and export them to Excel.")

# Input fields
asin = st.text_input("Enter the book's ASIN (e.g., B0CW1LJXKN):", placeholder="10-character ASIN")
submit_button = st.button("Extract Reviews")

# Function to clean text
def clean_text(text):
    text = re.sub(r'\s+', ' ', text.strip())
    return text

# Function to check Chrome version
def get_chrome_version():
    try:
        result = subprocess.run(['google-chrome', '--version'], capture_output=True, text=True)
        version = result.stdout.strip()
        st.write(f"Installed Chrome version: {version}")
        return version
    except Exception as e:
        st.error(f"Error checking Chrome version: {str(e)}. Ensure Google Chrome is installed.")
        return None

# Function to scrape Amazon reviews using Selenium
def scrape_reviews(asin):
    driver = None
    try:
        # Check Chrome installation
        chrome_version = get_chrome_version()
        if not chrome_version:
            st.error("Google Chrome is not installed. Please install it using: sudo apt-get install -y google-chrome-stable")
            return []
        
        # Set up Selenium with headless Chrome
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Initialize ChromeDriver
        st.write("Initializing ChromeDriver...")
        driver = webdriver.Chrome(
            service=Service(ChromeDriverManager().install()),
            options=chrome_options
        )
        
        # Log ChromeDriver version
        driver_version = driver.capabilities['chrome']['chromedriverVersion'].split()[0]
        st.write(f"ChromeDriver version: {driver_version}")
        
        # Explicitly use the specified URL format
        url = f"https://www.amazon.com/product-reviews/{asin}"
        st.write(f"Scraping URL: {url}")
        
        driver.get(url)
        
        # Wait for reviews to load (up to 15 seconds)
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div[data-hook="review"], div.a-section.review'))
            )
        except:
            st.warning("Reviews not loaded within 15 seconds. Checking for CAPTCHA or no reviews.")
        
        # Check for CAPTCHA
        if driver.find_elements(By.CSS_SELECTOR, 'form[action="/errors/validateCaptcha"]'):
            st.error("CAPTCHA detected. Amazon is blocking the request. Try manually visiting the URL or use a proxy.")
            return []
        
        # Debugging: Log page title
        title = driver.title
        st.write(f"Page title: {title if title else 'No title found'}")
        
        # Find review elements
        review_elements = driver.find_elements(By.CSS_SELECTOR, 'div[data-hook="review"]')
        if not review_elements:
            st.warning("No review elements found with 'div[data-hook=\"review\"]'. Trying fallback selectors.")
            review_elements = driver.find_elements(By.CSS_SELECTOR, 'div.a-section.review, div.review')
        
        reviews = []
        for element in review_elements:
            try:
                username = element.find_element(By.CSS_SELECTOR, 'span.a-profile-name, div.a-profile-content span')
                username = clean_text(username.text) if username else "Anonymous"
            except:
                username = "Anonymous"
                
            try:
                comment_text = element.find_element(By.CSS_SELECTOR, 'span[data-hook="review-body"], div.review-text')
                comment_text = clean_text(comment_text.text) if comment_text else ""
            except:
                comment_text = ""
                
            try:
                rating = element.find_element(By.CSS_SELECTOR, 'i[data-hook="review-star-rating"] span.a-icon-alt, i.review-rating span')
                rating = clean_text(rating.text.split()[0]) if rating else "N/A"
            except:
                rating = "N/A"
                
            try:
                date = element.find_element(By.CSS_SELECTOR, 'span[data-hook="review-date"], span.review-date')
                date = clean_text(date.text) if date else "N/A"
            except:
                date = "N/A"
            
            if comment_text:
                reviews.append({
                    'Username': username,
                    'Comment': comment_text,
                    'Rating': rating,
                    'Date': date,
                    'ASIN': asin
                })
        
        if not reviews:
            st.warning("No valid reviews extracted. Possible reasons: no reviews exist or page requires further interaction.")
        else:
            st.success(f"Found {len(reviews)} reviews.")
        
        return reviews
    except Exception as e:
        st.error(f"Error during scraping: {str(e)}")
        return []
    finally:
        if driver:
            driver.quit()

# Function to call Gemini API for sentiment analysis
def analyze_sentiment(comment):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{"text": f"Analyze the sentiment of this book review: '{comment}'. Return 'Positive', 'Negative', or 'Neutral'."}]
            }]
        }
        
        response = requests.post(f"{url}?key={api_key}", json=data, headers=headers)
        response.raise_for_status()
        result = response.json()
        sentiment = result.get('candidates', [{}])[0].get('content', {}).get('parts', [{}])[0].get('text', 'Neutral')
        return sentiment.strip()
    except Exception as e:
        st.warning(f"Error analyzing sentiment: {str(e)}")
        return "Neutral"

# Main logic
if submit_button and asin:
    # Validate ASIN format (10 characters, alphanumeric)
    if not re.match(r'^[A-Z0-9]{10}$', asin):
        st.error("Please enter a valid 10-character ASIN.")
    else:
        with st.spinner("Extracting reviews..."):
            reviews = scrape_reviews(asin)
            
            if reviews:
                # Add sentiment analysis
                for review in reviews:
                    review['Sentiment'] = analyze_sentiment(review['Comment'])
                
                # Create DataFrame
                df = pd.DataFrame(reviews)
                
                # Display results
                st.subheader(f"Reviews for Book (ASIN: {asin})")
                st.dataframe(df)
                
                # Export to Excel
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"amazon_book_{asin}_reviews_{timestamp}.xlsx"
                df.to_excel(filename, index=False)
                
                # Provide download button
                with open(filename, "rb") as file:
                    st.download_button(
                        label="Download Excel file",
                        data=file,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
            else:
                st.warning("No reviews found or error occurred during extraction. Check debug messages above.")

# Instructions for secrets and setup
st.sidebar.markdown(
    """
    ### Setup Instructions
    1. Create a `.streamlit/secrets.toml` file in your project directory.
    2. Add your Gemini API key:
    ```
    GEMINI_API_KEY = "your_api_key_here"
    ```
    3. Install required packages:
    ```
    pip install streamlit pandas selenium webdriver-manager openpyxl requests
    ```
    4. Install Google Chrome and dependencies (Linux):
    ```
    sudo apt-get update
    sudo apt-get install -y wget unzip libxss1 libappindicator1 libindicator7 libnss3 libx11-xcb1 libasound2 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0
    wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    sudo dpkg -i google-chrome-stable_current_amd64.deb
    sudo apt-get install -f -y
    ```
    5. Run the app:
    ```
    streamlit run app.py
    ```
    6. Enter a valid 10-character ASIN (e.g., B0CW1LJXKN).
    7. The app scrapes reviews from `https://www.amazon.com/product-reviews/<ASIN>` using Selenium.
    8. If no reviews are found:
       - Verify reviews exist by visiting the URL in your browser.
       - Check for CAPTCHA in debug messages.
       - Ensure Chrome and ChromeDriver are installed (run `google-chrome --version`).
    9. For CAPTCHA issues, try a proxy or manual browser interaction.
    10. For Docker/Streamlit Cloud, use a custom Dockerfile with Chrome installed.
    """
)
