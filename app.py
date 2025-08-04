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

def extract_sql_queries(response):
    """Extract SQL queries from the agent's response and intermediate steps"""
    sql_queries = []
    
    # Check intermediate steps for SQL queries
    if "intermediate_steps" in response:
        for step in response["intermediate_steps"]:
            if len(step) >= 2:
                action, observation = step[0], step[1]
                
                # Print debug info to help troubleshoot
                print(f"Action type: {type(action)}")
                print(f"Action: {action}")
                print(f"Has tool attribute: {hasattr(action, 'tool')}")
                if hasattr(action, 'tool'):
                    print(f"Tool: {action.tool}")
                print(f"Has tool_input: {hasattr(action, 'tool_input')}")
                if hasattr(action, 'tool_input'):
                    print(f"Tool input: {action.tool_input}")
                print("---")
                
                # Multiple ways to extract SQL queries
                
                # Method 1: Direct tool_input access
                if hasattr(action, 'tool_input'):
                    if isinstance(action.tool_input, dict) and 'query' in action.tool_input:
                        sql_queries.append(action.tool_input['query'])
                    elif isinstance(action.tool_input, str) and 'SELECT' in action.tool_input.upper():
                        sql_queries.append(action.tool_input)
                
                # Method 2: Check action attributes
                if hasattr(action, 'tool') and hasattr(action.tool, 'name'):
                    if 'sql_db_query' in action.tool.name and hasattr(action, 'tool_input'):
                        if isinstance(action.tool_input, dict) and 'query' in action.tool_input:
                            sql_queries.append(action.tool_input['query'])
                
                # Method 3: String parsing from action representation
                action_str = str(action)
                if 'sql_db_query' in action_str and 'SELECT' in action_str.upper():
                    # Try different regex patterns
                    patterns = [
                        r"'query':\s*'([^']+)'",
                        r'"query":\s*"([^"]+)"',
                        r'query[\'"]?\s*:\s*[\'"]([^\'"\}]+)[\'"]',
                        r'(SELECT\s+[^}]+?)(?=\}|$)',
                    ]
                    
                    for pattern in patterns:
                        matches = re.findall(pattern, action_str, re.IGNORECASE | re.DOTALL)
                        for match in matches:
                            if 'SELECT' in match.upper():
                                sql_queries.append(match.strip())
    
    # Clean up and remove duplicates while preserving order
    unique_queries = []
    for query in sql_queries:
        query = query.strip()
        if query and query not in unique_queries and 'SELECT' in query.upper():
            # Clean up the query
            query = query.replace('\\n', ' ').replace('\\t', ' ')
            # Remove extra spaces
            query = ' '.join(query.split())
            # Ensure query ends with semicolon if it doesn't already
            if not query.endswith(';'):
                query += ';'
            unique_queries.append(query)
    
    return unique_queries

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

        # Create agent if it doesn't exist
        if st.session_state.sql_agent is None:
            llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
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
                            # Capture the verbose output
                            import io
                            import sys
                            from contextlib import redirect_stdout, redirect_stderr
                            
                            # Capture stdout to get verbose output
                            captured_output = io.StringIO()
                            
                            with redirect_stdout(captured_output):
                                response = st.session_state.sql_agent.invoke({"input": user_question})
                            
                            # Get the captured verbose output
                            verbose_output = captured_output.getvalue()
                            
                            # Extract SQL queries from verbose output as backup
                            sql_from_verbose = []
                            if verbose_output:
                                # Look for sql_db_query invocations in verbose output
                                sql_pattern = r"Invoking: `sql_db_query` with `\{'query': '([^']+)'\}`"
                                sql_matches = re.findall(sql_pattern, verbose_output)
                                sql_from_verbose.extend(sql_matches)
                            
                            # Extract SQL queries from the response
                            sql_queries = extract_sql_queries(response)
                            
                            # Use verbose output as backup if main extraction failed
                            if not sql_queries and sql_from_verbose:
                                sql_queries = [query + ';' for query in sql_from_verbose]
                            
                            # Display SQL queries if found
                            if sql_queries:
                                st.subheader("🔍 Generated SQL Query:")
                                for i, query in enumerate(sql_queries, 1):
                                    if len(sql_queries) > 1:
                                        st.write(f"**Query {i}:**")
                                    st.code(query, language="sql")
                            else:
                                # Show verbose output for debugging if no SQL found
                                if verbose_output:
                                    with st.expander("Debug: Verbose Output"):
                                        st.text(verbose_output)

                            if "intermediate_steps" in response:
                                with st.expander("Show Agent's Thought Process"):
                                    st.write(response["intermediate_steps"])

                            # Store in chat history with SQL queries
                            chat_entry = {
                                "question": user_question, 
                                "answer": response.get("output", ""),
                                "sql_queries": sql_queries
                            }
                            st.session_state.chat_history.append(chat_entry)

                            st.subheader("📊 Answer:")
                            output = response.get("output", "")

                            if isinstance(output, pd.DataFrame):
                                st.dataframe(output, use_container_width=True)
                            elif isinstance(output, list) and all(isinstance(row, dict) for row in output):
                                st.dataframe(pd.DataFrame(output), use_container_width=True)
                            elif isinstance(output, str):
                                # Try to execute the first SQL query if available
                                if sql_queries:
                                    try:
                                        df = pd.read_sql_query(sql_queries[0], st.session_state.db_engine)
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
                
                # Display SQL queries in chat history if available
                if 'sql_queries' in qa and qa['sql_queries']:
                    st.markdown("**Generated SQL:**")
                    for j, query in enumerate(qa['sql_queries'], 1):
                        if len(qa['sql_queries']) > 1:
                            st.write(f"Query {j}:")
                        st.code(query, language="sql")
                
                answer = qa['answer']
                if isinstance(answer, pd.DataFrame):
                    st.dataframe(answer, use_container_width=True)
                elif isinstance(answer, list) and all(isinstance(row, dict) for row in answer):
                    st.dataframe(pd.DataFrame(answer), use_container_width=True)
                else:
                    st.markdown(f"**Answer:** {answer}")
    else:
        st.info("No chat history yet. Ask your first question!")