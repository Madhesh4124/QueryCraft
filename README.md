QueryCraft: AI SQL Assistant
This is a Streamlit web application that uses LangChain and Google's Gemini to answer natural language questions about your SQLite database.

Features
Upload a SQLite database file.

Ask questions in plain English.

View the AI-generated SQL query.

See the results from your database.

Keeps a history of your session.

How to Run
Install Packages:

pip install streamlit langchain langchain-google-genai langchain-community sqlalchemy pandas python-dotenv

Add API Key:
Create a .env file and add your key:

GOOGLE_API_KEY="YOUR_API_KEY_HERE"

Run the App:

streamlit run app.py


Working:

<img width="1856" height="963" alt="Image" src="https://github.com/user-attachments/assets/3af3cc40-b1a1-4e76-9da1-4bef49498f8a" />
