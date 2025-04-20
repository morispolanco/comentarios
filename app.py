import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime

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

# Function to scrape Amazon reviews
def scrape_reviews(asin):
    try:
        # Explicitly use the specified URL format
        url = f"https://www.amazon.com/product-reviews/{asin}"
        st.write(f"Scraping URL: {url}")
        
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Connection': 'keep-alive'
        }
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        
        # Debugging: Log response details
        st.write(f"Response status code: {response.status_code}")
        st.write(f"Response content length: {len(response.text)} bytes")
        
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Check for CAPTCHA or bot detection
        captcha = soup.select_one('form[action="/errors/validateCaptcha"]')
        if captcha:
            st.error("CAPTCHA detected. Amazon is blocking the request. Consider using a proxy or Selenium.")
            return []
        
        # Debugging: Log page title
        title = soup.select_one('title')
        st.write(f"Page title: {title.get_text() if title else 'No title found'}")
        
        # Find review elements
        review_elements = soup.select('div[data-hook="review"]')
        if not review_elements:
            st.warning("No review elements found with 'div[data-hook=\"review\"]'. Trying fallback selectors.")
            # Fallback selectors
            review_elements = soup.select('div.a-section.review, div.review, div.a-row.a-spacing-none')
        
        reviews = []
        for element in review_elements:
            username = element.select_one('span.a-profile-name, div.a-profile-content span')
            username = clean_text(username.get_text()) if username else "Anonymous"
            
            comment_text = element.select_one('span[data-hook="review-body"], div.review-text')
            comment_text = clean_text(comment_text.get_text()) if comment_text else ""
            
            rating = element.select_one('i[data-hook="review-star-rating"] span.a-icon-alt, i.review-rating span')
            rating = clean_text(rating.get_text().split()[0]) if rating else "N/A"
            
            date = element.select_one('span[data-hook="review-date"], span.review-date')
            date = clean_text(date.get_text()) if date else "N/A"
            
            if comment_text:
                reviews.append({
                    'Username': username,
                    'Comment': comment_text,
                    'Rating': rating,
                    'Date': date,
                    'ASIN': asin
                })
        
        if not reviews:
            st.warning("No valid reviews extracted. Possible reasons: no reviews exist, incorrect selectors, or page requires JavaScript.")
        else:
            st.success(f"Found {len(reviews)} reviews.")
        return reviews
    except requests.exceptions.HTTPError as e:
        st.error(f"HTTP error: {str(e)}")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"Network error: {str(e)}")
        return []
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        return []

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
    pip install streamlit requests pandas beautifulsoup4 openpyxl
    ```
    4. Run the app:
    ```
    streamlit run app.py
    ```
    5. Enter a valid 10-character ASIN (e.g., B0CW1LJXKN).
    6. The app scrapes reviews from `https://www.amazon.com/product-reviews/<ASIN>`.
    7. If no reviews are found:
       - Verify reviews exist by visiting the URL in your browser.
       - Check for CAPTCHA or bot detection in debug messages.
       - Inspect the page's HTML to update selectors if needed.
    8. For persistent issues, consider using Selenium for dynamic content or a proxy for bot detection.
    """
)
