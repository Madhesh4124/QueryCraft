import streamlit as st
from sqlalchemy import create_engine, inspect, text
import os
import tempfile
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import create_sql_agent
from langchain_community.utilities.sql_database import SQLDatabase
import pandas as pd
import re

st.set_page_config(page_title='QueryCraft', page_icon='@', layout='wide')
st.title("QueryCraft: AI SQL Assistant")
st.write("Upload a SQLite database and ask questions in natural language")

load_dotenv()
google_api_key = os.getenv("GOOGLE_API_KEY")

if 'db_engine' not in st.session_state:
    st.session_state.db_engine = None
if 'sql_agent' not in st.session_state:
    st.session_state.sql_agent = None
if 'table_names' not in st.session_state:
    st.session_state.table_names = []
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'selected_model' not in st.session_state:
    st.session_state.selected_model = "gemini-2.5-flash"

with st.sidebar:
    st.header("Configuration")

    if st.button("Reset Session"):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.rerun()

    upload_file = st.file_uploader("Upload your SQLite database", type=['db', 'sqlite', 'sqlite3'])

    if upload_file is not None:
        with tempfile.NamedTemporaryFile(delete=False, suffix='.db') as tmp:
            tmp.write(upload_file.getvalue())
            temp_path = tmp.name

        st.success(f"Uploaded '{upload_file.name}' successfully.")
        try:
            engine = create_engine(f"sqlite:///{temp_path}")
            inspector = inspect(engine)
            table_names = inspector.get_table_names()

            st.session_state.db_engine = engine
            st.session_state.table_names = table_names

            st.subheader("Tables found in Database:")
            st.write(table_names)

            # Agent creation will be handled in main logic based on model selection
        except Exception as e:
            st.error(f"Error connecting to database: {e}")
            st.session_state.db_engine = None
            st.session_state.sql_agent = None
            st.session_state.table_names = []

col1, col2 = st.columns([2, 1])

with col1:
    if st.session_state.db_engine:
        st.success("Database is connected. You are ready to ask questions!")

        # --- Model selection and agent recreation ---
        available_models = ["gemini-2.5-flash", "gemini-pro", "gemini-1.5-pro"]
        selected_model = st.sidebar.selectbox(
            "Gemini Model",
            available_models,
            index=available_models.index(st.session_state.selected_model)
        )

        # Only recreate agent if model changed or agent is None
        if st.session_state.sql_agent is None or st.session_state.selected_model != selected_model:
            llm = ChatGoogleGenerativeAI(
                model=selected_model,
                temperature=0,
                google_api_key=google_api_key
            )
            sql_db = SQLDatabase(st.session_state.db_engine)
            st.session_state.sql_agent = create_sql_agent(
                llm=llm,
                db=sql_db,
                agent_type="openai-tools",
                verbose=True
            )
        st.session_state.selected_model = selected_model

        user_question = st.text_area("Your Question:", height=100)

        if st.button("Get Answer", type="primary"):
            if not google_api_key:
                st.error("Google API Key not found")
            elif not user_question:
                st.warning("Please enter a question.")
            else:
                forbidden = ["drop", "delete", "truncate"]
                if any(word in user_question.lower() for word in forbidden):
                    st.error("Destructive queries (DROP, DELETE, TRUNCATE) are not allowed.")
                else:
                    with st.spinner("Gemini is thinking..."):
                        try:
                            response = st.session_state.sql_agent.invoke({"input": user_question})

                            if "intermediate_steps" in response:
                                with st.expander("Show Agent's Thought Process"):
                                    st.write(response["intermediate_steps"])

                            st.session_state.chat_history.append({"question": user_question, "answer": response.get("output", "")})

                            st.subheader("Answer:")
                            output = response.get("output", "")

                            if isinstance(output, pd.DataFrame):
                                st.dataframe(output, use_container_width=True)
                            elif isinstance(output, list) and all(isinstance(row, dict) for row in output):
                                st.dataframe(pd.DataFrame(output), use_container_width=True)
                            elif isinstance(output, str):
                                sql_match = re.search(r"SELECT\s+.+?;", output, re.IGNORECASE | re.DOTALL)
                                if sql_match:
                                    sql_query = sql_match.group(0)
                                    try:
                                        df = pd.read_sql_query(sql_query, st.session_state.db_engine)
                                        st.dataframe(df, use_container_width=True)
                                    except Exception as e:
                                        st.error(f"Error executing SQL: {e}")
                                    st.markdown(output)
                                else:
                                    st.markdown(output)
                            else:
                                st.markdown(str(output))

                        except Exception as e:
                            friendly_msg = "❌ Gemini could not answer your question. Please check the database schema or rephrase your query."
                            st.error(f"{friendly_msg}\n\nError: {str(e)}")
    else:
        st.warning("Please upload a database file or schema to begin.")

with col2:
    st.header("Chat History")

    if st.session_state.chat_history:
        if st.button("Clear History"):
            st.session_state.chat_history = []
            st.rerun()

        st.divider()

        for i, qa in enumerate(reversed(st.session_state.chat_history), 1):
            with st.expander(f"Q{i}: {qa['question'][:40]}{'...' if len(qa['question']) > 40 else ''}"):
                st.markdown(f"**Question:** {qa['question']}")
                answer = qa['answer']
                if isinstance(answer, pd.DataFrame):
                    st.dataframe(answer, use_container_width=True)
                elif isinstance(answer, list) and all(isinstance(row, dict) for row in answer):
                    st.dataframe(pd.DataFrame(answer), use_container_width=True)
                else:
                    st.markdown(f"**Answer:** {answer}")
    else:
        st.info("No chat history yet. Ask your first question!")