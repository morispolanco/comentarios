import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime

# Streamlit page configuration
st.set_page_config(page_title="Amazon Book Comments Extractor", layout="wide")

# Title and description
st.title("Amazon Book Comments Extractor")
st.markdown("Extract user reviews for a specific book from Amazon using its ASIN and export them to Excel.")

# Input fields
asin = st.text_input("Enter the book's ASIN (e.g., B08N5WRWNW):", placeholder="10-character ASIN")
submit_button = st.button("Extract Reviews")

# Function to clean text
def clean_text(text):
    text = re.sub(r'\s+', ' ', text.strip())
    return text

# Function to scrape Amazon reviews
def scrape_reviews(asin):
    try:
        url = f"https://www.amazon.com/product-reviews/{asin}/"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find review elements
        review_elements = soup.select('div[data-hook="review"]')
        reviews = []
        
        for element in review_elements:
            username = element.select_one('span.a-profile-name')
            username = clean_text(username.get_text()) if username else "Anonymous"
            
            comment_text = element.select_one('span[data-hook="review-body"]')
            comment_text = clean_text(comment_text.get_text()) if comment_text else ""
            
            rating = element.select_one('i[data-hook="review-star-rating"] span.a-icon-alt')
            rating = clean_text(rating.get_text().split()[0]) if rating else "N/A"
            
            date = element.select_one('span[data-hook="review-date"]')
            date = clean_text(date.get_text()) if date else "N/A"
            
            if comment_text:
                reviews.append({
                    'Username': username,
                    'Comment': comment_text,
                    'Rating': rating,
                    'Date': date,
                    'ASIN': asin
                })
        
        return reviews
    except Exception as e:
        st.error(f"Error scraping reviews: {str(e)}")
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
                st.warning("No reviews found or error occurred during extraction.")

# Instructions for secrets
st.sidebar.markdown("""
### Setup Instructions
1. Create a `secrets.toml` file in the `.streamlit` directory.
2. Add your Gemini API key:
```toml
GEMINI_API_KEY = "your_api_key_here"
```
3. Ensure the ASIN is a valid 10-character Amazon identifier.
4. The app is tailored for Amazon's review page structure as of April 2025.
""")
