import streamlit as st
import requests
import pandas as pd
from bs4 import BeautifulSoup
import re
from datetime import datetime

# Streamlit page configuration
st.set_page_config(page_title="Product Comments Extractor", layout="wide")

# Title and description
st.title("Product Comments Extractor")
st.markdown("Extract user comments for a specific product from a webpage and export them to Excel.")

# Input fields
url = st.text_input("Enter the product webpage URL:", placeholder="https://example.com/product")
product_name = st.text_input("Enter the product name:", placeholder="e.g., Wireless Headphones")
submit_button = st.button("Extract Comments")

# Function to clean text
def clean_text(text):
    text = re.sub(r'\s+', ' ', text.strip())
    return text

# Function to scrape comments (customize based on webpage structure)
def scrape_comments(url):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Example: Adjust selector based on actual webpage structure
        comment_elements = soup.select('div.review, div.comment, article.comment')
        comments = []
        
        for element in comment_elements:
            username = element.select_one('.username, .author, .user')
            username = clean_text(username.get_text()) if username else "Anonymous"
            
            comment_text = element.select_one('.comment-text, .review-body, .content')
            comment_text = clean_text(comment_text.get_text()) if comment_text else ""
            
            rating = element.select_one('.rating, .stars, .score')
            rating = clean_text(rating.get_text()) if rating else "N/A"
            
            date = element.select_one('.date, .timestamp, .posted-date')
            date = clean_text(date.get_text()) if date else "N/A"
            
            if comment_text:
                comments.append({
                    'Username': username,
                    'Comment': comment_text,
                    'Rating': rating,
                    'Date': date
                })
        
        return comments
    except Exception as e:
        st.error(f"Error scraping comments: {str(e)}")
        return []

# Function to call Gemini API for sentiment analysis
def analyze_sentiment(comment):
    try:
        api_key = st.secrets["GEMINI_API_KEY"]
        url = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
        headers = {'Content-Type': 'application/json'}
        data = {
            "contents": [{
                "parts": [{"text": f"Analyze the sentiment of this comment: '{comment}'. Return 'Positive', 'Negative', or 'Neutral'."}]
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
if submit_button and url and product_name:
    with st.spinner("Extracting comments..."):
        comments = scrape_comments(url)
        
        if comments:
            # Add sentiment analysis
            for comment in comments:
                comment['Sentiment'] = analyze_sentiment(comment['Comment'])
            
            # Create DataFrame
            df = pd.DataFrame(comments)
            
            # Display results
            st.subheader(f"Comments for {product_name}")
            st.dataframe(df)
            
            # Export to Excel
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{product_name.replace(' ', '_')}_comments_{timestamp}.xlsx"
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
            st.warning("No comments found or error occurred during extraction.")

# Instructions for secrets
st.sidebar.markdown("""
### Setup Instructions
1. Create a `secrets.toml` file in the `.streamlit` directory.
2. Add your Gemini API key:
```toml
GEMINI_API_KEY = "your_api_key_here"
```
3. Ensure the webpage URL contains user comments in a scrapable format.
4. Adjust the CSS selectors in the `scrape_comments` function if needed for the target website.
""")
