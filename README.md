QueryCraft: AI SQL Assistant
This is a Streamlit web application that uses LangChain and Google's Gemini to answer natural language questions about your SQLite database.


Features
> Upload a SQLite database file.<br>
>Ask questions in plain English.<br>
> See the results from your database.<br>
> Keeps a history of your session.<br>

How to Run

1) Install Packages: <br><br>
  **pip install streamlit langchain langchain-google-genai langchain-community sqlalchemy pandas python-dotenv** <br><br>

2) Add API Key:<br>
  Create a .env file and add your key:<br><br>
  **GOOGLE_API_KEY="YOUR_API_KEY_HERE"** <br><br>

3) Run the App:<br><br>
  **streamlit run app.py** <br><br>


Working:

<img width="1856" height="963" alt="Image" src="https://github.com/user-attachments/assets/3af3cc40-b1a1-4e76-9da1-4bef49498f8a" />
